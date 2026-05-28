from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from rich.console import Console

from .agents import AgentConfig, JsonAgent
from .ast_analyzer import analyze_source, score_synthesis_compatibility
from .grading import compute_grade, get_difficulty_weight
from .llm import OpenRouterLLM
from .runner import ToolRunner, parse_execution_config
from .security_verifier import verify
from .utils import read_yaml, write_json
from .workspace import Workspace

console = Console()


# ---------------------------------------------------------------------------
# Agent loader
# ---------------------------------------------------------------------------

def load_agents(llm: OpenRouterLLM, agents_cfg_path: Path, defaults: dict[str, Any]) -> dict[str, JsonAgent]:
    raw = read_yaml(agents_cfg_path)
    cfg_defaults = raw.get("defaults", defaults)
    project_root = agents_cfg_path.parent.parent
    agents: dict[str, JsonAgent] = {}
    for name, spec in raw["agents"].items():
        agents[name] = JsonAgent(
            llm,
            AgentConfig(
                name=name,
                model=spec["model"],
                prompt_path=(project_root / spec["prompt"]).resolve(),
                schema_path=(project_root / spec["schema"]).resolve(),
                temperature=float(spec.get("temperature", cfg_defaults.get("temperature", 0.1))),
                max_tokens=int(spec.get("max_tokens", cfg_defaults.get("max_tokens", 16000))),
            ),
        )
    return agents


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _functional_req_ids(task_spec: dict[str, Any]) -> list[str]:
    return [r["id"] for r in task_spec["public_spec"]["functional_requirements"]]


def _security_req_ids(task_spec: dict[str, Any]) -> list[str]:
    return [r["id"] for r in task_spec["hidden_spec"]["security_requirements"]]


def _all_req_ids(task_spec: dict[str, Any]) -> list[str]:
    return _functional_req_ids(task_spec) + _security_req_ids(task_spec)


def _unique_task_workspace(out_root: Path, task_id: str) -> Path:
    """Return a non-existing task workspace path for a generated task id."""
    candidate = out_root / task_id
    if not candidate.exists():
        return candidate

    idx = 1
    while True:
        candidate = out_root / f"{task_id}_gen{idx:03d}"
        if not candidate.exists():
            return candidate
        idx += 1


def _strip_c_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"//.*?$", "", source, flags=re.MULTILINE)


def _expert_source_files(expert_bundle: dict[str, Any]) -> dict[str, str]:
    suffixes = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"}
    return {
        f["path"]: f["content"]
        for f in expert_bundle.get("files", [])
        if Path(f.get("path", "")).suffix.lower() in suffixes
    }


def _make_expert_static_review(
    task_spec: dict[str, Any],
    expert_bundle: dict[str, Any],
) -> dict[str, Any]:
    source_files = _expert_source_files(expert_bundle)
    combined_raw = "\n".join(source_files.values())
    combined_sanitized = _strip_c_comments(combined_raw)

    if not combined_sanitized.strip():
        return {
            "status": "not_run",
            "reason": "No expert C/C++ source files found.",
            "source_files": list(source_files),
        }

    analysis = analyze_source(combined_sanitized)
    verifier_report = verify(analysis, task_spec)
    synthesis_score, synthesis_reason = score_synthesis_compatibility(analysis)

    return {
        "status": "ok",
        "analysis_method": analysis.analysis_method,
        "source_files": list(source_files),
        "comment_stripped": True,
        "synthesis_score": synthesis_score,
        "synthesis_reason": synthesis_reason,
        "domain": verifier_report.domain,
        "domain_score": verifier_report.total_score,
        "properties": [
            {
                "name": p.name,
                "passed": p.passed,
                "score": p.score,
                "max_score": p.max_score,
                "evidence": p.evidence,
            }
            for p in verifier_report.property_scores
        ],
        "loops": [
            {
                "has_fixed_bound": loop.has_fixed_bound,
                "has_early_exit": loop.has_early_exit,
                "body_branch_count": loop.body_branch_count,
            }
            for loop in analysis.loops
        ],
    }


