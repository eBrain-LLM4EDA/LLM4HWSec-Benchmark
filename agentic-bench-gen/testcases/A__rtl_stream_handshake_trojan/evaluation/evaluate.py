import json
import sys
import os

def main():
    results = {}
    all_pass = True

    # --- FR1: Valid JSON ---
    submission_path = os.path.join("submission", "trojan_report.json")
    if not os.path.exists(submission_path):
        print("[TEST] FAIL: SETUP: submission/trojan_report.json not found")
        sys.exit(1)

    try:
        with open(submission_path, "r") as f:
            report = json.load(f)
        print("[TEST] PASS: FR1")
        results["FR1"] = True
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[TEST] FAIL: FR1: invalid JSON - {e}")
        results["FR1"] = False
        all_pass = False
        # Cannot continue with other checks if JSON is invalid
        sys.exit(1)

    # --- FR2: Required fields ---
    required_fields = ["trojan_present", "trigger_condition", "payload_effect",
                       "trigger_signals", "payload_signals", "confidence"]
    missing = [f for f in required_fields if f not in report]
    if missing:
        for field in missing:
            print(f"[TEST] FAIL: FR2: missing field {field}")
        results["FR2"] = False
        all_pass = False
    else:
        print("[TEST] PASS: FR2")
        results["FR2"] = True

    # --- FR3: Confidence range ---
    confidence = report.get("confidence")
    if isinstance(confidence, (int, float)) and 0.0 <= confidence <= 1.0:
        print("[TEST] PASS: FR3")
        results["FR3"] = True
    else:
        print(f"[TEST] FAIL: FR3: confidence out of range or not a number (got {confidence})")
        results["FR3"] = False
        all_pass = False

    # --- Load ground truth ---
    gt_path = os.path.join("evaluation", "private", "ground_truth.json")
    if not os.path.exists(gt_path):
        print("[TEST] FAIL: SETUP: evaluation/private/ground_truth.json not found")
        sys.exit(1)

    with open(gt_path, "r") as f:
        ground_truth = json.load(f)

    # --- SR1: Trigger identification ---
    sr1_pass = True
    # Check trojan_present
    if report.get("trojan_present") != ground_truth.get("trojan_present"):
        print(f"[TEST] FAIL: SR1: trojan_present mismatch (expected {ground_truth.get('trojan_present')}, got {report.get('trojan_present')})")
        sr1_pass = False
    else:
        # Check trigger_condition contains key pattern
        submitted_cond = report.get("trigger_condition", "")
        if "1011" not in submitted_cond:
            print("[TEST] FAIL: SR1: trigger_condition does not contain '1011'")
            sr1_pass = False
        elif "valid" not in submitted_cond.lower() or "ready" not in submitted_cond.lower():
            print("[TEST] FAIL: SR1: trigger_condition does not mention valid-ready handshake")
            sr1_pass = False
        else:
            # Check trigger_signals exact match
            submitted_trig = set(report.get("trigger_signals", []))
            expected_trig = set(ground_truth.get("trigger_signals", []))
            if submitted_trig != expected_trig:
                missing_trig = expected_trig - submitted_trig
                extra_trig = submitted_trig - expected_trig
                msg = "trigger_signals mismatch"
                if missing_trig:
                    msg += f"; missing: {missing_trig}"
                if extra_trig:
                    msg += f"; unexpected: {extra_trig}"
                print(f"[TEST] FAIL: SR1: {msg}")
                sr1_pass = False

    if sr1_pass:
        print("[TEST] PASS: SR1")
        results["SR1"] = True
    else:
        results["SR1"] = False
        all_pass = False

    # --- SR2: Payload identification ---
    sr2_pass = True
    # Check payload_effect describes dropping transfer by forcing m_valid low
    submitted_effect = report.get("payload_effect", "").lower()
    if "drop" not in submitted_effect and "suppress" not in submitted_effect and "force" not in submitted_effect:
        print("[TEST] FAIL: SR2: payload_effect does not describe dropping/suppressing a transfer")
        sr2_pass = False
    elif "m_valid" not in submitted_effect and "valid" not in submitted_effect:
        print("[TEST] FAIL: SR2: payload_effect does not mention m_valid or valid signal")
        sr2_pass = False
    else:
        # Check payload_signals exact match
        submitted_pay = set(report.get("payload_signals", []))
        expected_pay = set(ground_truth.get("payload_signals", []))
        if submitted_pay != expected_pay:
            missing_pay = expected_pay - submitted_pay
            extra_pay = submitted_pay - expected_pay
            msg = "payload_signals mismatch"
            if missing_pay:
                msg += f"; missing: {missing_pay}"
            if extra_pay:
                msg += f"; unexpected: {extra_pay}"
            print(f"[TEST] FAIL: SR2: {msg}")
            sr2_pass = False

    if sr2_pass:
        print("[TEST] PASS: SR2")
        results["SR2"] = True
    else:
        results["SR2"] = False
        all_pass = False

    if all_pass:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()