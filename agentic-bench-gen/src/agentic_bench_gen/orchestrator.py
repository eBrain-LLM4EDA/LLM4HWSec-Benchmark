from __future__ import annotations

import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .agents import AgentConfig, FileBundleAgent, JsonAgent
from .domains import profile_as_prompt_context
from .llm import OpenRouterLLM
from .runner import DockerConfig, EvaluationRunner
from .utils import read_yaml, slugify
from .validator import _CODE_EXTS, _CWE_ID_RE, _SR_ID_RE, _compute_differential_validation, quality_report, validate_benchmark_case
from .workspace import Workspace
from .logio import console

def _resolve_max_tokens(name: str, spec: dict[str, Any], cfg_defaults: dict[str, Any],
                        overrides: dict[str, Any] | None = None) -> int:
    """Resolve an agent's max_tokens. Precedence: the pipeline.yaml
    `agent_max_tokens.<agent>` override > the agent's `max_tokens` in agents.yaml
    > the `defaults.max_tokens` > 16000.

    e.g. setting `agent_max_tokens: {tester: 24000}` in pipeline.yaml caps the
    Tester's output.
    """
    overrides = overrides or {}
    if name in overrides and overrides[name] is not None:
        return int(overrides[name])
    return int(spec.get("max_tokens", cfg_defaults.get("max_tokens", 16000)))


def load_agents(
    llm: OpenRouterLLM,
    agents_cfg_path: Path,
    defaults: dict[str, Any],
    max_tokens_overrides: dict[str, Any] | None = None,
) -> dict[str, JsonAgent]:
    raw = read_yaml(agents_cfg_path)
    cfg_defaults = raw.get("defaults", defaults)
    project_root = agents_cfg_path.parent.parent
    agents: dict[str, JsonAgent] = {}
    for name, spec in raw["agents"].items():
        # per_file switches the agent to two-phase bundle generation (JSON plan,
        # then one plain-text completion per file) so no single response has to
        # fit a whole bundle under the output-token cap.
        agent_cls = FileBundleAgent if spec.get("per_file") else JsonAgent
        agents[name] = agent_cls(
            llm,
            AgentConfig(
                name=name,
                model=spec["model"],
                prompt_path=(project_root / spec["prompt"]).resolve(),
                schema_path=(project_root / spec["schema"]).resolve(),
                temperature=float(spec.get("temperature", cfg_defaults.get("temperature", 0.1))),
                max_tokens=_resolve_max_tokens(name, spec, cfg_defaults, max_tokens_overrides),
                reasoning=spec.get("reasoning", cfg_defaults.get("reasoning")),
                allowed_paths=spec.get("allowed_paths"),
                plan_max_tokens=(int(spec["plan_max_tokens"])
                                 if spec.get("plan_max_tokens") is not None
                                 else (int(cfg_defaults["plan_max_tokens"])
                                       if cfg_defaults.get("plan_max_tokens") is not None else None)),
            ),
        )
    return agents


def _unique_workspace(out_root: Path, task_id: str) -> Path:
    candidate = out_root / task_id
    if not candidate.exists():
        return candidate
    idx = 1
    while True:
        candidate = out_root / f"{task_id}_gen{idx:03d}"
        if not candidate.exists():
            return candidate
        idx += 1


