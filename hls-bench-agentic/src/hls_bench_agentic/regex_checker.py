"""
Regex-based forbidden pattern checker.
Used as a fast first-pass filter and as a fallback when the LLM Scorer is unavailable.
"""
from __future__ import annotations

import re
from typing import Any


def check_forbidden_patterns(
    source: str,
    forbidden_patterns: list[str],
) -> dict[str, bool]:
    """Return {pattern: found} for every pattern in *forbidden_patterns*."""
    return {p: _match(source, p) for p in forbidden_patterns}


def score_security_requirements(
    source_files: dict[str, str],
    task_spec: dict[str, Any],
) -> dict[str, Any]:
    """
    Score security requirements via regex pattern matching.

    Returns a dict with:
      pattern_violation_rate   float  fraction of forbidden patterns found (0 = none found)
      requirement_scores       list   per-requirement {requirement_id, score, rationale, detected_issues}
      overall_regex_score      float  1 - pattern_violation_rate (higher = more secure)
      violations               dict   {pattern: found}
    """
    hidden = task_spec.get("hidden_spec", {})
    forbidden = hidden.get("forbidden_patterns", [])
    security_reqs = hidden.get("security_requirements", [])

    combined_source = "\n".join(source_files.values())

    violations = check_forbidden_patterns(combined_source, forbidden)
    n_violated = sum(violations.values())
    n_total = len(forbidden) if forbidden else 1
    pattern_violation_rate = n_violated / n_total

    req_scores = []
    for req in security_reqs:
        req_id = req["id"]
        req_text = req.get("requirement", "").lower()
        req_keywords = set(re.findall(r"\b\w{4,}\b", req_text))

        # Check if any violated forbidden pattern overlaps with this requirement's keywords
        relevant_violated = [
            p for p, found in violations.items()
            if found and _keywords_overlap(req_keywords, p.lower())
        ]

        # Also check detection_strategy patterns
        strategy = req.get("detection_strategy", "").lower()
        strategy_keywords = set(re.findall(r"\b\w{4,}\b", strategy))
        strategy_evidence = [
            p for p, found in violations.items()
            if found and _keywords_overlap(strategy_keywords, p.lower())
        ]

        all_issues = list(set(relevant_violated + strategy_evidence))
        score = 0.0 if all_issues else 1.0

        req_scores.append({
            "requirement_id": req_id,
            "score": score,
            "rationale": (
                f"Forbidden patterns detected: {all_issues}" if all_issues
                else "No forbidden patterns detected for this requirement"
            ),
            "detected_issues": all_issues,
        })

    overall = 1.0 - pattern_violation_rate
    return {
        "pattern_violation_rate": round(pattern_violation_rate, 4),
        "overall_regex_score": round(overall, 4),
        "violations": violations,
        "requirement_scores": req_scores,
    }


def _match(source: str, pattern: str) -> bool:
    try:
        return bool(re.search(pattern, source, re.IGNORECASE | re.MULTILINE))
    except re.error:
        return pattern.lower() in source.lower()


def _keywords_overlap(req_keywords: set[str], pattern: str) -> bool:
    pattern_words = set(re.findall(r"\b\w{4,}\b", pattern))
    return bool(req_keywords & pattern_words)