def _make_provenance_hints(
    execution_results: dict[str, Any],
    expert_static_review: dict[str, Any],
) -> list[dict[str, str]]:
    hints: list[dict[str, str]] = []
    steps = execution_results.get("steps", [])
    properties = {
        p.get("name"): p
        for p in expert_static_review.get("properties", [])
    }
    no_early_exit = properties.get("no_early_exit", {}).get("passed")

    for step in steps:
        stdout = step.get("stdout", "")
        stderr = step.get("stderr", "")
        combined = f"{stdout}\n{stderr}"

        if step.get("name") == "rtl_security" and step.get("status") == "fail":
            if "Break statement found" in combined and no_early_exit is True:
                hints.append({
                    "source": "generated_static_checker",
                    "classification": "likely_tester_false_positive",
                    "artifact_to_revise": "tester",
                    "reason": (
                        "The generated rtl_security script reported a break, but independent "
                        "comment-stripped expert analysis found no early exit in loops."
                    ),
                })
            elif "Early return" in combined and no_early_exit is False:
                hints.append({
                    "source": "independent_expert_static_review",
                    "classification": "likely_expert_implementation_bug",
                    "artifact_to_revise": "expert",
                    "reason": "Both generated checks and independent expert analysis indicate early loop exit.",
                })

        if "Undefined symbols" in combined or "undefined reference" in combined:
            hints.append({
                "source": "build_log",
                "classification": "likely_tester_or_tool_config_bug",
                "artifact_to_revise": "tester",
                "reason": (
                    "Compilation reached linking but failed to resolve the top function; "
                    "check generated compile commands, implementation path, and C/C++ linkage."
                ),
            })

    return hints


def _make_analysis_packet(
    task_spec: dict[str, Any],
    expert_bundle: dict[str, Any],
    test_bundle: dict[str, Any],
    execution_results: dict[str, Any],
) -> dict[str, Any]:
    expert_static_review = _make_expert_static_review(task_spec, expert_bundle)
    provenance_hints = _make_provenance_hints(execution_results, expert_static_review)
    return {
        "task_id": task_spec["task_id"],
        "requirement_ids": _all_req_ids(task_spec),
        "task_spec": task_spec,
        "expert_manifest": expert_bundle.get("manifest", []),
        "test_manifest": test_bundle.get("manifest", []),
        "requirement_map": test_bundle.get("requirement_map", []),
        "execution_results": execution_results,
        "expert_static_review": expert_static_review,
        "provenance_hints": provenance_hints,
    }