class BenchGenOrchestrator:
    """Domain-modular agentic benchmark generation pipeline."""

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path).resolve()
        self.pipeline_cfg = read_yaml(self.config_path)
        openrouter_cfg = self.pipeline_cfg.get("openrouter", {})
        self.llm = OpenRouterLLM.from_env(
            base_url=openrouter_cfg.get("base_url", "https://openrouter.ai/api/v1"),
            timeout_seconds=float(openrouter_cfg.get("timeout_seconds", 120)),
            max_retries=int(openrouter_cfg.get("max_retries", 3)),
            max_output_tokens=int(openrouter_cfg.get("max_output_tokens", 64000)),
            # Default reasoning OFF: hidden reasoning tokens bill as completion
            # tokens and eat each agent's max_tokens budget from the inside.
            # Set `openrouter.reasoning` in pipeline.yaml to override, or
            # `reasoning: null` to fall back to the provider default.
            reasoning=openrouter_cfg.get("reasoning", {"enabled": False}),
            # Provider routing pin (openrouter.provider in pipeline.yaml):
            # non-Anthropic endpoints serving the same model content-filter
            # this benchmark's vulnerability-heavy prompts.
            provider=openrouter_cfg.get("provider"),
        )
        agents_cfg_path = (self.config_path.parent.parent / self.pipeline_cfg["agents_config"]).resolve()
        self.agents = load_agents(
            self.llm,
            agents_cfg_path,
            self.pipeline_cfg.get("defaults", {}),
            max_tokens_overrides=self.pipeline_cfg.get("agent_max_tokens", {}),
        )
        self.runner = self._build_runner(self.pipeline_cfg.get("execution", {}))
        # Surface a missing daemon / un-built image up front rather than as
        # silent baseline failures on every generated case.
        self.runner.check_available()

    @staticmethod
    def _build_runner(exec_cfg: dict[str, Any]) -> EvaluationRunner:
        return EvaluationRunner(
            timeout_seconds=int(exec_cfg.get("timeout_seconds", 60)),
            use_docker=bool(exec_cfg.get("use_docker", False)),
            docker=DockerConfig(
                image=str(exec_cfg.get("docker_image", "agentic-bench-gen-runner:latest")),
                network=str(exec_cfg.get("network", "none")),
                memory_limit=str(exec_cfg.get("memory_limit", "2g")),
                cpus=str(exec_cfg.get("cpus", "2.0")),
                pids_limit=int(exec_cfg.get("pids_limit", 512)),
                extra_args=list(exec_cfg.get("extra_docker_args", [])),
            ),
        )

    def generate(self, seed_path: str | Path, out_dir: str | Path) -> list[Path]:
        seeds = read_yaml(seed_path)
        out_root = Path(out_dir).resolve()
        out_root.mkdir(parents=True, exist_ok=True)
        # Mirror everything printed from here on into a per-run log file, so a
        # failed multi-hour run can be debugged without the terminal scrollback.
        log_path = out_root / "generation.log"
        console.attach_log_file(log_path)
        console.print(
            f"[dim]Run log: {log_path} | seed={Path(seed_path).resolve()} | "
            f"config={self.config_path}[/dim]"
        )
        max_repair = int(self.pipeline_cfg.get("pipeline", {}).get("max_repair_rounds", 2))
        expand = bool(self.pipeline_cfg.get("pipeline", {}).get("expand_seeds", True))
        # TODO: Check why we are expanding a single idea into multiple when idea is quite specific
        # either changes in examples or this expendiation is needed
        generated: list[Path] = []
        failed: list[str] = []
        for raw_seed in seeds:
            ideas = self._expand_seed(raw_seed) if expand and "idea_generator" in self.agents else [raw_seed]
            for idea in ideas:
                label = str(idea.get("task_id") or idea.get("seed_id") or idea.get("title") or "unnamed_idea")
                try:
                    generated.append(self._generate_one(idea, out_root, max_repair))
                except Exception as exc:
                    # One idea's failure must not cost the rest of the run: log it
                    # (its partial workspace stays on disk for inspection) and
                    # continue with the remaining ideas and seeds.
                    failed.append(label)
                    console.print(f"[red]Case generation FAILED for {label!r}:[/red] {exc}")
        if failed:
            console.print(
                f"[red]{len(failed)} case(s) failed:[/red] " + ", ".join(failed)
            )
            if not generated:
                raise RuntimeError(
                    f"All {len(failed)} case generation attempt(s) failed; see errors above."
                )
        return generated

    def _expand_seed(self, raw_seed: dict[str, Any]) -> list[dict[str, Any]]:
        domain_context = profile_as_prompt_context(str(raw_seed.get("domain_id", "hls_security_codegen")))
        console.print(f"[bold cyan]IdeaGenerator:[/bold cyan] expanding {raw_seed.get('seed_id', 'seed')}")
        try:
            bundle = self.agents["idea_generator"].run({
                "seed_yaml": raw_seed,
                "domain_profile_json": domain_context,
            })
            return bundle.get("ideas", [raw_seed])
        except Exception as exc:
            console.print(f"[yellow]IdeaGenerator failed ({exc}); using raw seed.[/yellow]")
            return [raw_seed]

    def _generate_one(self, idea: dict[str, Any], out_root: Path, max_repair: int) -> Path:
        repair_notes = ""
        task_spec: dict[str, Any] | None = None
        artifact_bundle: dict[str, Any] | None = None
        expert_bundle: dict[str, Any] | None = None
        tester_bundle: dict[str, Any] | None = None
        mutation_bundle: dict[str, Any] | None = None
        analyzer_report: dict[str, Any] | None = None
        arbiter_decision: dict[str, Any] | None = None
        # Holds the PREVIOUS round's report at the top of each round (this
        # round's is computed after the Mutator); the mutants-only repair path
        # reads its flagged-requirement lists.
        validation: dict[str, Any] | None = None
        ws_path: Path | None = None
        generate_mutants = bool(self.pipeline_cfg.get("pipeline", {}).get("generate_mutants", True))

        # Keep-best / no-regression tracking: a repair round can regress an
        # earlier, better candidate (e.g. break a passing baseline). We snapshot
        # the best round and restore it if the final round is worse.
        best_key: tuple[Any, ...] | None = None
        best_snapshot: Path | None = None
        best_round = -1
        best_validation: dict[str, Any] | None = None
        best_analyzer: dict[str, Any] | None = None
        last_round = 0

        for round_idx in range(max_repair + 1):
            last_round = round_idx
            evaluator_ok = True
            try:
                artifact_to_fix = arbiter_decision["artifact_to_revise"] if arbiter_decision else "none"
                domain_id = str(idea.get("domain_id", "hls_security_codegen"))
                domain_context = profile_as_prompt_context(domain_id)

                if round_idx == 0 or artifact_to_fix == "specification":
                    console.print(f"[bold]Architect (round {round_idx}):[/bold] {domain_id}")
                    task_spec = self.agents["architect"].run({
                        "seed_yaml": idea,
                        "domain_profile_json": domain_context,
                        "submission_contract": domain_context.get("submission_contract", ""),
                        # Non-empty only for simulate domains: mandates that the
                        # interface pin exact cycle timing so the independently
                        # authored reference and golden land on one waveform.
                        "interface_timing_contract": domain_context.get("interface_timing_contract", ""),
                        "repair_notes": repair_notes,
                    })
                    task_spec = _normalize_task_spec(task_spec, idea, domain_context)

                task_id = str(task_spec["task_id"])
                if ws_path is None:
                    ws_path = _unique_workspace(out_root, task_id)
                ws = Workspace(ws_path)
                ws.write_json("spec/task_spec.json", task_spec)
                ws.write_json("spec/public_spec.json", task_spec["public_spec"])
                ws.write_json("spec/hidden_spec.json", task_spec["hidden_spec"])

                if round_idx == 0 or artifact_to_fix in {"specification", "case_artifacts"}:
                    console.print(f"[bold]ArtifactBuilder (round {round_idx}):[/bold] {task_id}")
                    artifact_bundle = self.agents["artifact_builder"].run({
                        "task_spec_json": task_spec,
                        "domain_profile_json": domain_context,
                        "submission_contract": domain_context.get("submission_contract", ""),
                        "repair_notes": repair_notes,
                        # Repair rounds hand the agent its own previous output so it
                        # patches the identified defect instead of rewriting from
                        # scratch (rewrites regularly regress what already worked).
                        "previous_bundle_json": artifact_bundle or "",
                    })
                    # Clear bundle-managed dirs first so a repair round cannot leave
                    # stale files (e.g. renamed inputs) from an earlier round behind.
                    # Also clear submission/ — for analysis_report domains the
                    # ArtifactBuilder ships the naive baseline answer there.
                    _reset_dirs(ws, ["inputs", "submission"])
                    ws.write_json("artifacts/artifact_bundle.json", artifact_bundle)
                    ws.write_file_bundle(artifact_bundle)
                    # The files actually shipped under inputs/ are ground truth for
                    # what evaluate.py may open; a spec that declares anything else
                    # (e.g. the case-root README.md as an "input artifact") sends
                    # the Tester chasing files that don't exist — every run then
                    # dies at SETUP and no Tester retry can ever fix it.
                    task_spec = _reconcile_input_artifacts(task_spec, artifact_bundle)
                    ws.write_json("spec/task_spec.json", task_spec)
                    ws.write_json("spec/public_spec.json", task_spec["public_spec"])

                if round_idx == 0 or artifact_to_fix in {"specification", "case_artifacts"}:
                    console.print(f"[bold]Expert (round {round_idx}):[/bold] golden reference for {task_id}")
                    expert_bundle = self.agents["expert"].run({
                        "task_spec_json": task_spec,
                        "domain_profile_json": domain_context,
                        "submission_contract": domain_context.get("submission_contract", ""),
                        "repair_notes": repair_notes,
                        "previous_bundle_json": expert_bundle or "",
                    })
                    _reset_dirs(ws, ["golden", "ground_truth"])
                    ws.write_json("expert/expert_bundle.json", expert_bundle)
                    ws.write_file_bundle(expert_bundle)

                if round_idx == 0 or artifact_to_fix in {"specification", "case_artifacts", "evaluation_framework"}:
                    console.print(f"[bold]Tester (round {round_idx}):[/bold] requirement harnesses for {task_id}")
                    _input_artifacts = task_spec.get("public_spec", {}).get("input_artifacts", [])
                    tester_vars = {
                        "task_spec_json": task_spec,
                        "domain_profile_json": domain_context,
                        "submission_contract": domain_context.get("submission_contract", ""),
                        "evaluation_contract": domain_context.get("evaluation_contract", ""),
                        "repair_notes": repair_notes,
                        "input_artifact_filenames": "\n".join(f"- {f}" for f in _input_artifacts),
                        "artifact_bundle_json": _slim_artifact_for_prompt(artifact_bundle),
                        "previous_bundle_json": tester_bundle or "",
                    }
                    tester_bundle = self.agents["tester"].run(tester_vars)
                    _write_tester_bundle(ws, tester_bundle)
                    # Deterministic pre-flight: run the differential gate now and, if
                    # the evaluator mis-grades golden/baseline, retry the Tester once
                    # with the run output — one LLM call instead of a full
                    # Analyzer+Arbiter repair round for the common regex/filename bugs.
                    tester_bundle, evaluator_ok = self._tester_preflight(ws, task_spec, expert_bundle, tester_bundle, tester_vars)
                    if not evaluator_ok:
                        # A known-broken evaluator grades every mutant meaninglessly
                        # (validation reports mutation_score_meaningful=false), so
                        # generating mutants this round only burns LLM calls. The
                        # Arbiter still sees the differential failure and directs
                        # the repair; the next fixed round regenerates mutants.
                        console.print(
                            "  [yellow]Evaluator still mis-grades golden/baseline after pre-flight "
                            "retries; skipping mutant generation this round.[/yellow]"
                        )
                        mutation_bundle = {"mutants": [], "skipped": "tester pre-flight differential failed"}
                        ws.write_json("mutants/mutation_bundle.json", mutation_bundle)

                if generate_mutants and "mutator" in self.agents and evaluator_ok and (round_idx == 0 or artifact_to_fix in {"specification", "case_artifacts", "evaluation_framework", "mutants"}):
                    console.print(f"[bold]Mutator (round {round_idx}):[/bold] quality mutants for {task_id}")
                    # Arbiter-directed mutants revision: keep the mutants that
                    # already demonstrated discrimination and regenerate only the
                    # flagged targets, with the failed (operator, target) pairs
                    # forbidden. `validation` still holds the previous round's
                    # report here (this round's is computed after the Mutator).
                    repair_plan = (
                        _plan_mutant_repair((mutation_bundle or {}).get("mutants", []), validation)
                        if artifact_to_fix == "mutants" else None
                    )
                    failed_pairs: set[tuple[str, str]] = set()
                    if repair_plan is not None:
                        kept_mutants, targets, failed_pairs = repair_plan
                        mutation_bundle = {"mutants": list(kept_mutants)}
                        console.print(
                            f"  [cyan]mutants-only repair:[/cyan] keeping {len(kept_mutants)} "
                            f"detected mutant(s); regenerating targets {targets}."
                        )
                    else:
                        mutation_bundle = {"mutants": []}
                        # Every requirement (SR and FR) must get at least one targeting
                        # mutant, otherwise its check can never demonstrate discrimination
                        # and the dead-check / uncovered / untested gates fail on sampling
                        # rather than on real defects.
                        targets = _plan_mutation_targets(
                            _requirement_id_list(task_spec, "hidden_spec", "security_requirements"),
                            _requirement_id_list(task_spec, "public_spec", "functional_requirements"),
                            int(self.pipeline_cfg.get("pipeline", {}).get("mutants_per_case", 5)),
                        )
                    used_pairs: set[tuple[str, str]] = failed_pairs | {
                        (str(m.get("operator", "")), str(m.get("target_requirement_id", "")))
                        for m in mutation_bundle["mutants"]
                    }
                    for m_idx, required_target in enumerate(targets):
                        console.print(f"  -> generating mutant {m_idx + 1}/{len(targets)} (target {required_target})...")
                        slot_error = "mutator returned no mutants"
                        for attempt in range(3):
                            try:
                                m_bundle = self.agents["mutator"].run({
                                    "task_spec_json": task_spec,
                                    "submission_contract": domain_context.get("submission_contract", ""),
                                    "artifact_bundle_json": _slim_artifact_for_prompt(artifact_bundle),
                                    "expert_bundle_json": _slim_expert_for_prompt(expert_bundle),
                                    # Ids and types only: the Tester's detection
                                    # strategies (expected_detection) are withheld so
                                    # mutants are designed from requirement semantics,
                                    # not tailored to the specific checks — otherwise
                                    # the mutation score measures nothing.
                                    "requirement_map_json": [
                                        {
                                            "requirement_id": m.get("requirement_id"),
                                            "requirement_type": m.get("requirement_type"),
                                        }
                                        for m in (tester_bundle or {}).get("requirement_map", [])
                                    ],
                                    "required_target_requirement_id": required_target,
                                    # The Arbiter's diagnosis of why the previous
                                    # mutant went undetected — only on mutants-only
                                    # repair rounds, where it is addressed to the
                                    # Mutator rather than another agent.
                                    "repair_notes": repair_notes if repair_plan is not None else "",
                                    "previous_mutations": [
                                        {
                                            "mutant_id": m.get("mutant_id"),
                                            "operator": m.get("operator"),
                                            "target_requirement_id": m.get("target_requirement_id"),
                                        }
                                        for m in mutation_bundle["mutants"]
                                    ],
                                    "forbidden_combinations": [
                                        {"operator": op, "target_requirement_id": tgt}
                                        for op, tgt in used_pairs
                                    ],
                                })
                            except Exception as exc:
                                # Transient API errors must not silently drop the
                                # mutant slot — retry the remaining attempts.
                                slot_error = str(exc)
                                console.print(f"  -> [yellow]mutant generation failed (attempt {attempt + 1}):[/yellow] {exc}")
                                continue
                            if not m_bundle.get("mutants"):
                                console.print(f"  -> [yellow]mutator returned no mutants (attempt {attempt + 1}); retrying...[/yellow]")
                                continue
                            mutant = m_bundle["mutants"][0]
                            pair = (str(mutant.get("operator", "")), str(mutant.get("target_requirement_id", "")))
                            if pair in used_pairs and attempt < 2:
                                console.print(f"  -> [yellow]duplicate pair {pair}, retrying (attempt {attempt + 1})...[/yellow]")
                                continue
                            used_pairs.add(pair)
                            mutation_bundle["mutants"].extend(m_bundle["mutants"])
                            break
                        else:
                            # All attempts failed: the requirement loses its
                            # targeting mutant, so its check's discrimination goes
                            # unproven this round. Record the gap in the bundle so
                            # it is auditable (and visible to the Analyzer via the
                            # validation report's untested_requirements) instead of
                            # vanishing from the run.
                            console.print(
                                f"  -> [red]giving up on the mutant targeting {required_target} "
                                f"after 3 attempts; recording the gap.[/red]"
                            )
                            mutation_bundle.setdefault("generation_failures", []).append({
                                "target_requirement_id": required_target,
                                "error": slot_error,
                            })

                    ws.write_json("mutants/mutation_bundle.json", mutation_bundle)

                validation = validate_benchmark_case(task_spec, artifact_bundle, tester_bundle, expert_bundle, mutation_bundle, ws, runner=self.runner)
                ws.write_json("reports/validation_report.json", validation)
                # Round-stamped copy: the canonical file is overwritten every
                # round (and replaced wholesale by a keep-best restore), so the
                # per-round history would otherwise be unreconstructable.
                ws.write_json(f"reports/validation_report_r{round_idx}.json", validation)

                console.print(f"[bold]Analyzer (round {round_idx}):[/bold] {task_id}")
                try:
                    analyzer_report = self.agents["analyzer"].run({
                        "task_spec_json": task_spec,
                        "submission_contract": domain_context.get("submission_contract", ""),
                        # Full artifact bundle: the Analyzer judges participant-facing
                        # coherence, so README/metadata content matters here.
                        "artifact_bundle_json": artifact_bundle,
                        "tester_bundle_json": _slim_tester_for_prompt(tester_bundle),
                        "validation_report_json": validation,
                    })
                except Exception as exc:
                    # The Analyzer is an advisory coherence review on top of the
                    # deterministic validation gates. If its LLM call fails, a
                    # synthetic 'warning' report keeps the round alive (and the
                    # deterministic scores in the driver's seat) instead of
                    # discarding a round whose validation may have passed.
                    console.print(
                        f"  [red]Analyzer failed (round {round_idx}): {exc}[/red] "
                        "[yellow]— continuing with a synthetic report; deterministic "
                        "validation drives this round's decision.[/yellow]"
                    )
                    analyzer_report = {
                        "overall_status": "warning",
                        "issues": [{
                            "artifact": "pipeline",
                            "severity": "medium",
                            "description": f"Analyzer LLM call failed; no coherence review this round: {exc}",
                        }],
                        "synthetic": True,
                    }
                ws.write_json("reports/analyzer_report.json", analyzer_report)
                ws.write_json(f"reports/analyzer_report_r{round_idx}.json", analyzer_report)

                console.print(f"[bold]Arbiter (round {round_idx}):[/bold] {task_id}")
                _baseline = validation.get("baseline_run") or {}
                _ms_note = "" if validation.get("mutation_score_meaningful", True) else \
                    " (NOT MEANINGFUL — the golden/baseline run failed; fix that first)"
                _validation_summary = (
                    f"mutation_score={validation['mutation_score']}{_ms_note} | "
                    f"coverage_score={validation['coverage_score']} | "
                    f"validation_status={validation['status']} | "
                    f"baseline_exit_code={_baseline.get('exit_code', 'n/a')} | "
                    f"issue_count={len(validation.get('issues', []))} | "
                    f"analyzer_status={analyzer_report.get('overall_status', 'unknown')}"
                )
                _min_ms = float(self.pipeline_cfg.get("validation", {}).get("min_mutation_score", 0.50))
                _min_cs = float(self.pipeline_cfg.get("validation", {}).get("min_coverage_score", 0.80))
                try:
                    arbiter_decision = self.agents["arbiter"].run({
                        "task_spec_json": task_spec,
                        "submission_contract": domain_context.get("submission_contract", ""),
                        "evaluation_contract": domain_context.get("evaluation_contract", ""),
                        "analyzer_report_json": analyzer_report,
                        "validation_report_json": _slim_validation_for_arbiter(validation),
                        "artifact_bundle_json": _slim_artifact_for_prompt(artifact_bundle),
                        # Undetected/dead-target mutants with full file content so
                        # the Arbiter can distinguish a weak check (revise
                        # evaluation_framework) from a defective mutant (revise
                        # mutants); detected mutants are reduced to their ids.
                        "mutation_bundle_json": _slim_mutation_for_arbiter(mutation_bundle, validation),
                        # HardSecBench §3.3: the Arbiter observes spec, golden, harnesses
                        # and runtime evidence to localize a mismatch. The golden goes to
                        # the Arbiter ONLY — its prompt forbids echoing golden code into
                        # revision_instructions, preserving Tester-side isolation.
                        "expert_bundle_json": _slim_expert_for_prompt(expert_bundle),
                        "validation_summary": _validation_summary,
                    })
                except Exception as exc:
                    # Retention is deterministically decidable from the validation
                    # gates; an Arbiter outage should degrade to that decision, not
                    # kill the case. artifact_to_revise='none' ends the repair loop
                    # (no diagnosis means no targeted revision to attempt).
                    _retain = _deterministic_retain(validation, analyzer_report, _min_ms, _min_cs)
                    console.print(
                        f"  [red]Arbiter failed (round {round_idx}): {exc}[/red] "
                        f"[yellow]— falling back to deterministic thresholds "
                        f"(retain_case={_retain}).[/yellow]"
                    )
                    arbiter_decision = {
                        "retain_case": _retain,
                        "artifact_to_revise": "none",
                        "failure_localization": "",
                        "revision_instructions": "",
                        "synthetic": f"Arbiter LLM call failed: {exc}",
                    }

                # Guard: if the Arbiter hallucinated the mutation_score, auto-correct retain_case
                # in BOTH directions based on the actual, deterministically-computed scores.
                _actual_ms = float(validation["mutation_score"])
                _reported_ms = float(arbiter_decision.get("observed_mutation_score", _actual_ms))
                if abs(_reported_ms - _actual_ms) > 0.01:
                    console.print(
                        f"  [yellow]Arbiter score mismatch: reported {_reported_ms}, "
                        f"actual {_actual_ms} — re-evaluating retain decision[/yellow]"
                    )
                    _actually_passes = _deterministic_retain(validation, analyzer_report, _min_ms, _min_cs)
                    if _actually_passes and not arbiter_decision.get("retain_case", False):
                        arbiter_decision["retain_case"] = True
                        arbiter_decision["_score_corrected"] = (
                            f"hallucinated {_reported_ms}, actual {_actual_ms} — retained on actual scores"
                        )
                        console.print("  [green]Corrected: case retained based on actual scores.[/green]")
                    elif not _actually_passes and arbiter_decision.get("retain_case", False):
                        arbiter_decision["retain_case"] = False
                        arbiter_decision["_score_corrected"] = (
                            f"hallucinated {_reported_ms}, actual {_actual_ms} — un-retained on actual scores"
                        )
                        console.print("  [yellow]Corrected: case un-retained; actual scores miss thresholds.[/yellow]")

                ws.write_json(f"reports/arbiter_decision_r{round_idx}.json", arbiter_decision)

                # Snapshot this round if it is the best seen so far, so a later
                # regressing round cannot cost us a strictly better candidate.
                round_key = _round_quality_key(validation, analyzer_report)
                if best_key is None or round_key > best_key:
                    best_snapshot = _snapshot_workspace(ws.root, best_snapshot)
                    best_key = round_key
                    best_round = round_idx
                    best_validation = validation
                    best_analyzer = analyzer_report

                if arbiter_decision.get("retain_case", False):
                    break
                if arbiter_decision.get("artifact_to_revise", "none") == "none":
                    # Nothing would regenerate next round — running validation,
                    # Analyzer and Arbiter again on identical artifacts only burns
                    # LLM calls. Stop here.
                    console.print(
                        "  [yellow]Arbiter did not retain the case but named no artifact to revise; "
                        "stopping repair rounds.[/yellow]"
                    )
                    break
                repair_notes = json.dumps(arbiter_decision, indent=2, sort_keys=True)
            except Exception as exc:
                # A failed repair round must not abandon the earlier rounds' work:
                # with a best-round snapshot in hand, stop repairing and keep it.
                # (Round 0 has nothing to fall back to, so its failures propagate.)
                if best_snapshot is None:
                    raise
                console.print(
                    f"  [red]Round {round_idx} failed ({exc});[/red] "
                    f"[yellow]stopping repair and keeping best round {best_round}.[/yellow]"
                )
                break

        try:
            # Restore the best round if the final round regressed below it.
            if best_snapshot is not None and best_round != last_round:
                console.print(
                    f"  [cyan]keep-best:[/cyan] final round {last_round} is worse than round "
                    f"{best_round}; restoring the better candidate."
                )
                _restore_workspace(ws.root, best_snapshot)
                # Debugging breadcrumb: the canonical reports now describe the
                # restored round, not the last one executed — say so explicitly.
                ws.write_json("reports/keep_best.json", {
                    "restored_round": best_round,
                    "final_round": last_round,
                    "note": "Later rounds regressed; canonical artifacts/reports are from "
                            "restored_round. Per-round history is in the *_r<N>.json reports.",
                })

            ws.write_json("reports/quality_report.json", quality_report(
                best_validation if best_validation is not None else ws_read_json(ws, "reports/validation_report.json"),
                best_analyzer or analyzer_report or {"overall_status": "fail", "issues": []},
                min_coverage_score=float(self.pipeline_cfg.get("validation", {}).get("min_coverage_score", 0.80)),
                min_mutation_score=float(self.pipeline_cfg.get("validation", {}).get("min_mutation_score", 0.50)),
            ))
        finally:
            if best_snapshot is not None:
                shutil.rmtree(best_snapshot.parent, ignore_errors=True)
        totals = getattr(self.llm, "usage_totals", None)
        if totals:
            console.print(
                f"  [dim]LLM usage (run cumulative): in={totals['prompt_tokens']} "
                f"out={totals['completion_tokens']} reasoning={totals['reasoning_tokens']} "
                f"calls={totals['calls']}[/dim]"
            )
        return ws.root

    def _tester_preflight(
        self,
        ws: Workspace,
        task_spec: dict[str, Any],
        expert_bundle: dict[str, Any] | None,
        tester_bundle: dict[str, Any],
        tester_vars: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        """Run the differential gate right after the Tester and, while the
        evaluator mis-grades the golden solution or the insecure baseline, retry
        the Tester with the actual evaluator output (runtime evidence only — the
        golden source itself is never shown, preserving Expert/Tester isolation).
        Each retry is re-checked and the best bundle seen is kept, so a retry
        can never silently replace a better earlier evaluator. Deterministic and
        cheap compared to discovering the same bug a full repair round later.

        Returns (bundle, evaluator_ok); evaluator_ok=False means the gate still
        fails after all retries, so downstream mutation scoring is meaningless."""
        diff = _compute_differential_validation(task_spec, expert_bundle or {}, ws, self.runner)
        if diff.get("status") != "fail":
            return tester_bundle, True
        retries = int(self.pipeline_cfg.get("pipeline", {}).get("tester_preflight_retries", 1))
        best_bundle, best_key = tester_bundle, _preflight_key(diff)
        notes_base = tester_vars.get("repair_notes") or ""
        # Each retry repairs the attempt whose evaluator output is in the notes,
        # not a blank slate — the previous bundle travels with the request.
        previous = tester_bundle
        for attempt in range(1, retries + 1):
            console.print(
                f"  [yellow]Tester pre-flight failed; retrying Tester "
                f"({attempt}/{retries}) with evaluator output.[/yellow]"
            )
            notes = (notes_base + "\n\n" if notes_base else "") + _preflight_notes(diff)
            try:
                candidate = self.agents["tester"].run({
                    **tester_vars, "repair_notes": notes, "previous_bundle_json": previous,
                })
            except Exception as exc:
                console.print(f"  [yellow]Pre-flight Tester retry failed ({exc}).[/yellow]")
                break
            previous = candidate
            _write_tester_bundle(ws, candidate)
            diff = _compute_differential_validation(task_spec, expert_bundle or {}, ws, self.runner)
            key = _preflight_key(diff)
            if key > best_key:
                best_bundle, best_key = candidate, key
            if diff.get("status") != "fail":
                return candidate, True
        # All retries exhausted (or errored): make sure the workspace holds the
        # best bundle seen, not merely the last one written.
        _write_tester_bundle(ws, best_bundle)
        return best_bundle, False


def _reconcile_input_artifacts(task_spec: dict[str, Any], artifact_bundle: dict[str, Any] | None) -> dict[str, Any]:
    """Set public_spec.input_artifacts to the basenames of the files the
    ArtifactBuilder actually shipped under inputs/. That list drives the Tester
    prompt ("the ONLY files evaluate.py may open"), the evaluator-scope check,
    and the golden-overlay staging — when the spec declares a file that was
    never shipped (seen with a case-root README.md declared as an input),
    evaluate.py fails at SETUP on every run and no Tester retry can fix it."""
    shipped = [
        Path(str(f.get("path", ""))).name
        for f in (artifact_bundle or {}).get("files", [])
        if str(f.get("path", "")).startswith("inputs/")
    ]
    if not shipped:
        return task_spec
    declared = [str(x) for x in task_spec.get("public_spec", {}).get("input_artifacts", []) or []]
    if set(declared) != set(shipped):
        console.print(
            f"  [yellow]input_artifacts reconciled to the shipped inputs/ files {shipped} "
            f"(spec declared {declared}).[/yellow]"
        )
        task_spec.setdefault("public_spec", {})["input_artifacts"] = shipped
    return task_spec


# Matches a leaked identifier plus the immediate joining punctuation, so
# removal reads cleanly: "(e.g., CWE-226 uncleared data)" -> "(e.g., uncleared data)".
_PUBLIC_LEAK_TOKEN_RE = re.compile(rf"(?:{_CWE_ID_RE.pattern}|{_SR_ID_RE.pattern})[:,]?\s*", re.IGNORECASE)


def _scrub_public_security_ids(value: Any, removed: list[str]) -> Any:
    """Deterministically strip CWE/SR identifiers from public_spec prose.
    The Architect is instructed to keep them in hidden_spec, but when one slips
    through, the validator's leak gate fails the round and — because the Arbiter
    names a single artifact_to_revise — the leak can survive repair rounds that
    revise something else. Scrubbing at normalize time removes the whole class.
    Filenames (input_artifacts) are left alone: renaming a file here would break
    the shipped-artifact match, and the validator still flags leaky names."""
    if isinstance(value, str):
        found = _CWE_ID_RE.findall(value) + _SR_ID_RE.findall(value)
        if not found:
            return value
        removed.extend(found)
        return re.sub(r"\s{2,}", " ", _PUBLIC_LEAK_TOKEN_RE.sub("", value)).strip()
    if isinstance(value, list):
        return [_scrub_public_security_ids(item, removed) for item in value]
    if isinstance(value, dict):
        return {key: _scrub_public_security_ids(item, removed) for key, item in value.items()}
    return value


def _slim_artifact_for_prompt(artifact_bundle: dict[str, Any] | None) -> dict[str, Any]:
    """Downstream agents only reason about the graded inputs/ files; shipping
    README/metadata content re-bills prompt tokens on every call for nothing."""
    bundle = artifact_bundle or {}
    return {"files": [f for f in bundle.get("files", []) if str(f.get("path", "")).startswith("inputs/")]}


def _slim_expert_for_prompt(expert_bundle: dict[str, Any] | None) -> dict[str, Any]:
    """The Mutator corrupts the golden submission. Keep everything under golden/
    (the answer files it starts from — code for hardened_artifact domains, JSON
    reports/labels for analysis_report domains) plus any code file; drop
    ground_truth oracle labels and reports, which are dead weight."""
    bundle = expert_bundle or {}
    return {"files": [
        f for f in bundle.get("files", [])
        if "golden" in Path(str(f.get("path", ""))).parts
        or Path(str(f.get("path", ""))).suffix in _CODE_EXTS
    ]}


def _slim_tester_for_prompt(tester_bundle: dict[str, Any] | None) -> dict[str, Any]:
    """Keep the evaluator and the requirement map; the private per-check harness
    bodies largely duplicate evaluate.py and dominate the bundle's size."""
    bundle = tester_bundle or {}
    return {
        "manifest": bundle.get("manifest", []),
        "requirement_map": bundle.get("requirement_map", []),
        "files": [f for f in bundle.get("files", []) if str(f.get("path", "")).startswith("evaluation/")],
    }


def _reset_dirs(ws: Workspace, subdirs: list[str]) -> None:
    """Remove bundle-managed directories before rewriting a regenerated bundle,
    so repair rounds cannot leave stale files from an earlier round in the case."""
    for sub in subdirs:
        target = ws.path(sub)
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)


