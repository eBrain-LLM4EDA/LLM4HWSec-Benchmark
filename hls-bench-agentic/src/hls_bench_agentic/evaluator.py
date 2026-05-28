from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from rich.console import Console

from .agents import AgentConfig, JsonAgent
from .ast_analyzer import analyze_source, score_synthesis_compatibility
from .grading import (
    compute_composite,
    functional_equivalence_from_execution,
    get_difficulty_weight,
    compute_grade,
)
from .llm import OpenRouterLLM
from .orchestrator import load_agents
from .regex_checker import score_security_requirements
from .runner import ToolRunner, parse_execution_config
from .security_verifier import verify as verify_security
from .utils import read_json, read_yaml, write_json
from .workspace import Workspace

console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_source_files(candidate_bundle: dict[str, Any]) -> dict[str, str]:
    """Extract all C/C++ source files from the candidate bundle."""
    src_exts = {".c", ".cpp", ".cxx", ".cc", ".h", ".hpp"}
    return {
        f["path"]: f["content"]
        for f in candidate_bundle.get("files", [])
        if Path(f["path"]).suffix.lower() in src_exts
    }


def _run_static_analysis(
    source_files: dict[str, str],
    task_spec: dict[str, Any],
) -> dict[str, Any]:
    """Run AST analysis + domain security verifier + regex checker on all source files."""

    # AST + synthesis scoring (combine across all files; worst-case violations)
    combined_violations: list[str] = []
    combined_pragmas = []
    combined_loops = []
    combined_functions = []
    combined_variables = []
    combined_source = ""
    analysis_method = "none"

    for filename, src in source_files.items():
        result = analyze_source(src, filename)
        combined_violations.extend(result.synthesis_violations)
        combined_pragmas.extend(result.pragmas)
        combined_loops.extend(result.loops)
        combined_functions.extend(result.functions)
        combined_variables.extend(result.variables)
        combined_source += "\n" + src
        analysis_method = result.analysis_method  # last one (consistent)

    from .ast_analyzer import AnalysisResult
    merged = AnalysisResult(
        functions=combined_functions,
        variables=combined_variables,
        loops=combined_loops,
        pragmas=combined_pragmas,
        synthesis_violations=list(set(combined_violations)),
        source_text=combined_source,
        analysis_method=analysis_method,
    )

    synth_score, synth_reason = score_synthesis_compatibility(merged)

    # Domain-specific security property verification
    verifier_report = verify_security(merged, task_spec)

    # Regex forbidden-pattern check (fast, always available)
    regex_report = score_security_requirements(source_files, task_spec)

    return {
        "analysis_method": analysis_method,
        "synthesis_pass": {
            "score": synth_score,
            "reason": synth_reason,
            "violations": merged.synthesis_violations,
            "pragmas_found": [{"kind": p.kind, "args": p.args} for p in merged.pragmas],
        },
        "security_property_correctness": {
            "domain": verifier_report.domain,
            "score": verifier_report.total_score,
            "property_scores": [
                {
                    "name": ps.name,
                    "score": ps.score,
                    "max_score": ps.max_score,
                    "passed": ps.passed,
                    "evidence": ps.evidence,
                }
                for ps in verifier_report.property_scores
            ],
        },
        "regex_check": regex_report,
    }


