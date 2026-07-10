from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

from .domains import DomainProfile, get_domain_profile, submission_paths
from .runner import EvaluationRunner
from .workspace import Workspace

# Requirement IDs may contain hyphens (e.g. "SR-1") in addition to word chars,
# so match a permissive identifier rather than just [\w].
_REQ_ID = r"[\w-]+"
_FAIL_RE = re.compile(rf"\[TEST\]\s+FAIL:\s+({_REQ_ID})")

# Public-side security leak signals (hardened_artifact domains only).
_LEAK_FILENAME_RE = re.compile(
    r"security[_-]?spec|cwe|threat[_-]?model|security[_-]?requirement", re.IGNORECASE
)
_CWE_ID_RE = re.compile(r"\bCWE[-_]?\d+\b", re.IGNORECASE)
_SR_ID_RE = re.compile(r"\bSR-?\d+\b")
# The task-spec normalizer's fallback FR and similar objective restatements.
_GENERIC_FR_RE = re.compile(
    r"satisfies the (public )?objective|meets the (stated )?objective", re.IGNORECASE
)

# Timing vocabulary a sequential (simulate-graded) interface must use. The
# golden and the reference design are authored independently and compared
# cycle-by-cycle, so an interface that names no output-timing discipline and no
# cycle/latency relationship cannot pin the waveform both must hit — two
# internally-correct designs then differ by a cycle and the golden is rejected.
# This is a FLOOR: it catches a total omission of timing, not a present-but-
# imprecise one (the runtime differential gate + Arbiter handle the subtle
# case), so keep both patterns broad to avoid false-failing a precise interface.
_TIMING_DISCIPLINE_RE = re.compile(
    r"\b(moore|mealy|registered|combinational|clocked|sequential)\b", re.IGNORECASE
)
_TIMING_CYCLE_RE = re.compile(
    r"\b(cycle|cycles|clock edge|rising edge|falling edge|pos[- ]?edge|neg[- ]?edge|latency)\b",
    re.IGNORECASE,
)


def _public_security_leaks(
    profile: DomainProfile | None,
    task_spec: dict[str, Any],
    public_files: dict[str, str],
) -> list[dict[str, str]]:
    """HardSecBench separation gate: for hardened_artifact domains the security
    intent is HIDDEN — the benchmark measures whether a participant produces
    secure code unprompted. A public file or spec entry that names the CWEs or
    SR ids, or ships a security spec / threat model, reconstructs hidden_spec
    and turns the task into security instruction-following. Analysis/detection
    domains are exempt: there the security goal IS the public task and only
    the ground-truth labels are hidden."""
    if profile is None or profile.submission_kind != "hardened_artifact":
        return []
    leaks: list[dict[str, str]] = []
    public_spec = task_spec.get("public_spec", {}) or {}
    for entry in public_spec.get("input_artifacts", []) or []:
        if _LEAK_FILENAME_RE.search(str(entry)):
            leaks.append({
                "issue": "public_security_leak",
                "detail": f"input_artifacts declares security-revealing file {str(entry)!r} — "
                          "security specs, CWE lists and threat models belong in hidden_spec only",
            })
    spec_text = json.dumps(public_spec, sort_keys=True)
    spec_tokens = sorted(set(_CWE_ID_RE.findall(spec_text)) | set(_SR_ID_RE.findall(spec_text)))
    if spec_tokens:
        leaks.append({
            "issue": "public_security_leak",
            "detail": f"public_spec text mentions hidden-security identifiers {spec_tokens[:8]}",
        })
    for path, content in sorted(public_files.items()):
        if _LEAK_FILENAME_RE.search(Path(path).name):
            leaks.append({
                "issue": "public_security_leak",
                "path": path,
                "detail": "participant-facing file whose name reveals the hidden security intent",
            })
            continue
        tokens = sorted(set(_CWE_ID_RE.findall(content)) | set(_SR_ID_RE.findall(content)))
        if tokens:
            leaks.append({
                "issue": "public_security_leak",
                "path": path,
                "detail": f"participant-facing file mentions hidden-security identifiers {tokens[:8]}",
            })
    return leaks