def _requirement_id_list(task_spec: dict[str, Any], section: str, key: str) -> list[str]:
    reqs = task_spec.get(section, {}).get(key, []) or []
    return [str(r.get("id", "")).strip() for r in reqs if str(r.get("id", "")).strip()]


def _plan_mutation_targets(sr_ids: list[str], fr_ids: list[str], requested: int) -> list[str]:
    """Plan one target requirement per mutant: every SR and every FR exactly
    once, then cycle FRs (or SRs when there are no FRs) to fill any slots a
    larger mutants_per_case asks for. Every requirement must appear — a
    requirement with no targeting mutant can never demonstrate discrimination,
    and the validation report carries a permanent untested_requirements gap.
    (A previous version filled only min(2, len(FRs)) FR slots, always starting
    at FR1, which deterministically starved FR3+ in every case of a whole run.)
    The configured mutants_per_case acts as a floor, never a cap."""
    if not sr_ids and not fr_ids:
        return []
    targets = list(sr_ids) + list(fr_ids)
    fill = fr_ids or sr_ids
    idx = 0
    while len(targets) < requested:
        targets.append(fill[idx % len(fill)])
        idx += 1
    return targets


def _plan_mutant_repair(
    prior_mutants: list[dict[str, Any]],
    validation: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[str], set[tuple[str, str]]] | None:
    """Selective plan for an Arbiter `artifact_to_revise == "mutants"` round:
    keep every mutant that already demonstrated discrimination and regenerate
    one mutant per requirement the validation flagged (undetected, dead-check,
    or never targeted). Returns (kept_mutants, regen_targets, failed_pairs) —
    failed_pairs are the (operator, target) combinations of the discarded
    mutants, forbidden on regeneration so the same defective mutant does not
    come back. Returns None when there is nothing to selectively repair, in
    which case the caller falls back to full regeneration."""
    if not prior_mutants or not isinstance(validation, dict):
        return None
    problem_ids = (
        set(validation.get("uncovered_requirements") or [])
        | set(validation.get("dead_checks") or [])
        | set(validation.get("untested_requirements") or [])
    )
    if not problem_ids:
        return None
    kept = [m for m in prior_mutants if str(m.get("target_requirement_id", "")) not in problem_ids]
    failed_pairs = {
        (str(m.get("operator", "")), str(m.get("target_requirement_id", "")))
        for m in prior_mutants
        if str(m.get("target_requirement_id", "")) in problem_ids
    }
    return kept, sorted(problem_ids), failed_pairs