def _clamp_score(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return min(max(score, 0.0), 1.0)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def evaluate_target_model(
    *,
    task_dir: str | Path,
    model: str,
    out_dir: str | Path,
    config_path: str | Path,
) -> Path:
    task_dir = Path(task_dir).resolve()
    config_path = Path(config_path).resolve()
    pipeline_cfg = read_yaml(config_path)

    public_spec = read_json(task_dir / "spec" / "public_spec.json")
    hidden_spec = read_json(task_dir / "spec" / "hidden_spec.json")
    task_spec   = read_json(task_dir / "spec" / "task_spec.json")

    base_url = pipeline_cfg.get("openrouter", {}).get("base_url", "https://openrouter.ai/api/v1")
    llm = OpenRouterLLM.from_env(base_url=base_url)

    agents_cfg_path = (config_path.parent.parent / pipeline_cfg["agents_config"]).resolve()
    agents_raw = read_yaml(agents_cfg_path)
    project_root = agents_cfg_path.parent.parent
    cfg_defaults = agents_raw.get("defaults", {})

    # Build target_model agent with caller-supplied model override.
    tm_spec = agents_raw["agents"]["target_model"]
    target_agent = JsonAgent(
        llm,
        AgentConfig(
            name="target_model",
            model=model,
            prompt_path=(project_root / tm_spec["prompt"]).resolve(),
            schema_path=(project_root / tm_spec["schema"]).resolve(),
            temperature=float(tm_spec.get("temperature", cfg_defaults.get("temperature", 0.2))),
            max_tokens=int(tm_spec.get("max_tokens", cfg_defaults.get("max_tokens", 16000))),
        ),
    )

    safe_model = model.replace("/", "__").replace(":", "_")
    out = Workspace(Path(out_dir).resolve() / task_dir.name / safe_model)

    # --- Step 1: generate candidate ---
    console.print(f"[bold]TargetModel ({model}):[/bold] generating candidate for {task_dir.name}")
    candidate_bundle = target_agent.run({"public_spec_json": public_spec})
    out.write_json("candidate/candidate_bundle.json", candidate_bundle)
    out.write_file_bundle(candidate_bundle, base_dir=".")
    out.normalize_hls_implementation(
        candidate_bundle,
        top_function=public_spec.get("top_function"),
    )

    # Copy tests and spec (target sees only public spec during prompting).
    shutil.copytree(task_dir / "tests", out.path("tests"), dirs_exist_ok=True)
    shutil.copytree(task_dir / "spec",  out.path("spec"),  dirs_exist_ok=True)

    # --- Step 2: run tool steps (csim, synth, cosim, rtl_security) ---
    runner = ToolRunner(parse_execution_config(pipeline_cfg))
    execution_results = runner.run_all(out.root)

    # --- Step 3: static analysis (AST + domain verifier + regex) ---
    source_files = _collect_source_files(candidate_bundle)
    console.print(f"[bold]Static Analysis:[/bold] {len(source_files)} source file(s) for {task_dir.name}")
    static_analysis = _run_static_analysis(source_files, task_spec)
    out.write_json("reports/static_analysis.json", static_analysis)

    # --- Step 4: LLM scorer (optional, best-effort) ---
    llm_score_report: dict[str, Any] | None = None
    if "scorer" in agents_raw.get("agents", {}):
        sc_spec = agents_raw["agents"]["scorer"]
        scorer = JsonAgent(
            llm,
            AgentConfig(
                name="scorer",
                model=sc_spec["model"],
                prompt_path=(project_root / sc_spec["prompt"]).resolve(),
                schema_path=(project_root / sc_spec["schema"]).resolve(),
                temperature=float(sc_spec.get("temperature", 0.0)),
                max_tokens=int(sc_spec.get("max_tokens", cfg_defaults.get("max_tokens", 16000))),
            ),
        )
        eval_packet = {
            "task_id":        task_dir.name,
            "model":          model,
            "public_spec":    public_spec,
            "hidden_spec":    hidden_spec,
            "task_spec":      task_spec,
            "candidate_files": candidate_bundle.get("files", []),
            "execution_results": execution_results,
            "static_analysis":   static_analysis,
        }
        console.print(f"[bold]Scorer:[/bold] LLM-based scoring for {task_dir.name}")
        try:
            llm_score_report = scorer.run({"eval_packet_json": eval_packet})
            out.write_json("reports/score_report.json", llm_score_report)
        except Exception as exc:
            console.print(f"[yellow]Scorer failed (using static analysis only): {exc}[/yellow]")

    # --- Step 5: composite score + grade ---
    llm_sec = (
        _clamp_score(llm_score_report["security_score"])
        if llm_score_report and "security_score" in llm_score_report
        else None
    )
    grading = compute_composite(
        synthesis_pass               = static_analysis["synthesis_pass"]["score"],
        security_property_correctness= static_analysis["security_property_correctness"]["score"],
        functional_equivalence       = functional_equivalence_from_execution(execution_results),
        security_completeness        = static_analysis["regex_check"]["overall_regex_score"],
        llm_security_score           = llm_sec,
    )
    grading["difficulty_weight"] = get_difficulty_weight(task_spec)
    grading["weighted_composite"] = round(
        grading["composite_score"] * grading["difficulty_weight"], 4
    )

    summary = {
        "task_id":          task_dir.name,
        "model":            model,
        "execution_results": execution_results,
        "static_analysis":   static_analysis,
        "llm_score_report":  llm_score_report,
        "grading":           grading,
        "note": (
            "target_model saw only spec/public_spec.json; "
            "hidden_spec was not exposed during prompting."
        ),
    }
    out.write_json("reports/evaluation_summary.json", summary)

    console.print(
        f"[green]Evaluation:[/green] {task_dir.name} | "
        f"composite={grading['composite_score']:.2f} "
        f"grade={grading['grade']} "
        f"(difficulty×{grading['difficulty_weight']})"
    )
    console.print(f"[green]Evaluation workspace:[/green] {out.root}")
    return out.root
