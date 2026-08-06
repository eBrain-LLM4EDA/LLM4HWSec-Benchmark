#!/usr/bin/env python3
"""evaluate.py – grades submission/trojan_report.json against hidden ground truth."""

import json
import os
import sys

# ---------------------------------------------------------------------------
# Private ground truth (imported from evaluation/private/ground_truth.py)
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "private"))
from ground_truth import (
    EXPECTED_TRIGGER_SIGNALS,
    EXPECTED_PAYLOAD_KEYWORDS,
    MIN_CONFIDENCE,
    EXPECTED_TROJAN_DETECTED,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def emit(ok: bool, req_id: str, reason: str = "") -> None:
    """Print a standardised PASS/FAIL line."""
    if ok:
        print(f"[TEST] PASS: {req_id}")
    else:
        print(f"[TEST] FAIL: {req_id}: {reason}")

def load_submission(path: str):
    """Return the parsed JSON object or None on failure."""
    if not os.path.isfile(path):
        emit(False, "FR1", f"submission file not found: {path}")
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        emit(False, "FR1", f"invalid JSON: {exc}")
        return None
    return data

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    submission_path = os.path.join("submission", "trojan_report.json")
    report = load_submission(submission_path)

    # FR1 – valid JSON (already checked during load)
    if report is not None:
        emit(True, "FR1")
    else:
        # FR1 already emitted FAIL; we cannot continue with the other checks
        # because they all depend on a valid report.
        # Emit FAIL for every remaining requirement and exit.
        for rid in ("FR2", "FR3", "SR1", "SR2", "SR3", "SR4", "SR5"):
            emit(False, rid, "cannot grade – report not valid JSON")
        return 1

    # FR2 – top-level fields and types
    fr2_ok = True
    if not isinstance(report.get("trojan_detected"), bool):
        emit(False, "FR2", "missing or non-boolean 'trojan_detected'")
        fr2_ok = False
    if not isinstance(report.get("findings"), list):
        emit(False, "FR2", "missing or non-array 'findings'")
        fr2_ok = False
    if not isinstance(report.get("overall_confidence"), (int, float)):
        emit(False, "FR2", "missing or non-numeric 'overall_confidence'")
        fr2_ok = False
    if fr2_ok:
        emit(True, "FR2")

    # FR3 – each finding must have module (str), signal (str), rationale (str), confidence (number)
    findings = report.get("findings", [])
    fr3_ok = True
    for idx, finding in enumerate(findings):
        if not isinstance(finding, dict):
            emit(False, "FR3", f"finding[{idx}] is not an object")
            fr3_ok = False
            continue
        for field in ("module", "signal", "rationale"):
            if not isinstance(finding.get(field), str):
                emit(False, "FR3", f"finding[{idx}] missing or non-string '{field}'")
                fr3_ok = False
        if not isinstance(finding.get("confidence"), (int, float)):
            emit(False, "FR3", f"finding[{idx}] missing or non-numeric 'confidence'")
            fr3_ok = False
    if fr3_ok:
        emit(True, "FR3")

    # -----------------------------------------------------------------------
    # Security requirements – substantive checks against ground truth
    # -----------------------------------------------------------------------
    # Helper: check if a finding matches a given module and signal name.
    def finding_matches(finding, module, signal):
        return (finding.get("module", "").strip().lower() == module.lower() and
                finding.get("signal", "").strip().lower() == signal.lower())

    # SR1 – counter_terminal in counter.v
    sr1_ok = any(finding_matches(f, "counter", "counter_terminal") for f in findings)
    emit(sr1_ok, "SR1", "counter_terminal not identified in counter.v")

    # SR2 – command_match in command_decoder.v
    sr2_ok = any(finding_matches(f, "command_decoder", "command_match") for f in findings)
    emit(sr2_ok, "SR2", "command_match not identified in command_decoder.v")

    # SR3 – sticky_error in error_handler.v
    sr3_ok = any(finding_matches(f, "error_handler", "sticky_error") for f in findings)
    emit(sr3_ok, "SR3", "sticky_error not identified in error_handler.v")

    # SR4 – payload mux in top.v (multiplexer / conditional assignment driving secret_reg[0] to status_out)
    sr4_ok = False
    for f in findings:
        if f.get("module", "").strip().lower() != "top":
            continue
        rationale = f.get("rationale", "").lower()
        # Check for presence of payload-related keywords
        if any(kw in rationale for kw in EXPECTED_PAYLOAD_KEYWORDS):
            sr4_ok = True
            break
    emit(sr4_ok, "SR4", "payload mux (secret_reg[0] -> status_out) not described in top.v")

    # SR5 – trojan_detected == true and overall_confidence >= threshold
    sr5_ok = (report.get("trojan_detected") is True and
              report.get("overall_confidence", 0) >= MIN_CONFIDENCE)
    emit(sr5_ok, "SR5", "trojan_detected must be true and overall_confidence >= 0.7")

    # -----------------------------------------------------------------------
    # Determine exit code
    # -----------------------------------------------------------------------
    # Collect all emitted lines to decide exit code (any FAIL -> non-zero)
    # We re-read stdout? Simpler: track failures manually.
    # We'll just check the boolean flags we already have.
    all_ok = (fr2_ok and fr3_ok and sr1_ok and sr2_ok and sr3_ok and sr4_ok and sr5_ok)
    # FR1 is already handled – if we got here it passed.
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())