def _slim_mutation_for_arbiter(
    mutation_bundle: dict[str, Any] | None,
    validation: dict[str, Any],
) -> dict[str, Any]:
    """The Arbiter must be able to tell a weak check from a weak mutant, which
    requires reading what the undetected mutants actually changed. Ship full
    file content only for mutants targeting flagged requirements; the detected
    ones contribute nothing to that diagnosis and are reduced to their ids."""
    bundle = mutation_bundle or {}
    flagged = (
        set(validation.get("uncovered_requirements") or [])
        | set(validation.get("dead_checks") or [])
    )
    mutants: list[dict[str, Any]] = []
    for m in bundle.get("mutants", []):
        entry: dict[str, Any] = {
            "mutant_id": m.get("mutant_id"),
            "operator": m.get("operator"),
            "target_requirement_id": m.get("target_requirement_id"),
        }
        if str(m.get("target_requirement_id", "")) in flagged:
            entry["expected_detection"] = m.get("expected_detection")
            entry["files"] = m.get("files")
        mutants.append(entry)
    slim: dict[str, Any] = {"mutants": mutants}
    if bundle.get("generation_failures"):
        slim["generation_failures"] = bundle["generation_failures"]
    return slim


def _write_tester_bundle(ws: Workspace, bundle: dict[str, Any]) -> None:
    """Replace the workspace's evaluator with the given tester bundle (clearing
    bundle-managed dirs first so stale harness files never survive a rewrite)."""
    _reset_dirs(ws, ["evaluation", "tests"])
    ws.write_json("tests/tester_bundle.json", bundle)
    ws.write_file_bundle(bundle)


