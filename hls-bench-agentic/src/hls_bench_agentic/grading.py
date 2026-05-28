"""
Difficulty weighting and grade-band computation.

Mirrors the scoring rubric from hls-security-benchmark:
  easy   = 1.0×
  medium = 1.5×
  hard   = 2.0×

Grade bands:
  A  0.90 – 1.00
  B  0.75 – 0.89
  C  0.60 – 0.74
  D  0.40 – 0.59
  F  0.00 – 0.39
"""
from __future__ import annotations

from typing import Any

DIFFICULTY_WEIGHTS: dict[str, float] = {
    "easy": 1.0,
    "medium": 1.5,
    "hard": 2.0,
}

_GRADE_BANDS = [
    (0.90, "A"),
    (0.75, "B"),
    (0.60, "C"),
    (0.40, "D"),
    (0.00, "F"),
]

# Dimension weights for composite score computation.
# Two modes: with LLM scorer and without (regex/static only).
_WEIGHTS_WITH_LLM = {
    "llm_security_score":            0.30,
    "security_property_correctness": 0.25,
    "synthesis_pass":                0.20,
    "functional_equivalence":        0.15,
    "security_completeness":         0.10,
}

_WEIGHTS_NO_LLM = {
    "security_property_correctness": 0.40,
    "synthesis_pass":                0.30,
    "functional_equivalence":        0.20,
    "security_completeness":         0.10,
}


def get_difficulty_weight(task_spec: dict[str, Any]) -> float:
    difficulty = task_spec.get("hidden_spec", {}).get("difficulty", "medium")
    return DIFFICULTY_WEIGHTS.get(difficulty, 1.5)


def compute_grade(score: float) -> str:
    for threshold, grade in _GRADE_BANDS:
        if score >= threshold:
            return grade
    return "F"


def compute_composite(
    *,
    synthesis_pass: float,
    security_property_correctness: float,
    functional_equivalence: float,
    security_completeness: float,
    llm_security_score: float | None = None,
) -> dict[str, Any]:
    """Compute weighted composite score and letter grade.

    Returns a dict with all dimension scores, composite, and grade.
    """
    dims = {
        "synthesis_pass":                round(synthesis_pass, 4),
        "security_property_correctness": round(security_property_correctness, 4),
        "functional_equivalence":        round(functional_equivalence, 4),
        "security_completeness":         round(security_completeness, 4),
    }

    if llm_security_score is not None:
        dims["llm_security_score"] = round(llm_security_score, 4)
        weights = _WEIGHTS_WITH_LLM
    else:
        weights = _WEIGHTS_NO_LLM

    composite = sum(dims.get(k, 0.0) * w for k, w in weights.items())
    composite = round(min(max(composite, 0.0), 1.0), 4)

    return {
        "dimension_scores": dims,
        "weights_used": weights,
        "composite_score": composite,
        "grade": compute_grade(composite),
    }


def functional_equivalence_from_execution(execution_results: dict[str, Any]) -> float:
    """Derive a 0–1 score from runner execution results."""
    all_steps = execution_results.get("steps", [])
    functional_steps = [
        s for s in all_steps
        if s.get("name") in {"csim", "functional", "c_simulation"}
    ]
    steps = functional_steps or all_steps
    if not steps:
        return 0.5   # no data; neutral

    not_run = sum(1 for s in steps if s.get("status") == "not_run")
    if not_run == len(steps):
        return 0.5   # all disabled; neutral

    passed = sum(1 for s in steps if s.get("status") == "pass")
    runnable = len(steps) - not_run
    return round(passed / runnable, 4) if runnable else 0.5