def validate_benchmark_case(
    task_spec: dict[str, Any],
    artifact_bundle: dict[str, Any],
    tester_bundle: dict[str, Any],
    expert_bundle: dict[str, Any] | None = None,
    mutation_bundle: dict[str, Any] | None = None,
    ws: Workspace | None = None,
    runner: EvaluationRunner | None = None,
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
    else:
        _valid_exts = {".cpp", ".c", ".h", ".v", ".sv", ".json", ".md", ".txt", ".tcl", ".yaml", ".py", ".vhd"}
        for entry in task_spec.get("public_spec", {}).get("input_artifacts", []):
            entry_str = str(entry)
            has_ext = any(entry_str.endswith(ext) for ext in _valid_exts)
            if not has_ext or " " in entry_str:
                issues.append({
                    "issue": "input_artifact_not_filename",
                    "detail": f"input_artifacts entry is not a plain filename: {entry_str!r}",
                })
    if not task_spec.get("hidden_spec", {}).get("ground_truth") and not expert_files:
        issues.append({"issue": "missing_ground_truth", "path": "spec/task_spec.json"})

    # The pinned interface is the ONLY reference the independently-generated
    # golden solution and evaluator share (HardSecBench-style isolation). For
    # in-place code submissions a missing/imprecise interface makes agreement
    # between them a matter of luck, so gate on it deterministically.
    if profile is not None and profile.submission_kind == "hardened_artifact":
        interface = str(task_spec.get("public_spec", {}).get("interface", "") or "").strip()
        if not interface:
            issues.append({
                "issue": "missing_interface",
                "detail": "public_spec.interface is empty — the exact entry-point signature must be pinned "
                          "so the Expert's golden and the Tester's harness can agree without communicating",
            })

    # Simulate-graded domains compare the submission to a reference design cycle
    # by cycle; the golden and reference are authored independently from the
    # interface, so it must pin OUTPUT TIMING, not just function. Floor check:
    # the interface must name a timing discipline (Moore/Mealy/registered/...)
    # AND a cycle/latency relationship. A total omission fails the spec gate and
    # routes to a specification repair before a cycle-offset golden_rejected is
    # discovered at runtime a full round later.
    if profile is not None and profile.evaluation_mode == "simulate":
        interface = str(task_spec.get("public_spec", {}).get("interface", "") or "").strip()
        if not interface or not (_TIMING_DISCIPLINE_RE.search(interface)
                                 and _TIMING_CYCLE_RE.search(interface)):
            issues.append({
                "issue": "missing_timing_discipline",
                "detail": "public_spec.interface does not pin sequential timing — for a design graded by "
                          "cycle-accurate simulation it must state the output timing discipline "
                          "(Moore/Mealy) for each output and the exact output/reset/handshake latency in "
                          "clock cycles, so the independently authored reference and golden land on the "
                          "identical waveform (otherwise a one-cycle latency difference fails the case)",
            })

    # Public/hidden separation: nothing participant-facing may reconstruct the
    # hidden security intent (hardened_artifact domains only; see helper).
    issues.extend(_public_security_leaks(profile, task_spec, files))

    # A benchmark whose only FR restates the objective grades functionality on
    # a single tautology; the Architect must pin concrete, machine-checkable
    # FRs. Empty FRs mean the Architect emitted none and the normalizer's
    # generic fallback was injected.
    frs = task_spec.get("public_spec", {}).get("functional_requirements") or []
    fr_texts = [str(fr.get("requirement", "")) for fr in frs if isinstance(fr, dict)]
    if not frs:
        issues.append({
            "issue": "missing_functional_requirements",
            "detail": "public_spec.functional_requirements is empty — supply 2-4 concrete, "
                      "machine-checkable FRs verifiable through the pinned interface",
        })
    elif len(frs) == 1 and any(_GENERIC_FR_RE.search(text) for text in fr_texts):
        issues.append({
            "issue": "generic_functional_requirement",
            "detail": f"the only FR is a generic objective restatement ({fr_texts[0][:90]!r}) — "
                      "replace with 2-4 concrete, machine-checkable FRs (known-answer outputs, "
                      "interface/compile conformance, output format)",
        })

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
    else:
        ev_content = test_files["evaluation/evaluate.py"]
        declared_inputs = set(task_spec.get("public_spec", {}).get("input_artifacts", []))
        for fname in _find_opened_input_files(ev_content):
            if fname not in declared_inputs:
                issues.append({
                    "issue": "evaluator_opens_undeclared_file",
                    "detail": f"evaluate.py opens inputs/{fname} but that file is not in input_artifacts {sorted(declared_inputs)}",
                })
        for skipped_id in re.findall(rf"\[TEST\]\s*SKIP\s*:\s*({_REQ_ID})", ev_content):
            issues.append({
                "issue": "evaluator_skips_requirement",
                "detail": f"evaluate.py emits SKIP for {skipped_id} instead of PASS/FAIL — every requirement must be actively checked",
            })
    if "evaluation/README.md" not in test_files:
        issues.append({"issue": "missing_evaluator_readme", "path": "evaluation/README.md"})

    req_ids = _requirement_ids(task_spec)
    if not tester_bundle.get("requirement_map"):
        issues.append({
            "issue": "missing_requirement_map",
            "detail": "tester_bundle has no requirement_map — coverage cannot be established and every requirement will be reported uncovered",
        })
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
    dms: dict[str, Any] = {}
    differential: dict[str, Any] = {}
    if ws:
        runner = runner or EvaluationRunner(timeout_seconds=60)

        # Differential gate first (grader semantics): the evaluator must ACCEPT
        # the expert golden solution and REJECT the known-insecure baseline
        # input. This deterministically catches buggy/over-strict evaluators
        # (golden fails) and inverted / no-op security checks (baseline passes).
        if "evaluation/evaluate.py" in test_files:
            differential = _compute_differential_validation(task_spec, expert_bundle or {}, ws, runner, profile)
            if differential.get("status") == "skipped":
                differential = {}
        golden = differential.get("golden_run")
        if golden is not None:
            if not golden.get("ok", False):
                issues.append({
                    "issue": "golden_rejected",
                    "detail": "evaluate.py rejects the expert golden solution (PASS expected) — the evaluator is buggy/over-strict or grades the wrong file",
                })
            else:
                # The golden run passes every check, so its stdout must carry a
                # [TEST] marker for every mapped requirement; missing ids mean
                # the requirement_map and the script disagree on requirement
                # naming (e.g. "SR-1" vs "SR1") and coverage stats are bogus.
                missing_markers = sorted(mapped_ids - _parse_marker_ids(golden.get("stdout", "")))
                if missing_markers:
                    issues.append({
                        "issue": "requirement_id_mismatch",
                        "detail": f"evaluate.py never emitted [TEST] PASS/FAIL for {missing_markers} on the golden run — requirement_map ids and the script's marker ids must match exactly",
                    })
        vuln = differential.get("vulnerable_run")
        if vuln is not None and not vuln.get("ok", False):
            issues.append({
                "issue": "vulnerable_accepted",
                "detail": "evaluate.py accepts the known-insecure baseline input (FAIL expected) — security checks are inverted, no-ops, or absent",
            })

        dms = _compute_dynamic_mutation_score(
            mutation_bundle or {}, mapped_ids, ws, runner,
            golden_overlay=_golden_overlay(task_spec, expert_bundle or {}, profile),
            golden_run=golden,
        )
        mutation_score = dms["score"]
        if dms.get("baseline_failed") and not differential:
            _b = dms.get("baseline_run") or {}
            issues.append({
                "issue": "baseline_failed",
                "detail": (
                    f"evaluate.py exited {_b.get('exit_code')} on the un-mutated case, so no mutant "
                    f"result is meaningful. stdout: {(_b.get('stdout') or '')[:400]}"
                ),
            })
        # Raise issues for dead SR checks and uncovered SR requirements
        for check_id in dms.get("dead_checks", []):
            if check_id.startswith("SR"):
                issues.append({
                    "issue": "dead_check",
                    "detail": f"{check_id} never emitted [TEST] FAIL on any mutant — provides no discrimination",
                })
        for req_id in dms.get("uncovered_requirements", []):
            if req_id.startswith("SR"):
                issues.append({
                    "issue": "uncovered_requirement",
                    "detail": f"{req_id} has no mutant that was detected — vulnerability coverage gap",
                })
    else:
        mutation_score = _estimate_mutation_score(mutation_bundle or {}, mapped_ids)

    report: dict[str, Any] = {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "domain_id": domain_id,
        "coverage_score": coverage_score,
        "mutation_score": mutation_score,
        # False when the golden/baseline run or the differential gate failed:
        # every mutant result is then noise (and the orchestrator skips mutant
        # generation entirely on a failed pre-flight), so a 0.0 must be read as
        # "not measurable", not "no discrimination".
        "mutation_score_meaningful": (
            not dms.get("baseline_failed", False)
            and differential.get("status") != "fail"
        ),
        "requirement_count": len(req_ids),
        "case_files": sorted(files),
        "expert_files": sorted(expert_files),
        "tester_files": sorted(test_files),
    }
    if dms.get("baseline_run") is not None:
        report["baseline_run"] = dms["baseline_run"]
    if dms.get("per_requirement_coverage"):
        report["per_requirement_coverage"] = dms["per_requirement_coverage"]
    if "check_activation" in dms:
        report["check_activation"] = dms["check_activation"]
    if dms.get("dead_checks") is not None:
        report["dead_checks"] = dms["dead_checks"]
    if dms.get("uncovered_requirements") is not None:
        report["uncovered_requirements"] = dms["uncovered_requirements"]
    if dms.get("untested_requirements"):
        report["untested_requirements"] = dms["untested_requirements"]
    if dms.get("error_runs"):
        report["error_runs"] = dms["error_runs"]
    if differential.get("status", "skipped") != "skipped":
        report["differential"] = differential
    return report


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


def _strip_comments_and_docstrings(src: str) -> str:
    """Drop # comments and triple-quoted strings so that filenames merely
    *mentioned* in prose are not mistaken for filenames the script opens."""
    src = re.sub(r"(?s)'''.*?'''", "", src)
    src = re.sub(r'(?s)""".*?"""', "", src)
    return re.sub(r"(?m)#.*$", "", src)


def _find_opened_input_files(ev_content: str) -> set[str]:
    """Extract hardcoded filenames that evaluate.py opens from inputs/."""
    ev_content = _strip_comments_and_docstrings(ev_content)
    _ext = r"[\w.\-]+"
    patterns = [
        # open("inputs/foo.cpp") or open('inputs/foo.cpp')
        rf"""open\s*\(\s*['"f]?(?:f?['"'])?inputs/({_ext})""",
        # os.path.join("inputs", "foo.cpp")
        rf"""os\.path\.join\s*\(\s*['"]inputs['"]\s*,\s*['"]({_ext})['"]""",
        # Path("inputs") / "foo.cpp"
        rf"""Path\s*\(\s*['"]inputs['"]\s*\)\s*/\s*['"]({_ext})['"]""",
        # f"inputs/foo.cpp" or 'inputs/foo.cpp' as bare string
        rf"""['"]inputs/({_ext})['"]""",
    ]
    found: set[str] = set()
    for pat in patterns:
        for m in re.finditer(pat, ev_content):
            fname = m.group(1).strip("\"'")
            if "." in fname:
                found.add(fname)
    return found


def _parse_failing_checks(stdout: str) -> set[str]:
    """Extract requirement IDs that emitted [TEST] FAIL from evaluate.py output."""
    return {m.group(1) for m in _FAIL_RE.finditer(stdout) if m.group(1) != "SETUP"}


_MARKER_RE = re.compile(rf"\[TEST\]\s+(?:PASS|FAIL):\s+({_REQ_ID})")


def _parse_marker_ids(stdout: str) -> set[str]:
    """Extract every requirement ID that emitted a [TEST] PASS/FAIL marker."""
    return {m.group(1) for m in _MARKER_RE.finditer(stdout) if m.group(1) != "SETUP"}


def _run_outcome(result: dict[str, Any]) -> str:
    """Classify an evaluator run on a mutant: "detected" (rejected), "undetected"
    (accepted), or "error" (infrastructure/harness failure).

    Error runs are excluded from the mutation score so docker daemon failures,
    evaluator crashes, and harness SETUP failures cannot inflate it — a crash is
    not evidence that the check discriminates."""
    status = result.get("status")
    if status == "pass":
        return "undetected"
    if status in {"error", "timeout"}:
        return "error"
    stdout = result.get("stdout", "") or ""
    if _parse_failing_checks(stdout):
        return "detected"
    if "[TEST] FAIL: SETUP" in stdout:
        return "error"
    if "Traceback (most recent call last)" in (result.get("stderr") or ""):
        return "error"
    return "detected"


def _write_overlay(stage: Path, overlay: dict[str, str]) -> None:
    for rel, content in overlay.items():
        p = stage / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def _compute_dynamic_mutation_score(
    mutation_bundle: dict[str, Any],
    mapped_ids: set[str],
    ws: Workspace,
    runner: EvaluationRunner | None = None,
    golden_overlay: dict[str, str] | None = None,
    golden_run: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run dynamic mutation evaluation and return a metrics dict containing:
    - score: overall mutation detection rate
    - baseline_run: stdout/exit summary for the un-mutated baseline
    - baseline_failed: True when the baseline was rejected (score is meaningless)
    - per_requirement_coverage: per-req targeting and detection counts
    - check_activation: how many mutant runs caused each check to fire
    - dead_checks: targeted requirement IDs whose check never emitted [TEST] FAIL
    - uncovered_requirements: targeted requirement IDs with no detected mutant
    - untested_requirements: mapped requirement IDs no mutant targeted
    - error_runs: mutant runs excluded due to infrastructure/harness errors

    Grader semantics: when a golden overlay exists, every mutant is graded as a
    corrupted *golden* submission — golden code is staged onto the inputs/ paths
    and the mutant's files are applied on top; the evaluator must reject the
    result. The baseline that must pass is therefore the golden run (reused from
    the differential gate when available). Without an overlay (no code inputs),
    mutants overlay the as-shipped workspace, which must itself pass.
    """
    _empty: dict[str, Any] = {
        "score": 0.0,
        "baseline_run": None,
        "baseline_failed": False,
        "per_requirement_coverage": {},
        "check_activation": {},
        "dead_checks": [],
        "uncovered_requirements": [],
        "untested_requirements": [],
        "error_runs": 0,
    }

    mutants = mutation_bundle.get("mutants", [])
    if not mutants:
        return _empty

    eval_script = ws.root / "evaluation" / "evaluate.py"
    if not eval_script.exists():
        return _empty

    # Default to a host runner when none is supplied (unit tests / Docker-less
    # setups); the orchestrator passes a configured, Docker-isolated runner.
    runner = runner or EvaluationRunner(timeout_seconds=60)
    overlay = golden_overlay or {}

    # Pre-check: the baseline (golden submission when an overlay exists, the
    # as-shipped workspace otherwise) must pass before mutant results mean
    # anything. Reuse the differential gate's golden run when supplied.
    if overlay and golden_run is not None:
        baseline_summary: dict[str, Any] = {
            "exit_code": golden_run.get("exit_code"),
            "status": golden_run.get("status"),
            "stdout": (golden_run.get("stdout") or "")[:3000],
            "stderr": (golden_run.get("stderr") or "")[:1000],
        }
    else:
        if overlay:
            with tempfile.TemporaryDirectory(prefix="bench_golden_") as stage_root:
                _write_overlay(Path(stage_root), overlay)
                baseline_result = runner.run_evaluator(ws.root, Path(stage_root))
        else:
            baseline_result = runner.run_evaluator(ws.root)
        baseline_summary = {
            "exit_code": baseline_result.get("returncode"),
            "status": baseline_result.get("status"),
            "stdout": baseline_result.get("stdout", "")[:3000],
            "stderr": baseline_result.get("stderr", "")[:1000],
        }
    if baseline_summary["status"] != "pass":
        return {**_empty, "baseline_run": baseline_summary, "baseline_failed": True}

    # Initialise per-requirement coverage table for every mapped requirement.
    per_req: dict[str, dict[str, Any]] = {
        req_id: {"mutants_targeting": 0, "mutants_detected": 0, "covered": False}
        for req_id in mapped_ids
    }
    check_activation: dict[str, int] = {}

    detected_count = 0
    total_valid = 0
    error_runs = 0

    # Stage mutant files in a throwaway temp dir rather than under ws.root, so the
    # generated case folder stays clean and run_evaluator's full-workspace copytree
    # doesn't re-copy a growing pile of mutant trees on every baseline/mutant run.
    with tempfile.TemporaryDirectory(prefix="bench_mutants_") as stage_root:
        stage = Path(stage_root)
        for idx, mutant in enumerate(mutants):
            target_id = str(mutant.get("target_requirement_id", ""))
            if target_id not in mapped_ids:
                continue

            mutant_dir = stage / f"mutant_{idx}"
            mutant_dir.mkdir(parents=True, exist_ok=True)
            _write_overlay(mutant_dir, overlay)
            for f in mutant.get("files", []):
                p = mutant_dir / f.get("path", "")
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(f.get("content", ""))

            res = runner.run_evaluator(ws.root, mutant_dir)
            outcome = _run_outcome(res)
            if outcome == "error":
                error_runs += 1
                continue

            total_valid += 1
            per_req[target_id]["mutants_targeting"] += 1
            if outcome == "detected":
                detected_count += 1
                per_req[target_id]["mutants_detected"] += 1
                per_req[target_id]["covered"] = True
                for check_id in _parse_failing_checks(res.get("stdout", "")):
                    check_activation[check_id] = check_activation.get(check_id, 0) + 1

    score = round(detected_count / total_valid, 3) if total_valid > 0 else 0.0

    # Only requirements that actually had a targeting mutant can be judged: an
    # SR nobody mutated is "untested", not "dead" — flagging it would punish
    # the mutant sampling, not the check.
    targeted = {req_id for req_id, cov in per_req.items() if cov["mutants_targeting"] > 0}
    dead_checks = sorted(req_id for req_id in targeted if check_activation.get(req_id, 0) == 0)
    uncovered = sorted(req_id for req_id in targeted if not per_req[req_id]["covered"])
    untested = sorted(mapped_ids - targeted)

    return {
        "score": score,
        "baseline_run": baseline_summary,
        "baseline_failed": False,
        "per_requirement_coverage": per_req,
        "check_activation": check_activation,
        "dead_checks": dead_checks,
        "uncovered_requirements": uncovered,
        "untested_requirements": untested,
        "error_runs": error_runs,
    }


_CODE_EXTS = {".cpp", ".cc", ".c", ".h", ".hpp", ".v", ".sv", ".vhd", ".py", ".tcl"}


def _match_golden_file(target_name: str, golden_files: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the golden/expert file that answers the submission target
    `target_name`: exact filename, then same stem, then same extension — the
    Expert is told to mirror the submission filename, so exact should hit; the
    fallbacks guard against a stray extra file (e.g. a testbench)."""
    stem, ext = Path(target_name).stem, Path(target_name).suffix
    match = next((f for f in golden_files if Path(str(f.get("path", ""))).name == target_name), None)
    if match is None:
        match = next((f for f in golden_files if Path(str(f.get("path", ""))).stem == stem), None)
    if match is None:
        match = next((f for f in golden_files if Path(str(f.get("path", ""))).suffix == ext), None)
    return match


def _golden_overlay(
    task_spec: dict[str, Any],
    expert_bundle: dict[str, Any],
    profile: DomainProfile | None = None,
) -> dict[str, str]:
    """Map the expert's golden solution onto the submission path(s) the evaluator
    grades, producing a "correct submission" overlay.

    The grading target depends on the domain's submission contract: for
    hardened_artifact domains it is the code input(s) under inputs/; for
    analysis_report domains it is the answer file(s) under submission/. Both
    resolve through domains.submission_paths(), the single source of truth the
    prompts also use, so evaluate.py and this overlay can never disagree.
    """
    input_artifacts = [str(x) for x in task_spec.get("public_spec", {}).get("input_artifacts", [])]
    if profile is None:
        try:
            profile = get_domain_profile(str(task_spec.get("domain_id", "")))
        except ValueError:
            return {}
    targets = submission_paths(profile, input_artifacts)
    if not targets:
        return {}

    # Prefer golden files under a golden/ directory; fall back to any expert file.
    expert_files = expert_bundle.get("files", [])
    golden_files = [
        f for f in expert_files
        if "golden" in Path(str(f.get("path", ""))).parts
    ] or expert_files

    overlay: dict[str, str] = {}
    for target in targets:
        match = _match_golden_file(Path(target).name, golden_files)
        if match is not None:
            overlay[target] = str(match.get("content", ""))
    return overlay


def _summarize_diff_run(result: dict[str, Any], expected_pass: bool, ok: bool) -> dict[str, Any]:
    return {
        "expected": "pass" if expected_pass else "fail",
        "ok": ok,
        "status": result.get("status"),
        "exit_code": result.get("returncode"),
        "stdout": result.get("stdout", "")[:3000],
        "stderr": result.get("stderr", "")[:1000],
    }


def _compute_differential_validation(
    task_spec: dict[str, Any],
    expert_bundle: dict[str, Any],
    ws: Workspace,
    runner: EvaluationRunner | None = None,
    profile: DomainProfile | None = None,
) -> dict[str, Any]:
    """Run the two-sided differential gate (grader semantics):

    - golden_run:     evaluator on the expert golden submission -> must PASS.
    - vulnerable_run: evaluator on the shipped baseline submission -> must FAIL.

    The golden submission is the expert answer overlaid onto the domain's
    submission path(s) (inputs/ for hardened_artifact domains, submission/ for
    analysis_report domains). The vulnerable submission is the workspace as
    shipped — the insecure baseline code, or the naive baseline answer file.

    Returns a dict with status pass|fail|skipped and per-arm summaries. The gate
    degrades to skipped when no golden overlay can be identified, so it never
    makes a case worse than before.
    """
    runner = runner or EvaluationRunner(timeout_seconds=60)
    overlay = _golden_overlay(task_spec, expert_bundle, profile)
    if not overlay:
        return {"status": "skipped", "golden_run": None, "vulnerable_run": None}

    # Golden submission: overlay the golden answer onto the graded path(s), expect PASS.
    with tempfile.TemporaryDirectory(prefix="bench_golden_") as stage_root:
        stage = Path(stage_root)
        _write_overlay(stage, overlay)
        golden_result = runner.run_evaluator(ws.root, stage)
    golden_ok = golden_result.get("status") == "pass"

    # Vulnerable submission: the workspace as-is is the insecure/naive baseline,
    # which a correct evaluator must reject. A clean "fail" is required — a
    # timeout or infrastructure error is not evidence of rejection.
    vuln_result = runner.run_evaluator(ws.root)
    vuln_ok = vuln_result.get("status") == "fail"

    return {
        "status": "pass" if (golden_ok and vuln_ok) else "fail",
        "golden_run": _summarize_diff_run(golden_result, expected_pass=True, ok=golden_ok),
        "vulnerable_run": _summarize_diff_run(vuln_result, expected_pass=False, ok=vuln_ok),
    }