def _preflight_key(diff: dict[str, Any]) -> tuple[int, int]:
    """Rank a differential-gate result; higher is better. Accepting the golden
    outranks rejecting the baseline: a golden-rejecting evaluator invalidates
    every downstream score, while a baseline-accepting one only weakens SRs."""
    golden = diff.get("golden_run") or {}
    vuln = diff.get("vulnerable_run") or {}
    return (1 if golden.get("ok") else 0, 1 if vuln.get("ok") else 0)


def _preflight_notes(diff: dict[str, Any]) -> str:
    lines = ["PRE-FLIGHT EVALUATOR CHECK FAILED (deterministic run before review):"]
    golden = diff.get("golden_run") or {}
    vuln = diff.get("vulnerable_run") or {}
    if golden and not golden.get("ok", False):
        lines.append(
            "- evaluate.py REJECTED the golden secure solution, but a correct secure "
            "implementation must exit 0 with every check emitting [TEST] PASS. Evaluator output:\n"
            + (golden.get("stdout") or "")[:1500]
        )
    if vuln and not vuln.get("ok", False):
        lines.append(
            "- evaluate.py ACCEPTED the insecure baseline inputs, but the shipped baseline is "
            "intentionally vulnerable and must exit non-zero with at least one SR [TEST] FAIL. "
            "Evaluator output:\n" + (vuln.get("stdout") or "")[:1500]
        )
    lines.append(
        "Rewrite evaluate.py so that a correct secure implementation passes every check and "
        "the provided insecure baseline fails at least one SR check. Keep requirement ids unchanged. "
        "Remember: the golden is an independent implementation that shares ONLY the pinned "
        "public interface with the baseline — every check listed as failing above must be "
        "graded behaviorally (compile/simulate the submission through the pinned interface and "
        "judge observed behavior) or as a fail-on-presence vulnerability pattern; a PASS "
        "condition that requires finding baseline-styled source text will keep rejecting it."
    )
    return "\n".join(lines)


