#!/usr/bin/env python3
"""
Evaluation Script for HLS Security-Aware Code Generation Benchmark (Arda)

Supports two modes:
    --mode regex     (default) Original regex-based scoring (no dependencies)
    --mode simulate  AST analysis + C-simulation + security verification

Usage:
    python run_evaluation.py --input llm_outputs/ --reference examples/ --mode simulate

Requirements for --mode simulate:
    pip install libclang
    apt install clang libclang-dev g++
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Try importing simulation backends (optional)
# ---------------------------------------------------------------------------

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    sys.path.insert(0, EVAL_DIR)
    from analysis.ast_analyzer import ASTAnalyzer
    from analysis.security_verifier import SecurityVerifier
    from sim_backend.compile_and_run import run_testbench as _run_testbench
    HAS_SIM_BACKEND = True
except ImportError as e:
    HAS_SIM_BACKEND = False
    _SIM_IMPORT_ERROR = str(e)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DimensionScores:
    detection_rate: float = 0.0
    flow_correctness: float = 0.0
    synthesis_pass: float = 0.0
    functional_equivalence: float = 0.0
    security_completeness: float = 0.0

    def composite(self) -> float:
        return (
            0.25 * self.detection_rate
            + 0.25 * self.flow_correctness
            + 0.20 * self.synthesis_pass
            + 0.15 * self.functional_equivalence
            + 0.15 * self.security_completeness
        )

    def grade(self) -> str:
        c = self.composite()
        if c >= 0.90: return "A"
        if c >= 0.75: return "B"
        if c >= 0.60: return "C"
        if c >= 0.40: return "D"
        return "F"


@dataclass
class ExampleResult:
    example_id: str
    scores: DimensionScores
    notes: List[str] = field(default_factory=list)
    property_details: List[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_rubric(rubric_path: str) -> dict:
    with open(rubric_path, "r") as f:
        return json.load(f)

def load_metadata(example_dir: str) -> dict:
    with open(os.path.join(example_dir, "metadata.json"), "r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Dimension 1: Vulnerability Detection (shared by both modes)
# ---------------------------------------------------------------------------

def count_reference_vulnerabilities(ref_dir: str) -> Tuple[int, List[str]]:
    vr_path = os.path.join(ref_dir, "vulnerability_report.md")
    if not os.path.exists(vr_path):
        return 0, []
    with open(vr_path, "r") as f:
        content = f.read()
    vulns = re.findall(r"### V\d+:.*?\(CWE-(\d+)\)", content)
    return len(vulns), [f"CWE-{c}" for c in vulns]


def score_detection(submission_vr_path: str, ref_dir: str, metadata: dict) -> Tuple[float, List[str]]:
    notes = []
    expected_count = metadata.get("expected_vulnerabilities", 0)
    _, ref_cwes = count_reference_vulnerabilities(ref_dir)

    if not os.path.exists(submission_vr_path):
        return 0.0, ["No vulnerability report submitted"]

    with open(submission_vr_path, "r") as f:
        content = f.read()

    reported_cwes = [f"CWE-{c}" for c in re.findall(r"CWE-(\d+)", content)]
    true_positives = len(set(reported_cwes) & set(ref_cwes))
    false_positives = len(set(reported_cwes) - set(ref_cwes))

    if expected_count == 0:
        return 1.0, notes

    detection_rate = min(true_positives / expected_count, 1.0)
    total_reported = len(reported_cwes)
    cwe_accuracy = true_positives / total_reported if total_reported > 0 else 0.0

    score = max(detection_rate * cwe_accuracy - (false_positives * 0.05), 0.0)

    if true_positives < expected_count:
        notes.append(f"Missed {expected_count - true_positives} of {expected_count} vulnerabilities")
    if false_positives > 0:
        notes.append(f"{false_positives} false positive(s)")

    return round(score, 3), notes


# ===================================================================
# MODE: SIMULATE — AST + C-Sim + Security Verification
# ===================================================================

def evaluate_example_simulate(
    submission_dir: str,
    reference_dir: str,
    rubric: dict,
) -> ExampleResult:
    """Evaluate using Clang AST analysis, C-simulation, and structural verification."""

    metadata = load_metadata(reference_dir)
    example_id = metadata["id"]
    scores = DimensionScores()
    all_notes = []
    property_details = []

    sub_vr = os.path.join(submission_dir, "vulnerability_report.md")
    sub_code = os.path.join(submission_dir, "secure.cpp")
    insecure_code = os.path.join(reference_dir, "insecure.cpp")
    spec_path = os.path.join(reference_dir, "security_spec.md")
    stubs_dir = os.path.join(EVAL_DIR, "sim_backend", "hls_stubs")
    tb_dir = os.path.join(EVAL_DIR, "testbenches")

    # --- Dim 1: Detection rate (same as regex mode) ---
    det_score, det_notes = score_detection(sub_vr, reference_dir, metadata)
    scores.detection_rate = det_score
    all_notes.extend(det_notes)

    if not os.path.exists(sub_code):
        all_notes.append("No secure code submitted")
        return ExampleResult(example_id=example_id, scores=scores,
                             notes=all_notes)

    # --- Parse AST ---
    try:
        ast = ASTAnalyzer(sub_code, stubs_dir=stubs_dir)
        if ast.parse_errors:
            all_notes.append(f"Parse errors: {'; '.join(ast.parse_errors[:3])}")
    except Exception as e:
        all_notes.append(f"AST analysis failed: {str(e)}")
        # Fall back to defaults
        scores.synthesis_pass = 0.0
        scores.flow_correctness = 0.0
        scores.functional_equivalence = 0.75
        scores.security_completeness = 0.0
        return ExampleResult(example_id=example_id, scores=scores,
                             notes=all_notes)

    # --- Dim 2: Security property correctness (AST-based) ---
    try:
        verifier = SecurityVerifier(ast, metadata)
        scores.flow_correctness = verifier.score()
        property_details = verifier.get_report()

        for prop in property_details:
            if not prop["passed"]:
                all_notes.append(f"Property not met: {prop['description']}")
    except Exception as e:
        all_notes.append(f"Security verification failed: {str(e)}")
        scores.flow_correctness = 0.0

    # --- Dim 3: Synthesis pass (AST-based) ---
    try:
        scores.synthesis_pass = ast.score_synthesis_compatibility()
        for v in ast.get_analysis().synthesis_violations:
            all_notes.append(f"Synthesis issue: {v}")
    except Exception as e:
        all_notes.append(f"Synthesis check failed: {str(e)}")
        scores.synthesis_pass = 0.0

    # --- Dim 4: Functional equivalence (C-simulation) ---
    try:
        func_score, func_notes = _run_testbench(
            example_id, sub_code, insecure_code, tb_dir
        )
        scores.functional_equivalence = func_score
        all_notes.extend(func_notes)
    except Exception as e:
        all_notes.append(f"Testbench failed: {str(e)}")
        scores.functional_equivalence = 0.75  # default if no testbench

    # --- Dim 5: Security completeness (AST-based spec coverage) ---
    try:
        verifier2 = SecurityVerifier(ast, metadata)
        verifier2.score()  # populate properties
        scores.security_completeness = verifier2.score_completeness(spec_path)
    except Exception as e:
        all_notes.append(f"Completeness check failed: {str(e)}")
        scores.security_completeness = 0.0

    return ExampleResult(
        example_id=example_id,
        scores=scores,
        notes=all_notes,
        property_details=property_details,
    )


# ===================================================================
# MODE: REGEX — Original regex-based scoring (no dependencies)
# ===================================================================

# --- Regex synthesis checks (unchanged from original) ---

SYNTHESIS_ANTIPATTERNS = [
    (r"\bnew\s+\w+", "dynamic allocation (new)"),
    (r"\bmalloc\s*\(", "dynamic allocation (malloc)"),
    (r"\bfree\s*\(", "dynamic deallocation (free)"),
    (r"\bdelete\s+", "dynamic deallocation (delete)"),
    (r"\bprintf\s*\(", "system call (printf)"),
    (r"\bcout\s*<<", "system call (cout)"),
    (r"\bfopen\s*\(", "file I/O (fopen)"),
    (r"\bthrow\s+", "exception (throw)"),
    (r"\bcatch\s*\(", "exception (catch)"),
    (r"\btry\s*\{", "exception (try)"),
    (r"\bvirtual\s+", "virtual function"),
    (r"\bdynamic_cast\s*<", "RTTI (dynamic_cast)"),
    (r"\bstd::vector\s*<", "STL container (vector)"),
    (r"\bstd::map\s*<", "STL container (map)"),
    (r"\bstd::string\b", "STL string"),
]
SYNTHESIS_POSITIVE_PATTERNS = [
    (r"#pragma\s+HLS", "HLS pragma present"),
    (r"\bap_uint\s*<", "HLS type ap_uint"),
    (r"\bap_int\s*<", "HLS type ap_int"),
    (r"\bhls::stream\s*<", "HLS stream type"),
]

def score_synthesis_regex(path: str) -> Tuple[float, List[str]]:
    notes = []
    if not os.path.exists(path):
        return 0.0, ["No secure code submitted"]
    with open(path, "r") as f:
        code = f.read()
    violations = [d for p, d in SYNTHESIS_ANTIPATTERNS if re.search(p, code)]
    positives = [d for p, d in SYNTHESIS_POSITIVE_PATTERNS if re.search(p, code)]
    if len(violations) == 0 and len(positives) >= 2:
        score = 1.0
    elif len(violations) == 0 and len(positives) >= 1:
        score = 0.85
    elif len(violations) <= 1:
        score = 0.5
        notes.append(f"Synthesis concern: {', '.join(violations)}")
    else:
        score = 0.25
        notes.append(f"Multiple synthesis issues: {', '.join(violations)}")
    return round(score, 3), notes


# --- Regex security property checks (unchanged from original) ---

def score_security_regex(path: str, metadata: dict) -> Tuple[float, List[str]]:
    if not os.path.exists(path):
        return 0.0, ["No secure code submitted"]
    with open(path, "r") as f:
        code = f.read()
    domain = metadata.get("security_domain", "")
    if domain == "information_flow_tracking":
        return _regex_ift(code)
    elif domain == "access_control":
        return _regex_ac(code)
    elif domain == "side_channel":
        return _regex_sc(code)
    elif domain == "resource_isolation":
        return _regex_ri(code)
    return 0.0, []

def _regex_ift(c):
    s, n = 0.0, []
    if re.search(r"struct\s+tainted|SecurityLabel|enum.*SECRET.*PUBLIC", c): s += 0.2
    else: n.append("Missing taint type")
    if "SECRET" in c and "PUBLIC" in c: s += 0.2
    if re.search(r"operator\^|operator\+|operator\|", c): s += 0.2
    if re.search(r"sbox.*label|label.*sbox", c, re.DOTALL): s += 0.1
    if re.search(r"declassif|authorized|check_output", c, re.I): s += 0.15
    if not re.search(r"debug_out|internal_state_out|diagnostic", c): s += 0.15
    else: n.append("Debug port still present")
    return round(s, 3), n

def _regex_ac(c):
    s, n = 0.0, []
    if re.search(r"(has_privilege|get_access|channel_authorized)\s*\(", c): s += 0.25
    if re.search(r"if\s*\(!?(has_privilege|get_access|channel_authorized)", c): s += 0.25
    if re.search(r"rdata\s*=\s*0", c): s += 0.2
    if re.search(r"access_denied", c): s += 0.15
    if not re.search(r"debug_mode", c): s += 0.15
    else: n.append("Debug mode bypass present")
    return round(s, 3), n

def _regex_sc(c):
    s, n = 0.0, []
    bodies = re.findall(r"for\s*\(.*?\)\s*\{(.*?)\}", c, re.DOTALL)
    if not any(re.search(r"\bbreak\b|\breturn\b", b) for b in bodies): s += 0.3
    else: n.append("Early exit in loop")
    if re.search(r"for\s*\(\s*int\s+\w+\s*=\s*\d+\s*;\s*\w+\s*[<>=]+\s*\d+", c): s += 0.2
    if re.search(r"diff\s*\|=|cswap|r0.*r1.*mod_mul", c): s += 0.2
    if re.search(r"\|=\s*\(|cswap|mask\s*&", c, re.I): s += 0.2
    if re.search(r"#pragma\s+HLS\s+(UNROLL|PIPELINE)", c): s += 0.1
    return round(s, 3), n

def _regex_ri(c):
    s, n = 0.0, []
    if len(re.findall(r"static\s+\w+\s+\w+\s*\[", c)) >= 2: s += 0.25
    if re.search(r"sanitize|for.*=\s*0.*\w+\[.*\]\s*=\s*0", c, re.DOTALL): s += 0.25
    if re.search(r"\[\w+\]\s*=\s*0\s*;.*//.*clear|//.*zero", c, re.I|re.DOTALL): s += 0.2
    if re.search(r"tdm|slot|current_slot", c, re.I): s += 0.15
    if re.search(r"zeroize|sanitize_buffer", c, re.I): s += 0.15
    return round(s, 3), n


def evaluate_example_regex(
    submission_dir: str, reference_dir: str, rubric: dict
) -> ExampleResult:
    metadata = load_metadata(reference_dir)
    example_id = metadata["id"]
    scores = DimensionScores()
    all_notes = []

    sub_vr = os.path.join(submission_dir, "vulnerability_report.md")
    sub_code = os.path.join(submission_dir, "secure.cpp")

    det_score, det_notes = score_detection(sub_vr, reference_dir, metadata)
    scores.detection_rate = det_score
    all_notes.extend(det_notes)

    sec_score, sec_notes = score_security_regex(sub_code, metadata)
    scores.flow_correctness = sec_score
    all_notes.extend(sec_notes)

    syn_score, syn_notes = score_synthesis_regex(sub_code)
    scores.synthesis_pass = syn_score
    all_notes.extend(syn_notes)

    scores.functional_equivalence = 0.75 if os.path.exists(sub_code) else 0.0

    spec_path = os.path.join(reference_dir, "security_spec.md")
    if os.path.exists(spec_path) and os.path.exists(sub_code):
        with open(spec_path) as f: spec = f.read()
        with open(sub_code) as f: code = f.read()
        props = re.findall(r"[-•]\s*(.+)", spec)
        addressed = sum(1 for p in props if any(
            kw.lower() in code.lower() for kw in re.findall(r"\w{4,}", p)[:3]
        ))
        scores.security_completeness = round(addressed / len(props), 3) if props else 0.5
    else:
        scores.security_completeness = 0.0

    return ExampleResult(example_id=example_id, scores=scores, notes=all_notes)


# ===================================================================
# Main
# ===================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Evaluate HLS Security Benchmark submissions"
    )
    parser.add_argument("--input", required=True,
                        help="Directory containing LLM submission outputs")
    parser.add_argument("--reference", required=True,
                        help="Directory containing reference examples")
    parser.add_argument("--rubric", default=None,
                        help="Path to scoring_rubric.json")
    parser.add_argument("--output", default="evaluation_report.json",
                        help="Output report path")
    parser.add_argument("--mode", choices=["regex", "simulate"], default="regex",
                        help="Evaluation mode: regex (no deps) or simulate (full)")
    args = parser.parse_args()

    if args.mode == "simulate" and not HAS_SIM_BACKEND:
        print(f"ERROR: Simulation backend unavailable: {_SIM_IMPORT_ERROR}")
        print("Install with: pip install libclang && apt install clang libclang-dev")
        print("Falling back to regex mode.\n")
        args.mode = "regex"

    rubric_path = args.rubric or os.path.join(EVAL_DIR, "scoring_rubric.json")
    rubric = load_rubric(rubric_path)
    difficulty_weights = rubric.get("difficulty_weights",
                                     {"easy": 1.0, "medium": 1.5, "hard": 2.0})

    evaluate_fn = (evaluate_example_simulate if args.mode == "simulate"
                   else evaluate_example_regex)

    print(f"Mode: {args.mode.upper()}")
    print(f"{'='*60}\n")

    results = []
    total_weighted = 0.0
    total_weight = 0.0

    for ex_info in rubric["examples"]:
        ex_id = ex_info["id"]
        ref_dir = os.path.join(args.reference, ex_id)
        sub_dir = os.path.join(args.input, ex_id)

        if not os.path.exists(ref_dir):
            print(f"  WARNING: Reference not found for {ex_id}, skipping")
            continue

        if not os.path.exists(sub_dir):
            print(f"  WARNING: Submission not found for {ex_id}, scoring zero")
            result = ExampleResult(
                example_id=ex_id, scores=DimensionScores(),
                notes=["No submission found"]
            )
        else:
            result = evaluate_fn(sub_dir, ref_dir, rubric)

        results.append(result)

        diff = ex_info.get("difficulty", "medium")
        w = difficulty_weights.get(diff, 1.0)
        total_weighted += result.scores.composite() * w
        total_weight += w

        c = result.scores.composite()
        print(f"  {ex_id}: composite={c:.3f} grade={result.scores.grade()} [{diff}]")
        print(f"    detection={result.scores.detection_rate:.2f}  "
              f"security={result.scores.flow_correctness:.2f}  "
              f"synth={result.scores.synthesis_pass:.2f}  "
              f"func={result.scores.functional_equivalence:.2f}  "
              f"complete={result.scores.security_completeness:.2f}")
        if result.notes:
            for note in result.notes[:5]:
                print(f"    → {note}")
        print()

    mean_composite = (sum(r.scores.composite() for r in results) / len(results)
                      if results else 0.0)
    diff_weighted = total_weighted / total_weight if total_weight > 0 else 0.0

    if diff_weighted >= 0.90: agg_grade = "A"
    elif diff_weighted >= 0.75: agg_grade = "B"
    elif diff_weighted >= 0.60: agg_grade = "C"
    elif diff_weighted >= 0.40: agg_grade = "D"
    else: agg_grade = "F"

    report = {
        "model": "unknown",
        "mode": args.mode,
        "examples": [
            {
                "id": r.example_id,
                "scores": {
                    "detection_rate": r.scores.detection_rate,
                    "flow_correctness": r.scores.flow_correctness,
                    "synthesis_pass": r.scores.synthesis_pass,
                    "functional_equivalence": r.scores.functional_equivalence,
                    "security_completeness": r.scores.security_completeness,
                },
                "composite": round(r.scores.composite(), 3),
                "grade": r.scores.grade(),
                "notes": r.notes,
                "property_details": r.property_details,
            }
            for r in results
        ],
        "aggregate": {
            "mean_composite": round(mean_composite, 3),
            "difficulty_weighted": round(diff_weighted, 3),
            "grade": agg_grade,
        },
    }

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(f"{'='*60}")
    print(f"  Mode: {args.mode.upper()}")
    print(f"  Aggregate: mean={mean_composite:.3f}  "
          f"difficulty-weighted={diff_weighted:.3f}  grade={agg_grade}")
    print(f"  Report saved to: {args.output}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