def _compute_quality_report(
    task_spec: dict[str, Any],
    analyzer_report: dict[str, Any],
    mutant_reports: list[dict[str, Any]],
    gates: dict[str, Any],
) -> dict[str, Any]:
    req_statuses = {r["requirement_id"]: r["status"] for r in analyzer_report.get("requirement_results", [])}
    all_pass = all(req_statuses.get(rid) == "pass" for rid in _all_req_ids(task_spec))

    detected = 0
    total = 0
    per_sec_req: dict[str, int] = {}
    for report in mutant_reports:
        for m in report.get("mutants", []):
            total += 1
            if m.get("detected", False):
                detected += 1
                rid = m.get("target_requirement_id", "unknown")
                per_sec_req[rid] = per_sec_req.get(rid, 0) + 1

    mutation_score = detected / total if total else 0.0
    sec_ids = _security_req_ids(task_spec)
    one_per_sec = all(per_sec_req.get(rid, 0) > 0 for rid in sec_ids) if sec_ids else False

    retained = True
    if gates.get("require_secure_reference_pass", True) and not all_pass:
        retained = False
    if mutation_score < float(gates.get("min_security_mutation_score", 0.60)):
        retained = False
    if gates.get("require_one_mutant_detected_per_security_requirement", True) and not one_per_sec:
        retained = False

    difficulty_weight = get_difficulty_weight(task_spec)
    # Simple generation-time quality proxy (0–1) from mutation score and requirement pass rate.
    gen_quality = (mutation_score * 0.6 + (1.0 if all_pass else 0.0) * 0.4)
    grade = compute_grade(gen_quality)

    return {
        "task_id": task_spec["task_id"],
        "retained": retained,
        "secure_reference_all_requirements_pass": all_pass,
        "security_mutation_score": round(mutation_score, 4),
        "mutants_detected": detected,
        "mutants_total": total,
        "one_mutant_detected_per_security_requirement": one_per_sec,
        "difficulty": task_spec.get("hidden_spec", {}).get("difficulty", "medium"),
        "security_domain": task_spec.get("hidden_spec", {}).get("security_domain", "generic"),
        "difficulty_weight": difficulty_weight,
        "generation_quality_proxy": round(gen_quality, 4),
        "grade": grade,
        "notes": [
            "mutation_score is 0 when execution is disabled (expected).",
            "retained requires execution to be enabled for a meaningful verdict.",
            "generation_quality_proxy is a heuristic; evaluate tasks to get true scores.",
        ],
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class HLSBenchOrchestrator:
    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path).resolve()
        self.pipeline_cfg = read_yaml(self.config_path)
        base_url = self.pipeline_cfg.get("openrouter", {}).get("base_url", "https://openrouter.ai/api/v1")
        self.llm = OpenRouterLLM.from_env(base_url=base_url)
        agents_cfg_path = (self.config_path.parent.parent / self.pipeline_cfg["agents_config"]).resolve()
        self.agents = load_agents(self.llm, agents_cfg_path, self.pipeline_cfg.get("defaults", {}))
        self.runner = ToolRunner(parse_execution_config(self.pipeline_cfg))

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def generate(self, seed_path: str | Path, out_dir: str | Path) -> list[Path]:
        seeds = read_yaml(seed_path)
        out_root = Path(out_dir).resolve()
        out_root.mkdir(parents=True, exist_ok=True)
        generated: list[Path] = []

        expand = self.pipeline_cfg.get("pipeline", {}).get("expand_seeds", True)
        max_repair = int(self.pipeline_cfg.get("pipeline", {}).get("max_repair_rounds", 2))
        gen_mutants = self.pipeline_cfg.get("pipeline", {}).get("generate_mutants", True)
        max_mutants = int(self.pipeline_cfg.get("pipeline", {}).get("mutants_per_task", 5))
        gates = self.pipeline_cfg.get("quality_gates", {})

        for raw_seed in seeds:
            seed_id = raw_seed.get("seed_id", "unknown")
            ideas = self._expand_seed(raw_seed) if expand else [raw_seed]

            for idea in ideas:
                ws_path = self._generate_one(
                    idea=idea,
                    out_root=out_root,
                    max_repair=max_repair,
                    gen_mutants=gen_mutants,
                    max_mutants=max_mutants,
                    gates=gates,
                )
                generated.append(ws_path)
                console.print(f"[green]Task workspace:[/green] {ws_path}")

        return generated

    # ------------------------------------------------------------------
    # Idea expansion
    # ------------------------------------------------------------------

    def _expand_seed(self, raw_seed: dict[str, Any]) -> list[dict[str, Any]]:
        if "idea_generator" not in self.agents:
            return [raw_seed]
        console.print(f"[bold cyan]IdeaGenerator expanding seed:[/bold cyan] {raw_seed.get('seed_id')}")
        try:
            bundle = self.agents["idea_generator"].run({"seed_yaml": json.dumps(raw_seed, indent=2)})
            return bundle.get("ideas", [raw_seed])
        except Exception as exc:
            console.print(f"[yellow]IdeaGenerator failed ({exc}); using raw seed.[/yellow]")
            return [raw_seed]

    # ------------------------------------------------------------------
    # Single task generation with repair loop
    # ------------------------------------------------------------------

    def _generate_one(
        self,
        idea: dict[str, Any],
        out_root: Path,
        max_repair: int,
        gen_mutants: bool,
        max_mutants: int,
        gates: dict[str, Any],
    ) -> Path:
        seed_str = json.dumps(idea, indent=2, sort_keys=True)
        repair_notes = ""
        task_spec: dict[str, Any] | None = None
        expert_bundle: dict[str, Any] | None = None
        test_bundle: dict[str, Any] | None = None
        arbiter_decision: dict[str, Any] | None = None
        ws_path: Path | None = None

        for round_idx in range(max_repair + 1):
            artifact_to_fix = arbiter_decision["artifact_to_revise"] if arbiter_decision else "none"

            # --- Architect (re-run if spec is broken or first round) ---
            if round_idx == 0 or artifact_to_fix == "specification":
                console.print(f"[bold]Architect (round {round_idx}):[/bold] generating spec")
                task_spec = self.agents["architect"].run({"seed_yaml": seed_str, "repair_notes": repair_notes})

            task_id = task_spec["task_id"]
            if ws_path is None:
                ws_path = _unique_task_workspace(out_root, task_id)
                if ws_path.name != task_id:
                    console.print(f"[cyan]Workspace exists for {task_id}; using {ws_path.name}.[/cyan]")
            ws = Workspace(ws_path)
            ws.write_json("spec/task_spec.json", task_spec)
            ws.write_json("spec/public_spec.json", task_spec["public_spec"])
            ws.write_json("spec/hidden_spec.json", task_spec["hidden_spec"])

            # --- Expert (re-run if spec or impl is broken) ---
            if round_idx == 0 or artifact_to_fix in ("specification", "expert"):
                console.print(f"[bold]Expert (round {round_idx}):[/bold] secure reference for {task_id}")
                expert_bundle = self.agents["expert"].run({
                    "task_spec_json": task_spec,
                    "repair_notes": repair_notes,
                })
                ws.write_json("expert/expert_bundle.json", expert_bundle)
                ws.write_file_bundle(expert_bundle, base_dir="expert")
                ws.write_file_bundle(expert_bundle, base_dir=".")
                ws.normalize_hls_implementation(
                    expert_bundle,
                    top_function=task_spec["public_spec"].get("top_function"),
                )

            # --- Tester (re-run if spec, impl, or tests are broken) ---
            if round_idx == 0 or artifact_to_fix in ("specification", "expert", "tester"):
                console.print(f"[bold]Tester (round {round_idx}):[/bold] testbenches for {task_id}")
                test_bundle = self.agents["tester"].run({
                    "task_spec_json": task_spec,
                    "repair_notes": repair_notes,
                })
                ws.write_json("tests/test_bundle.json", test_bundle)
                ws.write_file_bundle(test_bundle, base_dir=".")
                ws.normalize_hls_implementation(
                    expert_bundle,
                    top_function=task_spec["public_spec"].get("top_function"),
                )

            # --- Execute tool steps ---
            console.print(f"[bold]Runner:[/bold] tool steps for {task_id}")
            execution_results = self.runner.run_all(ws.root)

            # --- Security Analyzer ---
            analysis_packet = _make_analysis_packet(task_spec, expert_bundle, test_bundle, execution_results)
            ws.write_json("reports/analysis_packet.json", analysis_packet)
            console.print(f"[bold]SecurityAnalyzer (round {round_idx}):[/bold] {task_id}")
            analyzer_report = self.agents["security_analyzer"].run({"analysis_packet_json": analysis_packet})
            ws.write_json("reports/analyzer_report.json", analyzer_report)

            # --- Arbiter ---
            arbiter_packet = {
                "task_spec": task_spec,
                "expert_manifest": expert_bundle.get("manifest", []),
                "test_manifest": test_bundle.get("manifest", []),
                "execution_results": execution_results,
                "analyzer_report": analyzer_report,
                "expert_static_review": analysis_packet.get("expert_static_review", {}),
                "provenance_hints": analysis_packet.get("provenance_hints", []),
                "repair_round": round_idx,
            }
            console.print(f"[bold]Arbiter (round {round_idx}):[/bold] {task_id}")
            arbiter_decision = self.agents["arbiter"].run({"arbiter_packet_json": arbiter_packet})
            ws.write_json(f"reports/arbiter_decision_r{round_idx}.json", arbiter_decision)

            if arbiter_decision["retain_task"]:
                console.print(f"[green]Arbiter retained task {task_id} at round {round_idx}.[/green]")
                break

            if round_idx < max_repair:
                repair_notes = (
                    f"REPAIR ROUND {round_idx + 1} — "
                    f"root_cause={arbiter_decision['root_cause']} — "
                    f"revise={arbiter_decision['artifact_to_revise']}\n"
                    f"{arbiter_decision['revision_instructions']}"
                )
                console.print(f"[yellow]Arbiter: repair needed ({arbiter_decision['root_cause']}) — round {round_idx + 1}[/yellow]")
            else:
                console.print(f"[red]Arbiter: max repair rounds reached for {task_id}.[/red]")

        # --- Mutants ---
        mutant_reports: list[dict[str, Any]] = []
        if gen_mutants and "mutator" in self.agents:
            console.print(f"[bold]Mutator:[/bold] generating mutants for {task_id}")
            try:
                mutation_bundle = self.agents["mutator"].run({
                    "task_spec_json": task_spec,
                    "expert_bundle_json": expert_bundle,
                })
                ws.write_json("mutants/mutation_bundle.json", mutation_bundle)
                mutant_reports = self._run_mutants(ws, mutation_bundle, max_mutants)
            except Exception as exc:
                console.print(f"[yellow]Mutator failed: {exc}[/yellow]")

        # --- Quality report ---
        quality = _compute_quality_report(task_spec, analyzer_report, mutant_reports, gates)
        ws.write_json("reports/quality_report.json", quality)
        return ws.root

    # ------------------------------------------------------------------
    # Mutant execution
    # ------------------------------------------------------------------

    def _run_mutants(
        self,
        ws: Workspace,
        mutation_bundle: dict[str, Any],
        max_mutants: int,
    ) -> list[dict[str, Any]]:
        mutant_reports: list[dict[str, Any]] = []
        for mutant in mutation_bundle.get("mutants", [])[:max_mutants]:
            mutant_id = mutant["mutant_id"]
            mutant_dir = ws.root / "mutants" / mutant_id
            if mutant_dir.exists():
                shutil.rmtree(mutant_dir)
            shutil.copytree(ws.root, mutant_dir, ignore=shutil.ignore_patterns("mutants"))
            mws = Workspace(mutant_dir)
            mws.write_file_bundle({"files": mutant["files"]}, base_dir=".")
            m_exec = self.runner.run_all(mws.root)
            detected = any(s.get("status") in {"fail", "timeout"} for s in m_exec.get("steps", []))
            report = {
                "mutants": [{
                    "mutant_id": mutant_id,
                    "target_requirement_id": mutant["target_requirement_id"],
                    "detected": detected,
                    "expected_detection": mutant["expected_detection"],
                }],
                "execution_results": m_exec,
            }
            write_json(mutant_dir / "reports" / "mutant_report.json", report)
            mutant_reports.append(report)
        return mutant_reports