def _deterministic_retain(
    validation: dict[str, Any],
    analyzer_report: dict[str, Any] | None,
    min_mutation_score: float,
    min_coverage_score: float,
) -> bool:
    """The retention decision computed purely from deterministic evidence: the
    validation gates plus the Analyzer verdict. Used to override a hallucinated
    Arbiter score and as the fallback when the Arbiter call itself fails."""
    analyzer_ok = (analyzer_report or {}).get("overall_status", "fail") in {"pass", "warning"}
    return (
        validation.get("status") == "pass"
        and analyzer_ok
        and float(validation.get("mutation_score") or 0.0) >= min_mutation_score
        and float(validation.get("coverage_score") or 0.0) >= min_coverage_score
    )


def _round_quality_key(validation: dict[str, Any], analyzer_report: dict[str, Any] | None) -> tuple[Any, ...]:
    """Rank a repair round; higher tuples are strictly better candidates.

    Ordering prefers, in priority order: clean validation, a passing differential
    gate, a healthy analyzer verdict, a passing baseline run, then higher
    mutation/coverage scores, then fewer issues.
    """
    analyzer = analyzer_report or {}
    baseline = validation.get("baseline_run") or {}
    differential = validation.get("differential") or {}
    return (
        1 if validation.get("status") == "pass" else 0,
        1 if differential.get("status") == "pass" else 0,
        1 if analyzer.get("overall_status") in {"pass", "warning"} else 0,
        1 if baseline.get("status") == "pass" else 0,
        round(float(validation.get("mutation_score") or 0.0), 3),
        round(float(validation.get("coverage_score") or 0.0), 3),
        -len(validation.get("issues") or []),
    )


