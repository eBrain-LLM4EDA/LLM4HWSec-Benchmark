#!/usr/bin/env python3
"""
Evaluation Script for HLS Security-Aware Code Generation Benchmark (Arda)

Usage:
    python run_evaluation.py --input llm_outputs/ --reference examples/

Each example directory in llm_outputs/ should contain:
    - secure.cpp         (hardened HLS code)
    - vulnerability_report.md  (vulnerability findings)

The script performs static analysis checks and scores against the reference.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


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


# ---------------------------------------------------------------------------
# Scoring rubric loader
# ---------------------------------------------------------------------------

def load_rubric(rubric_path: str) -> dict:
    with open(rubric_path, "r") as f:
        return json.load(f)


def load_metadata(example_dir: str) -> dict:
    with open(os.path.join(example_dir, "metadata.json"), "r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Vulnerability Detection Scoring
# ---------------------------------------------------------------------------

def count_reference_vulnerabilities(ref_dir: str) -> Tuple[int, List[str]]:
    """Parse reference vulnerability report and return count + CWE list."""
    vr_path = os.path.join(ref_dir, "vulnerability_report.md")
    if not os.path.exists(vr_path):
        return 0, []

    with open(vr_path, "r") as f:
        content = f.read()

    # Extract vulnerability headers (### V1: ..., ### V2: ..., etc.)
    vulns = re.findall(r"### V\d+:.*?\(CWE-(\d+)\)", content)
    return len(vulns), [f"CWE-{c}" for c in vulns]


def score_detection(submission_vr_path: str, ref_dir: str, metadata: dict) -> Tuple[float, List[str]]:
    """Score vulnerability detection rate."""
    notes = []
    expected_count = metadata.get("expected_vulnerabilities", 0)
    _, ref_cwes = count_reference_vulnerabilities(ref_dir)

    if not os.path.exists(submission_vr_path):
        notes.append("No vulnerability report submitted")
        return 0.0, notes

    with open(submission_vr_path, "r") as f:
        content = f.read()

    # Count reported vulnerabilities
    reported_vulns = re.findall(r"(?:###|##)\s*V\d+|(?:###|##)\s*\d+\.", content)
    reported_cwes = re.findall(r"CWE-(\d+)", content)
    reported_cwes = [f"CWE-{c}" for c in reported_cwes]

    # True positives: CWEs that match reference
    true_positives = len(set(reported_cwes) & set(ref_cwes))
    # False positives: CWEs not in reference
    false_positives = len(set(reported_cwes) - set(ref_cwes))

    if expected_count == 0:
        return 1.0, notes

    detection_rate = min(true_positives / expected_count, 1.0)

    # CWE accuracy factor
    total_reported = len(reported_cwes)
    if total_reported > 0:
        cwe_accuracy = true_positives / total_reported
    else:
        cwe_accuracy = 0.0

    score = detection_rate * cwe_accuracy
    # False positive penalty
    score = max(score - (false_positives * 0.05), 0.0)

    if true_positives < expected_count:
        notes.append(f"Missed {expected_count - true_positives} of {expected_count} vulnerabilities")
    if false_positives > 0:
        notes.append(f"{false_positives} false positive(s)")

    return round(score, 3), notes


# ---------------------------------------------------------------------------
# 2. Synthesis Compatibility Scoring
# ---------------------------------------------------------------------------

SYNTHESIS_ANTIPATTERNS = [
    (r"\bnew\s+\w+",                        "dynamic allocation (new)"),
    (r"\bmalloc\s*\(",                       "dynamic allocation (malloc)"),
    (r"\bfree\s*\(",                         "dynamic deallocation (free)"),
    (r"\bdelete\s+",                         "dynamic deallocation (delete)"),
    (r"\bprintf\s*\(",                       "system call (printf)"),
    (r"\bcout\s*<<",                         "system call (cout)"),
    (r"\bfopen\s*\(",                        "file I/O (fopen)"),
    (r"\bthrow\s+",                          "exception (throw)"),
    (r"\bcatch\s*\(",                        "exception (catch)"),
    (r"\btry\s*\{",                          "exception (try)"),
    (r"\bvirtual\s+",                        "virtual function"),
    (r"\bdynamic_cast\s*<",                  "RTTI (dynamic_cast)"),
    (r"\bstd::vector\s*<",                   "STL container (vector)"),
    (r"\bstd::map\s*<",                      "STL container (map)"),
    (r"\bstd::string\b",                     "STL string"),
]

SYNTHESIS_POSITIVE_PATTERNS = [
    (r"#pragma\s+HLS",                       "HLS pragma present"),
    (r"\bap_uint\s*<",                       "HLS type ap_uint"),
    (r"\bap_int\s*<",                        "HLS type ap_int"),
    (r"\bhls::stream\s*<",                   "HLS stream type"),
]


def score_synthesis(secure_code_path: str) -> Tuple[float, List[str]]:
    """Score synthesis compatibility via static pattern checks."""
    notes = []
    if not os.path.exists(secure_code_path):
        notes.append("No secure code submitted")
        return 0.0, notes

    with open(secure_code_path, "r") as f:
        code = f.read()

    # Check for anti-patterns
    violations = []
    for pattern, desc in SYNTHESIS_ANTIPATTERNS:
        if re.search(pattern, code):
            violations.append(desc)

    # Check for positive patterns
    positives = []
    for pattern, desc in SYNTHESIS_POSITIVE_PATTERNS:
        if re.search(pattern, code):
            positives.append(desc)

    # Scoring
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


# ---------------------------------------------------------------------------
# 3. Security Property Checks (domain-specific)
# ---------------------------------------------------------------------------

def score_security_properties(secure_code_path: str, metadata: dict) -> Tuple[float, List[str]]:
    """Score security property implementation based on domain."""
    notes = []
    if not os.path.exists(secure_code_path):
        return 0.0, ["No secure code submitted"]

    with open(secure_code_path, "r") as f:
        code = f.read()

    domain = metadata.get("security_domain", "")
    score = 0.0

    if domain == "information_flow_tracking":
        score, notes = _score_ift(code)
    elif domain == "access_control":
        score, notes = _score_access_control(code)
    elif domain == "side_channel":
        score, notes = _score_side_channel(code)
    elif domain == "resource_isolation":
        score, notes = _score_resource_isolation(code)

    return round(score, 3), notes


def _score_ift(code: str) -> Tuple[float, List[str]]:
    score = 0.0
    notes = []

    # Taint type defined
    if re.search(r"struct\s+tainted|SecurityLabel|enum.*SECRET.*PUBLIC", code):
        score += 0.2
    else:
        notes.append("Missing taint-tracked data type")

    # Labels assigned at inputs
    if re.search(r"SECRET", code) and re.search(r"PUBLIC", code):
        score += 0.2
    else:
        notes.append("Missing label assignment at inputs")

    # Taint propagation through operators
    if re.search(r"operator\^|operator\+|operator\|", code):
        score += 0.2
    else:
        notes.append("Missing taint propagation in operators")

    # S-box / lookup propagation
    if re.search(r"sbox.*label|label.*sbox|tainted.*sbox", code, re.DOTALL):
        score += 0.1
    else:
        notes.append("S-box lookup may not propagate taint")

    # Declassification check
    if re.search(r"declassif|authorized|check_output", code, re.IGNORECASE):
        score += 0.15

    # Debug port removed
    if not re.search(r"debug_out|internal_state_out|diagnostic", code):
        score += 0.15
    else:
        notes.append("Debug/diagnostic port still present")

    return score, notes


def _score_access_control(code: str) -> Tuple[float, List[str]]:
    score = 0.0
    notes = []

    # Policy function exists
    if re.search(r"(has_privilege|get_access|check_access|channel_authorized|is_authorized)\s*\(", code):
        score += 0.25
    else:
        notes.append("No access policy function found")

    # Policy check before memory access
    if re.search(r"if\s*\(!?(has_privilege|get_access|channel_authorized|access)", code):
        score += 0.25
    else:
        notes.append("No policy check guards memory/register access")

    # Safe default on deny
    if re.search(r"rdata\s*=\s*0", code):
        score += 0.2

    # Denial feedback
    if re.search(r"access_denied", code):
        score += 0.15

    # Debug mode removed
    if not re.search(r"debug_mode", code):
        score += 0.15
    else:
        notes.append("Debug mode bypass still present")

    return score, notes


def _score_side_channel(code: str) -> Tuple[float, List[str]]:
    score = 0.0
    notes = []

    # No break in comparison/exponent loop
    loop_bodies = re.findall(r"for\s*\(.*?\)\s*\{(.*?)\}", code, re.DOTALL)
    has_early_exit = any(re.search(r"\bbreak\b|\breturn\b", body) for body in loop_bodies)
    if not has_early_exit:
        score += 0.3
    else:
        notes.append("Early exit (break/return) found in loop body")

    # Fixed iteration count
    if re.search(r"for\s*\(\s*int\s+\w+\s*=\s*\d+\s*;\s*\w+\s*[<>=]+\s*\d+", code):
        score += 0.2

    # Constant operations (OR-accumulate or Montgomery ladder)
    if re.search(r"diff\s*\|=|cswap|r0.*r1.*mod_mul|r1.*r0.*mod_mul", code):
        score += 0.2
    else:
        notes.append("No constant-time operation pattern found (OR-accum or cswap)")

    # Branchless conditional
    if re.search(r"\|=\s*\(|cswap|mask\s*&|XOR.*swap", code, re.IGNORECASE):
        score += 0.2

    # HLS fixed pipeline pragma
    if re.search(r"#pragma\s+HLS\s+(UNROLL|PIPELINE)", code):
        score += 0.1

    return score, notes


def _score_resource_isolation(code: str) -> Tuple[float, List[str]]:
    score = 0.0
    notes = []

    # Separate storage arrays
    array_decls = re.findall(r"static\s+\w+\s+(\w+)\s*\[", code)
    if len(array_decls) >= 2:
        score += 0.25
    else:
        notes.append("Fewer than 2 separate storage arrays found")

    # Sanitize on transition
    if re.search(r"sanitize|for.*=\s*0.*\{?\s*\w+\[.*\]\s*=\s*0", code, re.DOTALL):
        score += 0.25
    else:
        notes.append("No buffer sanitization found")

    # Stale data cleared
    if re.search(r"\[\w+\]\s*=\s*0\s*;.*//.*clear|//.*FIX.*clear|//.*zero", code, re.IGNORECASE | re.DOTALL):
        score += 0.2

    # TDM or temporal isolation
    if re.search(r"tdm|time.?division|slot|current_slot", code, re.IGNORECASE):
        score += 0.15

    # Zeroize command
    if re.search(r"zeroize|sanitize_buffer|clear_buffer", code, re.IGNORECASE):
        score += 0.15

    return score, notes


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------

def evaluate_example(
    submission_dir: str,
    reference_dir: str,
    rubric: dict
) -> ExampleResult:
    """Evaluate a single benchmark example."""
    metadata = load_metadata(reference_dir)
    example_id = metadata["id"]

    scores = DimensionScores()
    all_notes = []

    # Submission files
    sub_vr = os.path.join(submission_dir, "vulnerability_report.md")
    sub_code = os.path.join(submission_dir, "secure.cpp")

    # 1. Detection rate
    det_score, det_notes = score_detection(sub_vr, reference_dir, metadata)
    scores.detection_rate = det_score
    all_notes.extend(det_notes)

    # 2. Security property correctness (flow_correctness dimension)
    sec_score, sec_notes = score_security_properties(sub_code, metadata)
    scores.flow_correctness = sec_score
    all_notes.extend(sec_notes)

    # 3. Synthesis pass
    syn_score, syn_notes = score_synthesis(sub_code)
    scores.synthesis_pass = syn_score
    all_notes.extend(syn_notes)

    # 4. Functional equivalence (requires simulation — placeholder)
    # In automated mode, we check structural compatibility
    if os.path.exists(sub_code):
        scores.functional_equivalence = 0.75  # Default: assume functional unless proven otherwise
    else:
        scores.functional_equivalence = 0.0

    # 5. Security completeness
    spec_path = os.path.join(reference_dir, "security_spec.md")
    if os.path.exists(spec_path) and os.path.exists(sub_code):
        with open(spec_path, "r") as f:
            spec = f.read()
        with open(sub_code, "r") as f:
            code = f.read()

        # Check required properties mentioned in spec appear in code
        properties = re.findall(r"[-•]\s*(.+)", spec)
        addressed = sum(1 for p in properties if any(
            kw.lower() in code.lower()
            for kw in re.findall(r"\w{4,}", p)[:3]
        ))
        if properties:
            scores.security_completeness = round(addressed / len(properties), 3)
        else:
            scores.security_completeness = 0.5
    else:
        scores.security_completeness = 0.0

    return ExampleResult(
        example_id=example_id,
        scores=scores,
        notes=all_notes
    )


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
    args = parser.parse_args()

    # Load rubric
    rubric_path = args.rubric or os.path.join(
        os.path.dirname(__file__), "scoring_rubric.json"
    )
    rubric = load_rubric(rubric_path)

    difficulty_weights = rubric.get("difficulty_weights", {
        "easy": 1.0, "medium": 1.5, "hard": 2.0
    })

    results = []
    total_weighted = 0.0
    total_weight = 0.0

    # Iterate over examples
    for ex_info in rubric["examples"]:
        ex_id = ex_info["id"]
        ref_dir = os.path.join(args.reference, ex_id)
        sub_dir = os.path.join(args.input, ex_id)

        if not os.path.exists(ref_dir):
            print(f"WARNING: Reference not found for {ex_id}, skipping")
            continue

        if not os.path.exists(sub_dir):
            print(f"WARNING: Submission not found for {ex_id}, scoring zero")
            result = ExampleResult(
                example_id=ex_id,
                scores=DimensionScores(),
                notes=["No submission found"]
            )
        else:
            result = evaluate_example(sub_dir, ref_dir, rubric)

        results.append(result)

        # Difficulty-weighted aggregate
        diff = ex_info.get("difficulty", "medium")
        w = difficulty_weights.get(diff, 1.0)
        total_weighted += result.scores.composite() * w
        total_weight += w

        print(f"  {ex_id}: composite={result.scores.composite():.3f} "
              f"grade={result.scores.grade()} [{diff}]")

    # Aggregate
    mean_composite = (
        sum(r.scores.composite() for r in results) / len(results)
        if results else 0.0
    )
    diff_weighted = total_weighted / total_weight if total_weight > 0 else 0.0

    # Determine aggregate grade
    if diff_weighted >= 0.90: agg_grade = "A"
    elif diff_weighted >= 0.75: agg_grade = "B"
    elif diff_weighted >= 0.60: agg_grade = "C"
    elif diff_weighted >= 0.40: agg_grade = "D"
    else: agg_grade = "F"

    # Build report
    report = {
        "model": "unknown",
        "timestamp": None,
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

    print(f"\n{'='*60}")
    print(f"  Aggregate: mean={mean_composite:.3f}  "
          f"difficulty-weighted={diff_weighted:.3f}  grade={agg_grade}")
    print(f"  Report saved to: {args.output}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
