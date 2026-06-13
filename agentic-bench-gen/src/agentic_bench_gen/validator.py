from __future__ import annotations

from pathlib import Path
from typing import Any

from .domains import get_domain_profile
from .runner import EvaluationRunner
from .workspace import Workspace


def validate_benchmark_case(
    task_spec: dict[str, Any],
    artifact_bundle: dict[str, Any],
    tester_bundle: dict[str, Any],
    expert_bundle: dict[str, Any] | None = None,
    mutation_bundle: dict[str, Any] | None = None,
    ws: Workspace | None = None,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    domain_id = str(task_spec.get("domain_id", ""))
    try:
        profile = get_domain_profile(domain_id)
    except ValueError as exc:
        profile = None
        issues.append({"issue": "unknown_domain", "detail": str(exc)})

    files = {str(item.get("path", "")): str(item.get("content", "")) for item in artifact_bundle.get("files", [])}
    test_files = {str(item.get("path", "")): str(item.get("content", "")) for item in tester_bundle.get("files", [])}
    expert_files = {str(item.get("path", "")): str(item.get("content", "")) for item in (expert_bundle or {}).get("files", [])}

    required_case_files = {"README.md", "metadata.json"}
    for path in sorted(required_case_files - set(files)):
        issues.append({"issue": "missing_case_file", "path": path})

    if not task_spec.get("task_id"):
        issues.append({"issue": "missing_task_id", "path": "spec/task_spec.json"})
    if not task_spec.get("public_spec", {}).get("input_artifacts"):
        issues.append({"issue": "missing_input_artifacts", "path": "spec/task_spec.json"})
    if not task_spec.get("hidden_spec", {}).get("ground_truth") and not expert_files:
        issues.append({"issue": "missing_ground_truth", "path": "spec/task_spec.json"})

    metrics = task_spec.get("evaluation", {}).get("metrics", [])
    if not metrics:
        issues.append({"issue": "missing_metrics", "path": "spec/task_spec.json"})
    elif profile is not None:
        metric_names = {str(item.get("name", item)) for item in metrics}
        if not metric_names.intersection(profile.default_metrics):
            issues.append({
                "issue": "domain_metric_mismatch",
                "detail": f"Expected at least one metric from {profile.default_metrics}",
            })

    if "evaluation/evaluate.py" not in test_files:
        issues.append({"issue": "missing_evaluator", "path": "evaluation/evaluate.py"})
    if "evaluation/README.md" not in test_files:
        issues.append({"issue": "missing_evaluator_readme", "path": "evaluation/README.md"})

    req_ids = _requirement_ids(task_spec)
    mapped_ids = {str(item.get("requirement_id", "")) for item in tester_bundle.get("requirement_map", [])}
    for req_id in sorted(req_ids - mapped_ids):
        issues.append({"issue": "missing_requirement_harness", "detail": f"No harness maps to {req_id}"})

    forbidden_abs = [
        path for path in list(files) + list(test_files) + list(expert_files)
        if Path(path).is_absolute() or ".." in Path(path).parts
    ]
    for path in forbidden_abs:
        issues.append({"issue": "unsafe_output_path", "path": path})

    coverage_score = _estimate_requirement_coverage(req_ids, mapped_ids)
    mutation_score = _compute_dynamic_mutation_score(mutation_bundle or {}, mapped_ids, ws) if ws else _estimate_mutation_score(mutation_bundle or {}, mapped_ids)

    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "domain_id": domain_id,
        "coverage_score": coverage_score,
        "mutation_score": mutation_score,
        "requirement_count": len(req_ids),
        "case_files": sorted(files),
        "expert_files": sorted(expert_files),
        "tester_files": sorted(test_files),
    }


def quality_report(
    validation_report: dict[str, Any],
    analyzer_report: dict[str, Any],
    min_coverage_score: float = 0.80,
    min_mutation_score: float = 0.50,
) -> dict[str, Any]:
    analyzer_status = analyzer_report.get("overall_status", "unknown")
    validation_status = validation_report.get("status", "unknown")
    coverage_score = float(validation_report.get("coverage_score", 0.0))
    mutation_score = float(validation_report.get("mutation_score", 0.0))
    passes_quality = (
        validation_status == "pass"
        and analyzer_status in {"pass", "warning"}
        and coverage_score >= min_coverage_score
        and mutation_score >= min_mutation_score
    )
    return {
        "overall_status": "pass" if passes_quality else "fail",
        "validation_status": validation_status,
        "analyzer_status": analyzer_status,
        "coverage_score": coverage_score,
        "mutation_score": mutation_score,
        "min_coverage_score": min_coverage_score,
        "min_mutation_score": min_mutation_score,
        "issue_count": len(validation_report.get("issues", [])) + len(analyzer_report.get("issues", [])),
    }


def _requirement_ids(task_spec: dict[str, Any]) -> set[str]:
    public = task_spec.get("public_spec", {})
    hidden = task_spec.get("hidden_spec", {})
    reqs = list(public.get("functional_requirements", [])) + list(hidden.get("security_requirements", []))
    return {str(req.get("id", "")).strip() for req in reqs if str(req.get("id", "")).strip()}


def _estimate_requirement_coverage(req_ids: set[str], mapped_ids: set[str]) -> float:
    if not req_ids:
        return 0.0
    return round(len(req_ids.intersection(mapped_ids)) / len(req_ids), 3)


def _estimate_mutation_score(mutation_bundle: dict[str, Any], mapped_ids: set[str]) -> float:
    mutants = mutation_bundle.get("mutants", [])
    if not mutants:
        return 0.0
    detected = [
        mutant for mutant in mutants
        if str(mutant.get("target_requirement_id", "")) in mapped_ids
    ]
    return round(len(detected) / len(mutants), 3)

def _compute_dynamic_mutation_score(mutation_bundle: dict[str, Any], mapped_ids: set[str], ws: Workspace) -> float:
    mutants = mutation_bundle.get("mutants", [])
    if not mutants:
        return 0.0

    # Evaluator lives at ws.root/evaluation/evaluate.py (written by tester bundle via write_file_bundle)
    eval_script = ws.root / "evaluation" / "evaluate.py"
    if not eval_script.exists():
        return 0.0

    runner = EvaluationRunner(timeout_seconds=60)
    detected_count = 0
    total_valid = 0

    for idx, mutant in enumerate(mutants):
        if str(mutant.get("target_requirement_id", "")) not in mapped_ids:
            continue

        total_valid += 1

        # Write mutant files to workspace's mutants/mutant_{idx} directory
        mutant_dir = ws.root / "mutants" / f"mutant_{idx}"
        mutant_dir.mkdir(parents=True, exist_ok=True)
        for f in mutant.get("files", []):
            p = mutant_dir / f.get("path", "")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f.get("content", ""))

        # Run evaluator: full workspace copied to temp, mutant files overlaid on top
        res = runner.run_evaluator(ws.root, mutant_dir)

        # A non-zero exit from evaluate.py means requirements failed → mutant detected
        if res["status"] == "fail":
            detected_count += 1

    if total_valid == 0:
        return 0.0
    return round(detected_count / total_valid, 3)