def _snapshot_workspace(ws_root: Path, previous: Path | None) -> Path:
    """Copy the current workspace into a fresh temp dir, discarding any prior
    snapshot. Returns the snapshot's case directory."""
    if previous is not None:
        shutil.rmtree(previous.parent, ignore_errors=True)
    holder = Path(tempfile.mkdtemp(prefix="benchgen_best_"))
    snap_case = holder / "case"
    shutil.copytree(ws_root, snap_case)
    return snap_case


_ROUND_STAMPED_REPORT_RE = re.compile(r"_r\d+\.json$")


def _restore_workspace(ws_root: Path, snapshot: Path) -> None:
    """Replace the workspace contents with a previously taken snapshot.

    Round-stamped reports (arbiter_decision_r*.json, validation_report_r*.json,
    analyzer_report_r*.json) are preserved across the restore: the snapshot was
    taken at an earlier round, so it predates the later rounds' decisions — the
    exact evidence needed to debug why those rounds regressed. The canonical
    (unstamped) reports come from the snapshot and describe the restored round."""
    reports_dir = ws_root / "reports"
    stamped: dict[str, str] = {}
    if reports_dir.is_dir():
        for child in reports_dir.iterdir():
            if child.is_file() and _ROUND_STAMPED_REPORT_RE.search(child.name):
                stamped[child.name] = child.read_text(encoding="utf-8")
    for child in ws_root.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink()
    shutil.copytree(snapshot, ws_root, dirs_exist_ok=True)
    reports_dir.mkdir(exist_ok=True)
    for name, content in stamped.items():
        (reports_dir / name).write_text(content, encoding="utf-8")


