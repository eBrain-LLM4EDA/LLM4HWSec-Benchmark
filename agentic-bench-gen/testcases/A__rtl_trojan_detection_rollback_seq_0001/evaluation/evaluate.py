#!/usr/bin/env python3
"""
evaluate.py - main grading entry point for rtl_trojan_detection_rollback_seq_0001

Grades submission/trojan_report.json against the public functional
requirements (FR1-FR4) and the hidden security requirements (SR1-SR4).

This is a report_grading task: the submission is an analysis report (JSON),
not code. inputs/version_ctrl.v is read for reference AND to extract the
set of genuine internal register names declared in the design (used by
FR3/SR1 to reject vague placeholder phrasing); the actual PASS/FAIL
verdicts are computed from the submitted report.
"""

import json
import os
import sys

# Make sibling modules importable regardless of CWD.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
_PRIVATE_DIR = os.path.join(_THIS_DIR, "private")
if _PRIVATE_DIR not in sys.path:
    sys.path.insert(0, _PRIVATE_DIR)

import report_checks  # noqa: E402

try:
    from private import sr_checks  # noqa: E402
except Exception:
    # Fallback in case package-style import fails due to layout; try direct module import.
    import sr_checks  # noqa: E402

INPUTS_VERILOG = "inputs/version_ctrl.v"
SUBMISSION_PATH = "submission/trojan_report.json"

results = []  # list of (requirement_id, passed_bool, reason_str)


def record(req_id, passed, reason=""):
    results.append((req_id, passed, reason))
    if passed:
        print("[TEST] PASS: {}".format(req_id))
    else:
        print("[TEST] FAIL: {}: {}".format(req_id, reason))


def fail_all_remaining(req_ids, reason):
    for rid in req_ids:
        record(rid, False, reason)


