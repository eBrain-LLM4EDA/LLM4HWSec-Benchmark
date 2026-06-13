from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)

from .agents import AgentConfig, JsonAgent
from .llm import OpenRouterLLM
from .preflight import preflight_tester_bundle
from .runner import ToolRunner, parse_execution_config
from .utils import read_yaml, write_json
from .workspace import Workspace


console = Console()


def _make_progress() -> Progress:
    """Single-row progress: spinner | description | elapsed time.

    No BarColumn / MofNCompleteColumn — those extra columns were causing
    rich's Live display to print a new frame every refresh cycle (scroll
    mode) because the wide bar forced terminal reflows.  Spinner + text +
    elapsed is all we need to know which step is running and how long it
    has been waiting.
    """
    return Progress(
        SpinnerColumn(finished_text="[green]✓[/green]"),
        TextColumn("{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )


def load_agents(llm: OpenRouterLLM, agents_config_path: str | Path) -> dict[str, JsonAgent]:
    cfg_path = Path(agents_config_path).resolve()
    raw = read_yaml(cfg_path)
    defaults = raw.get("defaults", {})
    agents: dict[str, JsonAgent] = {}
    for name, spec in raw["agents"].items():
        agent_cfg = AgentConfig(
            name=name,
            model=spec["model"],
            prompt_path=(cfg_path.parent.parent / spec["prompt"]).resolve(),
            schema_path=(cfg_path.parent.parent / spec["schema"]).resolve(),
            temperature=float(spec.get("temperature", defaults.get("temperature", 0.1))),
            max_tokens=int(spec.get("max_tokens", defaults.get("max_tokens", 12000))),
        )
        agents[name] = JsonAgent(llm, agent_cfg)
    return agents


def requirement_ids(task_spec: dict[str, Any]) -> list[str]:
    ids = []
    ids.extend(r["id"] for r in task_spec["public_spec"]["functional_requirements"])
    ids.extend(r["id"] for r in task_spec["hidden_spec"]["security_requirements"])
    return ids


def make_analysis_packet(
    task_spec: dict[str, Any],
    expert_bundle: dict[str, Any],
    test_bundle: dict[str, Any],
    execution_results: dict[str, Any],
) -> dict[str, Any]:
    return {
        "task_id": task_spec["task_id"],
        "requirement_ids": requirement_ids(task_spec),
        "task_spec": task_spec,
        "expert_manifest": expert_bundle.get("manifest", []),
        "test_manifest": test_bundle.get("manifest", []),
        "requirement_map": test_bundle.get("requirement_map", []),
        "execution_results": execution_results,
    }


def bundle_file_contents(bundle: dict[str, Any], max_chars_per_file: int = 12000) -> list[dict[str, Any]]:
    files = []
    for file_obj in bundle.get("files", []):
        content = str(file_obj.get("content", ""))
        files.append({
            "path": str(file_obj.get("path", "")),
            "content": content[:max_chars_per_file],
            "truncated": len(content) > max_chars_per_file,
        })
    return files


def failure_signature(execution_results: dict[str, Any]) -> str:
    parts = []
    for step in execution_results.get("steps", []):
        status = step.get("status")
        if status not in {"fail", "timeout"}:
            continue
        stderr = " ".join(str(step.get("stderr", "")).split())[:500]
        stdout = " ".join(str(step.get("stdout", "")).split())[:500]
        parts.append(f"{step.get('name')}:{status}:{step.get('returncode')}:{stderr}:{stdout}")
    return "\n".join(parts)


def compute_simple_quality_report(
    task_spec: dict[str, Any],
    analyzer_report: dict[str, Any],
    mutant_reports: list[dict[str, Any]],
    gates: dict[str, Any],
) -> dict[str, Any]:
    req_results = analyzer_report.get("requirement_results", [])
    statuses = {r["requirement_id"]: r["status"] for r in req_results}
    all_known_pass = all(statuses.get(rid) == "pass" for rid in requirement_ids(task_spec))

    detected = 0
    total = 0
    target_coverage = {}
    for report in mutant_reports:
        for mutant in report.get("mutants", []):
            total += 1
            if mutant.get("detected", False):
                detected += 1
                rid = mutant.get("target_requirement_id", "unknown")
                target_coverage[rid] = target_coverage.get(rid, 0) + 1

    mutation_score = detected / total if total else 0.0
    sec_reqs = [r["id"] for r in task_spec["hidden_spec"]["security_requirements"]]
    one_per_sec = all(target_coverage.get(rid, 0) > 0 for rid in sec_reqs) if sec_reqs else False

    retained = True
    if gates.get("require_secure_reference_pass", True) and not all_known_pass:
        retained = False
    if mutation_score < float(gates.get("min_security_mutation_score", 0.60)):
        retained = False
    if gates.get("require_one_mutant_detected_per_security_requirement", True) and not one_per_sec:
        retained = False

    return {
        "task_id": task_spec["task_id"],
        "retained": retained,
        "secure_reference_all_requirements_pass": all_known_pass,
        "security_mutation_score": mutation_score,
        "mutants_detected": detected,
        "mutants_total": total,
        "one_mutant_detected_per_security_requirement": one_per_sec,
        "notes": [
            "Coverage gates require tool-specific parsers; this scaffold records placeholders unless reports are supplied.",
            "If execution.allow_execution is false, retained is expected to be false because checks are not run.",
        ],
    }


class HLSBenchmarkOrchestrator:
    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path).resolve()
        self.pipeline_config = read_yaml(self.config_path)
        openrouter_config = self.pipeline_config.get("openrouter", {})
        base_url = openrouter_config.get("base_url", "https://openrouter.ai/api/v1")
        timeout_seconds = float(openrouter_config.get("timeout_seconds", 120))
        max_retries = int(openrouter_config.get("max_retries", 0))
        self.llm = OpenRouterLLM.from_env(
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        agents_config = (self.config_path.parent.parent / self.pipeline_config["agents_config"]).resolve()
        self.agents = load_agents(self.llm, agents_config)
        self.runner = ToolRunner(parse_execution_config(self.pipeline_config))

    def _clear_bundle_files(self, ws: Workspace, bundle: dict[str, Any], base_dir: str = ".") -> None:
        for file_obj in bundle.get("files", []):
            path = ws.path(Path(base_dir) / file_obj["path"])
            if path.is_file():
                path.unlink()

    def _preflight_execution_results(self, ws: Workspace, report: dict[str, Any]) -> dict[str, Any]:
        detail = json.dumps(report.get("issues", []), indent=2, sort_keys=True)
        results = {
            "allow_execution": self.runner.config.allow_execution,
            "workspace": str(ws.root),
            "steps": [
                {
                    "name": "tester_preflight",
                    "command": "internal tester bundle preflight",
                    "status": "fail",
                    "required": True,
                    "stdout": "",
                    "stderr": detail,
                    "returncode": 1,
                    "duration_seconds": 0.0,
                }
            ],
        }
        write_json(ws.path("reports/execution_results.json"), results)
        return results

    def _run_tools_analyzer_arbiter(
        self,
        *,
        progress: Progress,
        task_id: str,
        task_spec: dict[str, Any],
        expert_bundle: dict[str, Any],
        test_bundle: dict[str, Any],
        ws: Workspace,
        step_factory,
        done_factory,
        fail_factory,
        label_suffix: str = "",
        tester_preflight: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        suffix = f" {label_suffix}" if label_suffix else ""

        if tester_preflight and tester_preflight.get("status") != "pass":
            tid = step_factory(f"Tester preflight → {task_id}{suffix}")
            execution_results = self._preflight_execution_results(ws, tester_preflight)
            done_factory(tid, f"Tester preflight → {task_id}{suffix}")
        else:
            tid = step_factory(f"Tool steps → {task_id}{suffix}")
            execution_results = self.runner.run_all(ws.root)
            done_factory(tid, f"Tool steps → {task_id}{suffix}")

        analysis_packet = make_analysis_packet(task_spec, expert_bundle, test_bundle, execution_results)
        ws.write_json("reports/analysis_packet.json", analysis_packet)

        tid = step_factory(f"Security Analyzer → {task_id}{suffix}")
        try:
            analyzer_report = self.agents["security_analyzer"].run({
                "analysis_packet_json": analysis_packet
            })
        except Exception as exc:
            fail_factory(tid, f"Security Analyzer → {task_id}{suffix}", exc)
            raise
        ws.write_json("reports/analyzer_report.json", analyzer_report)
        done_factory(tid, f"Security Analyzer → {task_id}{suffix}")

        arbiter_packet = {
            "task_spec": task_spec,
            "expert_manifest": expert_bundle.get("manifest", []),
            "test_manifest": test_bundle.get("manifest", []),
            "execution_results": execution_results,
            "analyzer_report": analyzer_report,
        }
        tid = step_factory(f"Arbiter → {task_id}{suffix}")
        try:
            arbiter_decision = self.agents["arbiter"].run({
                "arbiter_packet_json": arbiter_packet
            })
        except Exception as exc:
            fail_factory(tid, f"Arbiter → {task_id}{suffix}", exc)
            raise
        ws.write_json("reports/arbiter_decision.json", arbiter_decision)
        done_factory(tid, f"Arbiter → {task_id}{suffix}")

        return execution_results, analyzer_report, arbiter_decision

    def generate(self, seed_path: str | Path, out_dir: str | Path) -> list[Path]:
        seeds = read_yaml(seed_path)
        out_root = Path(out_dir).resolve()
        out_root.mkdir(parents=True, exist_ok=True)
        generated: list[Path] = []

        n = len(seeds)
        console.print(f"[bold]Generating {n} task(s) from {Path(seed_path).name}[/bold]")

        with _make_progress() as progress:

            def _step(label: str) -> TaskID:
                """Register a new in-progress step (indeterminate spinner)."""
                return progress.add_task(f"  {label}", total=None)

            def _done(tid: TaskID, label: str) -> None:
                """Mark a step complete — spinner switches to ✓."""
                progress.update(tid, description=f"  [green]{label}[/green]", total=1, completed=1)

            def _fail(tid: TaskID, label: str, exc: Exception) -> None:
                """Mark a step failed with the error message visible."""
                short = str(exc)[:120]
                progress.update(
                    tid,
                    description=f"  [red]✗ {label}[/red]  [dim red]{short}[/dim red]",
                    total=1,
                    completed=1,
                )

            for seed_idx, seed in enumerate(seeds, start=1):
                seed_id = seed.get("seed_id", f"seed-{seed_idx}")
                seed_yaml = json.dumps(seed, indent=2, sort_keys=True)

                console.rule(
                    f"[bold cyan]Task {seed_idx}/{n}: {seed_id}[/bold cyan]",
                    style="cyan",
                )

                # ── Architect ──────────────────────────────────────────────
                tid = _step(f"Architect → {seed_id}")
                try:
                    task_spec = self.agents["architect"].run({"seed_yaml": seed_yaml})
                except Exception as exc:
                    _fail(tid, f"Architect → {seed_id}", exc)
                    raise
                task_id = task_spec["task_id"]
                ws = Workspace(out_root / task_id)
                ws.write_json("spec/task_spec.json", task_spec)
                ws.write_json("spec/public_spec.json", task_spec["public_spec"])
                ws.write_json("spec/hidden_spec.json", task_spec["hidden_spec"])
                _done(tid, f"Architect → {task_id}")

                # ── Expert ─────────────────────────────────────────────────
                tid = _step(f"Expert → {task_id}")
                try:
                    expert_bundle = self.agents["expert"].run({"task_spec_json": task_spec})
                except Exception as exc:
                    _fail(tid, f"Expert → {task_id}", exc)
                    raise
                ws.write_json("expert/expert_bundle.json", expert_bundle)
                ws.write_file_bundle(expert_bundle, base_dir="expert")
                _done(tid, f"Expert → {task_id}")

                # ── Tester ─────────────────────────────────────────────────
                tid = _step(f"Tester → {task_id}  [dim](waiting for LLM…)[/dim]")
                try:
                    test_bundle = self.agents["tester"].run({"task_spec_json": task_spec})
                except Exception as exc:
                    _fail(tid, f"Tester → {task_id}", exc)
                    raise
                ws.write_json("tests/test_bundle.json", test_bundle)
                ws.write_file_bundle(expert_bundle, base_dir=".")
                ws.write_file_bundle(test_bundle, base_dir=".")
                tester_preflight = preflight_tester_bundle(ws, test_bundle)
                _done(tid, f"Tester → {task_id}")

                execution_results, analyzer_report, arbiter_decision = self._run_tools_analyzer_arbiter(
                    progress=progress,
                    task_id=task_id,
                    task_spec=task_spec,
                    expert_bundle=expert_bundle,
                    test_bundle=test_bundle,
                    ws=ws,
                    step_factory=_step,
                    done_factory=_done,
                    fail_factory=_fail,
                    tester_preflight=tester_preflight,
                )

                repair_history: list[dict[str, Any]] = []
                seen_failure_signatures = {failure_signature(execution_results)}
                max_repair_rounds = int(self.pipeline_config["pipeline"].get("max_repair_rounds", 0))
                for repair_round in range(1, max_repair_rounds + 1):
                    if arbiter_decision.get("retain_task", False):
                        break

                    artifact = arbiter_decision.get("artifact_to_revise", "none")
                    repair_agent = "tester" if artifact == "tool_config" else artifact
                    if repair_agent not in {"tester", "expert"}:
                        repair_history.append({
                            "round": repair_round,
                            "artifact": artifact,
                            "status": "not_repaired",
                            "reason": "Automatic repair is currently implemented for tester, tool_config, and expert artifacts only.",
                            "arbiter_decision": arbiter_decision,
                        })
                        break

                    triggering_decision = arbiter_decision
                    repair_context = {
                        "repair_round": repair_round,
                        "artifact_to_revise": artifact,
                        "repair_agent": repair_agent,
                        "arbiter_decision": triggering_decision,
                        "analyzer_report": analyzer_report,
                        "execution_results": execution_results,
                        "previous_expert_manifest": expert_bundle.get("manifest", []),
                        "previous_test_manifest": test_bundle.get("manifest", []),
                        "previous_requirement_map": test_bundle.get("requirement_map", []),
                        "previous_expert_files": bundle_file_contents(expert_bundle),
                        "previous_test_files": bundle_file_contents(test_bundle),
                        "tester_preflight_report": tester_preflight,
                    }

                    if repair_agent == "tester":
                        tid = _step(f"Repair Tester r{repair_round} → {task_id}  [dim](waiting for LLM…)[/dim]")
                        try:
                            self._clear_bundle_files(ws, test_bundle, base_dir=".")
                            test_bundle = self.agents["tester"].run({
                                "task_spec_json": task_spec,
                                "repair_context_json": repair_context,
                            })
                        except Exception as exc:
                            _fail(tid, f"Repair Tester r{repair_round} → {task_id}", exc)
                            raise
                        ws.write_json("tests/test_bundle.json", test_bundle)
                        ws.write_file_bundle(test_bundle, base_dir=".")
                        tester_preflight = preflight_tester_bundle(ws, test_bundle)
                        _done(tid, f"Repair Tester r{repair_round} → {task_id}")

                    elif repair_agent == "expert":
                        tid = _step(f"Repair Expert r{repair_round} → {task_id}  [dim](waiting for LLM…)[/dim]")
                        try:
                            self._clear_bundle_files(ws, expert_bundle, base_dir=".")
                            self._clear_bundle_files(ws, expert_bundle, base_dir="expert")
                            expert_bundle = self.agents["expert"].run({
                                "task_spec_json": task_spec,
                                "repair_context_json": repair_context,
                            })
                        except Exception as exc:
                            _fail(tid, f"Repair Expert r{repair_round} → {task_id}", exc)
                            raise
                        ws.write_json("expert/expert_bundle.json", expert_bundle)
                        ws.write_file_bundle(expert_bundle, base_dir="expert")
                        ws.write_file_bundle(expert_bundle, base_dir=".")
                        tester_preflight = preflight_tester_bundle(ws, test_bundle)
                        _done(tid, f"Repair Expert r{repair_round} → {task_id}")

                    execution_results, analyzer_report, arbiter_decision = self._run_tools_analyzer_arbiter(
                        progress=progress,
                        task_id=task_id,
                        task_spec=task_spec,
                        expert_bundle=expert_bundle,
                        test_bundle=test_bundle,
                        ws=ws,
                        step_factory=_step,
                        done_factory=_done,
                        fail_factory=_fail,
                        label_suffix=f"(repair r{repair_round})",
                        tester_preflight=tester_preflight,
                    )
                    sig = failure_signature(execution_results)
                    repeated_failure = bool(sig and sig in seen_failure_signatures)
                    seen_failure_signatures.add(sig)
                    repair_history.append({
                        "round": repair_round,
                        "artifact": artifact,
                        "repair_agent": repair_agent,
                        "status": "retained" if arbiter_decision.get("retain_task", False)
                        else "repeated_failure_stopped" if repeated_failure
                        else "needs_more_repair",
                        "triggering_decision": triggering_decision,
                        "arbiter_decision": arbiter_decision,
                        "failure_signature": sig,
                    })
                    ws.write_json("reports/repair_history.json", {
                        "max_repair_rounds": max_repair_rounds,
                        "repairs": repair_history,
                        "final_retain_task": bool(arbiter_decision.get("retain_task", False)),
                    })
                    if repeated_failure and not arbiter_decision.get("retain_task", False):
                        break

                ws.write_json("reports/repair_history.json", {
                    "max_repair_rounds": max_repair_rounds,
                    "repairs": repair_history,
                    "final_retain_task": bool(arbiter_decision.get("retain_task", False)),
                })

                # ── Mutator ────────────────────────────────────────────────
                mutant_reports: list[dict[str, Any]] = []
                if self.pipeline_config["pipeline"].get("generate_mutants", True):
                    tid = _step(f"Mutator → {task_id}")
                    try:
                        mutation_bundle = self.agents["mutator"].run({
                            "task_spec_json": task_spec,
                            "expert_bundle_json": expert_bundle,
                        })
                    except Exception as exc:
                        _fail(tid, f"Mutator → {task_id}", exc)
                        raise
                    ws.write_json("mutants/mutation_bundle.json", mutation_bundle)
                    _done(tid, f"Mutator → {task_id}")

                    max_mutants = int(self.pipeline_config["pipeline"].get("mutants_per_task", 5))
                    mutants = mutation_bundle.get("mutants", [])[:max_mutants]
                    mutant_tid = progress.add_task(
                        f"  [cyan]Mutants → {task_id}[/cyan]",
                        total=len(mutants),
                    )
                    for mutant in mutants:
                        mutant_id = mutant["mutant_id"]
                        progress.update(
                            mutant_tid,
                            description=f"  [cyan]Mutant {mutant_id}[/cyan]",
                        )
                        mutant_dir = ws.path("mutants") / mutant_id
                        if mutant_dir.exists():
                            shutil.rmtree(mutant_dir)
                        shutil.copytree(ws.root, mutant_dir, ignore=shutil.ignore_patterns("mutants"))
                        mws = Workspace(mutant_dir)
                        mws.write_file_bundle({"files": mutant["files"]}, base_dir=".")
                        m_execution = self.runner.run_all(mws.root)
                        detected = any(
                            step.get("status") in {"fail", "timeout"}
                            for step in m_execution.get("steps", [])
                        )
                        m_report = {
                            "mutants": [{
                                "mutant_id": mutant_id,
                                "target_requirement_id": mutant["target_requirement_id"],
                                "detected": detected,
                                "expected_detection": mutant["expected_detection"],
                            }],
                            "execution_results": m_execution,
                        }
                        write_json(mutant_dir / "reports" / "mutant_report.json", m_report)
                        mutant_reports.append(m_report)
                        progress.advance(mutant_tid)

                # ── Quality report ─────────────────────────────────────────
                quality = compute_simple_quality_report(
                    task_spec,
                    analyzer_report,
                    mutant_reports,
                    self.pipeline_config.get("quality_gates", {}),
                )
                ws.write_json("reports/quality_report.json", quality)
                generated.append(ws.root)
                console.print(f"[green bold]✓ Task {seed_idx}/{n} complete:[/green bold] {ws.root}")

        return generated