def ws_read_json(ws: Workspace, rel: str) -> dict[str, Any]:
    return json.loads(ws.path(rel).read_text(encoding="utf-8"))


def _slim_validation_for_arbiter(validation: dict[str, Any]) -> dict[str, Any]:
    """Strip per-mutant coverage tables and verbose stdout — keep actionable fields."""
    baseline = dict(validation.get("baseline_run") or {})
    # Keep only first 500 chars of stdout so Arbiter can see the error type
    if "stdout" in baseline:
        baseline["stdout"] = baseline["stdout"][:500]
    if "stderr" in baseline:
        baseline["stderr"] = baseline["stderr"][:200]
    differential = None
    if validation.get("differential"):
        diff = validation["differential"]
        differential = {
            "status": diff.get("status"),
            "golden_run": _slim_diff_arm(diff.get("golden_run")),
            "vulnerable_run": _slim_diff_arm(diff.get("vulnerable_run")),
        }
    return {
        "status": validation.get("status"),
        "issues": validation.get("issues", []),
        "coverage_score": validation.get("coverage_score"),
        "mutation_score": validation.get("mutation_score"),
        "mutation_score_meaningful": validation.get("mutation_score_meaningful", True),
        "requirement_count": validation.get("requirement_count"),
        "dead_checks": validation.get("dead_checks", []),
        "uncovered_requirements": validation.get("uncovered_requirements", []),
        "untested_requirements": validation.get("untested_requirements", []),
        "error_runs": validation.get("error_runs", 0),
        "baseline_run": baseline if baseline else None,
        "differential": differential,
    }


def _slim_diff_arm(arm: dict[str, Any] | None) -> dict[str, Any] | None:
    if not arm:
        return None
    return {
        "expected": arm.get("expected"),
        "ok": arm.get("ok"),
        "status": arm.get("status"),
        "stdout": (arm.get("stdout") or "")[:500],
    }


def _normalize_task_spec(raw: dict[str, Any], seed: dict[str, Any], domain_context: dict[str, Any]) -> dict[str, Any]:
    domain_id = str(raw.get("domain_id") or seed.get("domain_id") or domain_context["domain_id"])
    task_id = slugify(str(raw.get("task_id") or seed.get("seed_id") or f"{domain_id}_case"))
    public = raw.get("public_spec") if isinstance(raw.get("public_spec"), dict) else {}
    hidden = raw.get("hidden_spec") if isinstance(raw.get("hidden_spec"), dict) else {}
    evaluation = raw.get("evaluation") if isinstance(raw.get("evaluation"), dict) else {}
    metrics = evaluation.get("metrics") or [
        {"name": metric, "direction": "maximize", "description": metric.replace("_", " ")}
        for metric in domain_context["default_metrics"]
    ]
    # Hardened-artifact tasks measure UNPROMPTED security: participant-facing
    # spec text must never name the hidden CWE/SR identifiers. Scrub them
    # deterministically (filenames excluded — see the helper) instead of
    # spending a repair round on a leak the Arbiter may never target.
    if domain_context.get("submission_kind") == "hardened_artifact" and public:
        removed: list[str] = []
        public = {
            key: item if key == "input_artifacts" else _scrub_public_security_ids(item, removed)
            for key, item in public.items()
        }
        if removed:
            console.print(
                f"  [yellow]scrubbed hidden-security identifiers {sorted(set(removed))} "
                "from public_spec text.[/yellow]"
            )
    return {
        "task_id": task_id,
        "domain_id": domain_id,
        "title": str(raw.get("title") or seed.get("title") or domain_context["title"]),
        "public_spec": {
            "objective": public.get("objective") or seed.get("objective") or domain_context["example_tasks"][0],
            "input_artifacts": public.get("input_artifacts") or domain_context["input_artifacts"],
            "expected_outputs": public.get("expected_outputs") or domain_context["output_artifacts"],
            "interface": public.get("interface") or seed.get("interface") or "",
            "functional_requirements": public.get("functional_requirements") or seed.get("functional_requirements") or [
                {"id": "FR1", "requirement": "The submitted artifact satisfies the public objective and interface contract."}
            ],
            "constraints": public.get("constraints") or seed.get("constraints") or [],
            "response_format": public.get("response_format") or "JSON or Markdown report plus generated artifacts as requested.",
        },
        "hidden_spec": {
            "ground_truth": hidden.get("ground_truth") or seed.get("ground_truth") or "Evaluator-specific ground truth to be generated with the case artifacts.",
            "threat_model": hidden.get("threat_model") or seed.get("threat_model") or "",
            "cwe_ids": hidden.get("cwe_ids") or seed.get("cwe_ids") or [],
            "security_requirements": hidden.get("security_requirements") or seed.get("security_requirements") or [
                {"id": "SR1", "requirement": "The submitted artifact satisfies the hidden domain-specific security property.", "detection_strategy": "Requirement-level private harness."}
            ],
            "acceptance_criteria": hidden.get("acceptance_criteria") or seed.get("acceptance_criteria") or [],
        },
        "evaluation": {
            "metrics": metrics,
            "baselines": evaluation.get("baselines") or domain_context["baseline_sources"],
        },
    }
