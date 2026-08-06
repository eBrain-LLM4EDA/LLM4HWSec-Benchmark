#!/usr/bin/env python3
"""evaluate.py – Grade the submitted vulnerability_report.json for the RTL variable-latency divider task."""

import json
import os
import sys

# ---------------------------------------------------------------------------
# Private ground truth (inlined to keep the bundle self-contained)
# ---------------------------------------------------------------------------
# SR1: vulnerable_component must mention the early-termination logic.
SR1_KEYWORDS = [
    "early_done",
    "comparator",
    "a_reg == 0",
    "a_reg == {WIDTH{1'b0}}",
    "early termination",
    "early-termination",
    "variable latency",
    "variable-latency",
]

# SR2: recommended_fix must describe a fixed-latency design change.
SR2_KEYWORDS = [
    "remove early_done",
    "remove early done",
    "fixed latency",
    "fixed-latency",
    "all iterations",
    "run all iterations",
    "counter runs to width",
    "WIDTH cycles",
    "always run WIDTH",
    "disable early termination",
    "eliminate early termination",
    "constant time",
    "constant-time",
    "fixed number of cycles",
    "run for WIDTH",
    "complete all WIDTH",
    "no early exit",
    "no early termination",
    "run to completion",
    "full WIDTH iterations",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def emit(pass_: bool, req_id: str, reason: str = "") -> None:
    """Print a standardised [TEST] marker."""
    if pass_:
        print(f"[TEST] PASS: {req_id}")
    else:
        msg = f"[TEST] FAIL: {req_id}"
        if reason:
            msg += f": {reason}"
        print(msg)

def check_keywords(text: str, keywords: list[str]) -> bool:
    """Return True if *any* keyword appears as a case-insensitive substring."""
    lower = text.lower()
    return any(kw.lower() in lower for kw in keywords)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    submission_path = os.path.join("submission", "vulnerability_report.json")

    # --- FR1: file exists and is valid JSON with required keys ------------
    if not os.path.isfile(submission_path):
        emit(False, "FR1", f"{submission_path} not found")
        # Cannot continue without the file – fail remaining requirements
        for rid in ("FR2", "FR3", "FR4", "SR1", "SR2"):
            emit(False, rid, "submission file missing")
        return 1

    try:
        with open(submission_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        emit(False, "FR1", f"invalid JSON: {exc}")
        for rid in ("FR2", "FR3", "FR4", "SR1", "SR2"):
            emit(False, rid, "submission file not valid JSON")
        return 1

    required_keys = {"vulnerability_found", "vulnerable_component", "recommended_fix"}
    missing = required_keys - set(data.keys())
    if missing:
        emit(False, "FR1", f"missing top-level keys: {sorted(missing)}")
        # Still try to check the keys that *are* present for FR2-FR4,
        # but SR checks will fail because the required data is absent.
    else:
        emit(True, "FR1")

    # --- FR2: vulnerability_found is a boolean ----------------------------
    vf = data.get("vulnerability_found")
    if isinstance(vf, bool):
        emit(True, "FR2")
    else:
        emit(False, "FR2", f"expected bool, got {type(vf).__name__}")

    # --- FR3: vulnerable_component is a non-empty string -------------------
    vc = data.get("vulnerable_component")
    if isinstance(vc, str) and len(vc) > 0:
        emit(True, "FR3")
    else:
        emit(False, "FR3", "must be a non-empty string")

    # --- FR4: recommended_fix is a non-empty string -----------------------
    rf = data.get("recommended_fix")
    if isinstance(rf, str) and len(rf) > 0:
        emit(True, "FR4")
    else:
        emit(False, "FR4", "must be a non-empty string")

    # --- SR1 & SR2: substantive correctness -------------------------------
    # Only check if vulnerability_found is True; otherwise fail.
    if vf is not True:
        emit(False, "SR1", "vulnerability_found is not true")
        emit(False, "SR2", "vulnerability_found is not true")
    else:
        # SR1
        if isinstance(vc, str) and check_keywords(vc, SR1_KEYWORDS):
            emit(True, "SR1")
        else:
            emit(False, "SR1", "vulnerable_component does not identify early-termination logic")

        # SR2
        if isinstance(rf, str) and check_keywords(rf, SR2_KEYWORDS):
            emit(True, "SR2")
        else:
            emit(False, "SR2", "recommended_fix does not describe a fixed-latency design change")

    # Determine overall exit code
    # Re-read stdout? Simpler: track failures ourselves.
    # We'll just re-check the conditions used above.
    failures = []

    # FR1
    if not os.path.isfile(submission_path):
        failures.append("FR1")
    else:
        try:
            with open(submission_path, "r", encoding="utf-8") as fh:
                data2 = json.load(fh)
            if missing := required_keys - set(data2.keys()):
                failures.append("FR1")
        except Exception:
            failures.append("FR1")

    # FR2
    if not isinstance(vf, bool):
        failures.append("FR2")

    # FR3
    if not (isinstance(vc, str) and len(vc) > 0):
        failures.append("FR3")

    # FR4
    if not (isinstance(rf, str) and len(rf) > 0):
        failures.append("FR4")

    # SR1
    if vf is not True or not (isinstance(vc, str) and check_keywords(vc, SR1_KEYWORDS)):
        failures.append("SR1")

    # SR2
    if vf is not True or not (isinstance(rf, str) and check_keywords(rf, SR2_KEYWORDS)):
        failures.append("SR2")

    if failures:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())