def main():
    # --- SETUP: reference RTL must exist (needed for FR3/SR1 real-signal check) ---
    if not os.path.isfile(INPUTS_VERILOG):
        print("[TEST] FAIL: SETUP: {} not found".format(INPUTS_VERILOG))
        sys.exit(1)

    try:
        with open(INPUTS_VERILOG, "r", encoding="utf-8") as f:
            verilog_text = f.read()
    except OSError as e:
        print("[TEST] FAIL: SETUP: could not read {}: {}".format(INPUTS_VERILOG, e))
        sys.exit(1)

    real_regs = report_checks.extract_internal_registers(verilog_text)

    # --- SETUP: submission file must exist and be valid JSON ---
    if not os.path.isfile(SUBMISSION_PATH):
        print("[TEST] FAIL: SETUP: {} not found".format(SUBMISSION_PATH))
        sys.exit(1)

    try:
        with open(SUBMISSION_PATH, "r", encoding="utf-8") as f:
            raw_text = f.read()
    except OSError as e:
        print("[TEST] FAIL: SETUP: could not read {}: {}".format(SUBMISSION_PATH, e))
        sys.exit(1)

    try:
        report = json.loads(raw_text)
    except json.JSONDecodeError as e:
        # Invalid JSON is a submission content failure, not an infra failure --
        # but per the contract, malformed submission JSON should fail FR1 (and
        # cascade), not be treated as SETUP (the file exists and was read).
        # We still need FR1 to explicitly fail with a reason.
        record("FR1", False, "submission/trojan_report.json is not valid JSON: {}".format(e))
        fail_all_remaining(["FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"],
                            "cannot evaluate: submission JSON failed to parse")
        sys.exit(1)

    if not isinstance(report, dict):
        record("FR1", False, "top-level JSON value is not an object")
        fail_all_remaining(["FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"],
                            "cannot evaluate: top-level JSON is not an object")
        sys.exit(1)

    # ---------------- FR1 ----------------
    fr1_reasons = []
    candidates = report.get("candidates", None)
    summary = report.get("summary", None)
    tool_version = report.get("tool_version", None)

    if not isinstance(candidates, list):
        fr1_reasons.append("'candidates' missing or not a list")
    if not isinstance(summary, str):
        fr1_reasons.append("'summary' missing or not a string")
    if not isinstance(tool_version, str):
        fr1_reasons.append("'tool_version' missing or not a string")

    fr1_pass = len(fr1_reasons) == 0
    record("FR1", fr1_pass, "; ".join(fr1_reasons))

    if not fr1_pass:
        # Without valid top-level structure we cannot safely evaluate the rest.
        fail_all_remaining(["FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"],
                            "cannot evaluate: FR1 top-level structure invalid")
        sys.exit(1)

    # ---------------- FR2 ----------------
    fr2_reasons = []
    required_fields = {
        "id": str,
        "description": str,
        "confidence": (int, float),
        "trigger_condition": str,
        "payload_effect": str,
    }

    for idx, cand in enumerate(candidates):
        if not isinstance(cand, dict):
            fr2_reasons.append("candidate[{}] is not an object".format(idx))
            continue
        for field, ftype in required_fields.items():
            if field not in cand:
                fr2_reasons.append("candidate[{}] missing field '{}'".format(idx, field))
                continue
            val = cand[field]
            if field == "confidence":
                if isinstance(val, bool) or not isinstance(val, (int, float)):
                    fr2_reasons.append(
                        "candidate[{}].confidence is not numeric".format(idx))
                elif not (0.0 <= float(val) <= 1.0):
                    fr2_reasons.append(
                        "candidate[{}].confidence {} not in [0,1]".format(idx, val))
            else:
                if not isinstance(val, ftype):
                    fr2_reasons.append(
                        "candidate[{}].{} is not a string".format(idx, field))

    fr2_pass = len(fr2_reasons) == 0
    record("FR2", fr2_pass, "; ".join(fr2_reasons[:5]) +
           (" (+{} more)".format(len(fr2_reasons) - 5) if len(fr2_reasons) > 5 else ""))

    if not fr2_pass:
        fail_all_remaining(["FR3", "FR4", "SR1", "SR2", "SR3", "SR4"],
                            "cannot evaluate: FR2 candidate schema invalid")
        sys.exit(1)

    # From here on, candidates are well-formed enough (schema-wise) to inspect.
    # An empty candidates list is schema-valid but must fail the substantive
    # checks below (FR3/FR4/SR1-4), matching the baseline behavior.

    # ---------------- FR3 ----------------
    fr3_pass = False
    for cand in candidates:
        text = " ".join([
            str(cand.get("description", "")),
            str(cand.get("trigger_condition", "")),
            str(cand.get("payload_effect", "")),
        ])
        if report_checks.mentions_internal_state(text, real_regs):
            fr3_pass = True
            break

    record("FR3", fr3_pass,
           "no candidate description/trigger_condition/payload_effect names a "
           "genuine internal register declared in version_ctrl.v (distinct "
           "from the documented interface ports clk/rst_n/req_valid/"
           "candidate_version/req_accept/version_q/update_ack); vague "
           "placeholder phrases such as 'internal_state' or 'some internal "
           "logic' do not satisfy this requirement")

    if not fr3_pass:
        fail_all_remaining(["FR4", "SR1", "SR2", "SR3", "SR4"],
                            "cannot evaluate: FR3 failed (no genuine internal state signal identified)")
        sys.exit(1)

    # ---------------- FR4 ----------------
    top_candidate = report_checks.find_top_candidate(candidates)
    fr4_pass = False
    fr4_reason = "no candidates available"
    if top_candidate is not None:
        payload_text = str(top_candidate.get("payload_effect", ""))
        if report_checks.mentions_decrement_payload(payload_text):
            fr4_pass = True
        else:
            fr4_reason = (
                "top-confidence candidate's payload_effect does not state the "
                "exact terminal update expression (decrement/version_q-1 "
                "semantics); got: {!r}".format(payload_text)
            )
    record("FR4", fr4_pass, fr4_reason)

    if not fr4_pass:
        fail_all_remaining(["SR1", "SR2", "SR3", "SR4"],
                            "cannot evaluate: FR4 failed (no exact terminal update expression)")
        sys.exit(1)

    # ---------------- SR1-SR4 (private substantive checks) ----------------
    sr1_pass, sr1_reason = sr_checks.check_sr1(candidates, real_regs)
    record("SR1", sr1_pass, sr1_reason)

    sr2_pass, sr2_reason = sr_checks.check_sr2(candidates)
    record("SR2", sr2_pass, sr2_reason)

    sr3_pass, sr3_reason = sr_checks.check_sr3(candidates)
    record("SR3", sr3_pass, sr3_reason)

    sr4_pass, sr4_reason = sr_checks.check_sr4(candidates)
    record("SR4", sr4_pass, sr4_reason)

    # ---------------- Final verdict ----------------
    all_passed = all(p for (_, p, _) in results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()