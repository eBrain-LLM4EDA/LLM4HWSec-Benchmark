#!/usr/bin/env python3
"""
evaluation/evaluate.py

Grades submission/trojan_report.json (the participant's hardware-trojan
analysis report) against the hidden ground truth for the bus_arbiter.v
denial-of-service FSM trojan task.

This script does NOT modify or require modification of inputs/bus_arbiter.v.
It reads that file only to confirm it is present (the RTL under analysis is
a fixed reference artifact). All PASS/FAIL verdicts are computed by grading
the content of submission/trojan_report.json.

Requirement IDs checked, in order: FR1, FR2, FR3, FR4, SR1, SR2, SR3, SR4.
"""

import os
import re
import sys
import json
import importlib.util

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(THIS_DIR, os.pardir))

ORDER = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]


def load_ground_truth():
    gt_path = os.path.join(THIS_DIR, "private", "ground_truth.py")
    if not os.path.isfile(gt_path):
        print("[TEST] FAIL: SETUP: evaluation/private/ground_truth.py not found")
        sys.exit(1)
    try:
        spec = importlib.util.spec_from_file_location("ground_truth", gt_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"[TEST] FAIL: SETUP: failed to load evaluation/private/ground_truth.py: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# FR checks
# ---------------------------------------------------------------------------

def check_fr1(report):
    if not isinstance(report, dict):
        return False, "top-level JSON is not an object"
    candidates = report.get("candidates")
    if not isinstance(candidates, list) or len(candidates) == 0:
        return False, "'candidates' key missing, not an array, or empty"
    oa = report.get("overall_assessment")
    if not isinstance(oa, str):
        return False, "'overall_assessment' missing or not a string"
    rf = report.get("recommended_fix")
    if not isinstance(rf, str):
        return False, "'recommended_fix' missing or not a string"
    return True, ""


def check_fr2(candidates):
    if not isinstance(candidates, list) or len(candidates) == 0:
        return False, "no candidates present to validate"
    required_str_fields = ["state_name", "trigger_condition", "rationale", "impact"]
    for i, c in enumerate(candidates):
        if not isinstance(c, dict):
            return False, f"candidate index {i} is not a JSON object"
        for field in required_str_fields:
            val = c.get(field)
            if not isinstance(val, str) or len(val.strip()) == 0:
                return False, f"candidate index {i} missing/empty field '{field}'"
        conf = c.get("confidence")
        if isinstance(conf, bool) or not isinstance(conf, (int, float)):
            return False, f"candidate index {i} 'confidence' missing or non-numeric"
        if conf < 0.0 or conf > 1.0:
            return False, f"candidate index {i} 'confidence' {conf} out of range [0.0, 1.0]"
    return True, ""


def check_fr3(report):
    if not isinstance(report, dict):
        return False, "report is not a JSON object"
    oa = report.get("overall_assessment")
    if not isinstance(oa, str):
        return False, "'overall_assessment' missing or not a string"
    stripped = oa.strip()
    if len(stripped) <= 15:
        return False, "'overall_assessment' is too short/trivial to be substantive"
    if not re.search(r'\b(yes|no)\b', stripped, re.IGNORECASE):
        return False, "'overall_assessment' does not contain an explicit yes/no answer token"
    return True, ""


def check_fr4(candidates):
    if not isinstance(candidates, list) or len(candidates) == 0:
        return False, "no candidates present to ground in literal RTL constructs"

    # These state/signal names are literally present in inputs/bus_arbiter.v,
    # which is visible to participants as the artifact under analysis.
    state_names = ["IDLE", "GRANT0", "GRANT1", "GRANT2", "GRANT3", "STATE5"]
    signal_names = ["req", "gnt", "busy", "rst_n"]

    state_pattern = re.compile(r'\b(' + '|'.join(state_names) + r')\b', re.IGNORECASE)
    signal_pattern = re.compile(r'\b(' + '|'.join(signal_names) + r')\b', re.IGNORECASE)
    concrete_pattern = re.compile(r"(4'b|0b|0x|\[\s*\d+\s*\]|==)", re.IGNORECASE)

    fields = ["state_name", "trigger_condition", "rationale", "impact"]
    for c in candidates:
        if not isinstance(c, dict):
            continue
        text = " ".join(str(c.get(f, "")) for f in fields)
        if state_pattern.search(text) and signal_pattern.search(text) and concrete_pattern.search(text):
            return True, ""
    return False, "no candidate grounds its findings in a literal RTL state name + signal + concrete bit-pattern/selector token"


# ---------------------------------------------------------------------------
# SR checks (use private ground-truth helpers/thresholds)
# ---------------------------------------------------------------------------

def check_sr1(candidates, gt):
    if not isinstance(candidates, list):
        return False, "no candidates present"
    for c in candidates:
        if not isinstance(c, dict):
            continue
        conf = c.get("confidence")
        if isinstance(conf, bool) or not isinstance(conf, (int, float)):
            continue
        if conf < gt.CONFIDENCE_THRESHOLD:
            continue
        try:
            hidden_ok = gt.matches_hidden_state(c)
            legit_only = gt.is_legit_state_only(c)
        except Exception:
            hidden_ok = False
            legit_only = True
        if hidden_ok and not legit_only:
            return True, ""
    return False, "no candidate with sufficient confidence correctly identifies the hidden sink state distinct from legitimate IDLE/GRANT0-3 states"


def check_sr2(candidates, gt):
    if not isinstance(candidates, list):
        return False, "no candidates present"
    for c in candidates:
        if not isinstance(c, dict):
            continue
        conf = c.get("confidence")
        if isinstance(conf, bool) or not isinstance(conf, (int, float)):
            continue
        if conf < gt.CONFIDENCE_THRESHOLD:
            continue
        try:
            trigger_ok = gt.matches_trigger(c)
        except Exception:
            trigger_ok = False
        if trigger_ok:
            return True, ""
    return False, "no sufficiently-confident candidate correctly ties the trigger to the GRANT2-origin req=4'b1011 bit pattern"


def check_sr3(report):
    if not isinstance(report, dict):
        return False, "report is not a JSON object"
    oa = report.get("overall_assessment")
    if not isinstance(oa, str):
        return False, "'overall_assessment' missing or not a string"
    text = oa.strip().lower()
    for m in re.finditer(r'\byes\b', text):
        start = m.start()
        preceding = text[max(0, start - 12):start]
        if re.search(r'\b(not|no)\s*$', preceding):
            continue
        return True, ""
    return False, "'overall_assessment' does not give an unhedged affirmative 'yes' answer to the permanent-DoS question"


def check_sr4(sr1_pass, sr2_pass, sr3_pass):
    if sr1_pass and sr2_pass and sr3_pass:
        return True, ""
    failed = []
    if not sr1_pass:
        failed.append("SR1")
    if not sr2_pass:
        failed.append("SR2")
    if not sr3_pass:
        failed.append("SR3")
    return False, "aggregate gate failed because " + ", ".join(failed) + " did not pass"


def main():
    gt = load_ground_truth()

    rtl_path = os.path.join(REPO_ROOT, "inputs", "bus_arbiter.v")
    if not os.path.isfile(rtl_path):
        print("[TEST] FAIL: SETUP: inputs/bus_arbiter.v not found")
        sys.exit(1)

    sub_path = os.path.join(REPO_ROOT, "submission", "trojan_report.json")
    if not os.path.isfile(sub_path):
        print("[TEST] FAIL: SETUP: submission/trojan_report.json not found")
        sys.exit(1)

    try:
        with open(sub_path, "r") as f:
            raw = f.read()
    except Exception as e:
        print(f"[TEST] FAIL: SETUP: could not read submission/trojan_report.json: {e}")
        sys.exit(1)

    report = None
    parse_error = None
    try:
        report = json.loads(raw)
    except Exception as e:
        parse_error = str(e)

    if parse_error is not None:
        reason = f"submission/trojan_report.json is not valid JSON: {parse_error}"
        for rid in ORDER:
            print(f"[TEST] FAIL: {rid}: {reason}")
        sys.exit(1)

    candidates = report.get("candidates") if isinstance(report, dict) else None
    if not isinstance(candidates, list):
        candidates = []

    fr1_pass, fr1_reason = check_fr1(report)
    fr2_pass, fr2_reason = check_fr2(candidates)
    fr3_pass, fr3_reason = check_fr3(report)
    fr4_pass, fr4_reason = check_fr4(candidates)

    sr1_pass, sr1_reason = check_sr1(candidates, gt)
    sr2_pass, sr2_reason = check_sr2(candidates, gt)
    sr3_pass, sr3_reason = check_sr3(report)
    sr4_pass, sr4_reason = check_sr4(sr1_pass, sr2_pass, sr3_pass)

    results = [
        ("FR1", fr1_pass, fr1_reason),
        ("FR2", fr2_pass, fr2_reason),
        ("FR3", fr3_pass, fr3_reason),
        ("FR4", fr4_pass, fr4_reason),
        ("SR1", sr1_pass, sr1_reason),
        ("SR2", sr2_pass, sr2_reason),
        ("SR3", sr3_pass, sr3_reason),
        ("SR4", sr4_pass, sr4_reason),
    ]

    all_pass = True
    for rid, ok, reason in results:
        if ok:
            print(f"[TEST] PASS: {rid}")
        else:
            print(f"[TEST] FAIL: {rid}: {reason}")
            all_pass = False

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()