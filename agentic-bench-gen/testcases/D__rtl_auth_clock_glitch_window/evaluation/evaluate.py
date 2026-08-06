import json
import os
import sys
import re

# Fix import path so that 'from private.ground_truth import ...' works
# when evaluate.py is executed from the work directory.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from private.ground_truth import GROUND_TRUTH_CYCLE, GROUND_TRUTH_STATE_REG, GROUND_TRUTH_RESULT_REG, extract_signal_names

def main():
    submission_path = "submission/vulnerability_report.json"
    if not os.path.exists(submission_path):
        print("[TEST] FAIL: SETUP: submission/vulnerability_report.json not found")
        sys.exit(1)

    # FR1: valid JSON parseable
    try:
        with open(submission_path, "r") as f:
            report = json.load(f)
        print("[TEST] PASS: FR1")
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[TEST] FAIL: FR1: submission is not valid JSON: {e}")
        # Cannot continue without parsed report, fail remaining and exit
        for req in ["FR2", "FR3", "FR4", "SR1", "SR2"]:
            print(f"[TEST] FAIL: {req}: cannot evaluate due to FR1 failure")
        sys.exit(1)

    # FR2: vulnerable_cycle is an integer
    if "vulnerable_cycle" not in report or not isinstance(report["vulnerable_cycle"], int):
        print("[TEST] FAIL: FR2: vulnerable_cycle must be an integer")
    else:
        print("[TEST] PASS: FR2")

    # FR3: state_register and result_register are strings matching signal names in auth_fsm.v
    try:
        signal_names = extract_signal_names("inputs/auth_fsm.v")
    except Exception as e:
        print(f"[TEST] FAIL: FR3: cannot extract signal names from auth_fsm.v: {e}")
        signal_names = set()  # empty set so subsequent checks will fail appropriately

    state_reg = report.get("state_register")
    result_reg = report.get("result_register")
    if not isinstance(state_reg, str) or not isinstance(result_reg, str):
        print("[TEST] FAIL: FR3: registers must name signals in auth_fsm.v")
    elif state_reg not in signal_names or result_reg not in signal_names:
        print("[TEST] FAIL: FR3: registers must name signals in auth_fsm.v")
    else:
        print("[TEST] PASS: FR3")

    # FR4: explanation is a non-empty string
    explanation = report.get("explanation")
    if not isinstance(explanation, str) or len(explanation.strip()) == 0:
        print("[TEST] FAIL: FR4: explanation must be a non-empty string")
    else:
        print("[TEST] PASS: FR4")

    # SR1: vulnerable_cycle equals ground truth cycle index
    if report.get("vulnerable_cycle") == GROUND_TRUTH_CYCLE:
        print("[TEST] PASS: SR1")
    else:
        print("[TEST] FAIL: SR1: vulnerable_cycle does not match ground truth")

    # SR2: state_register equals 'state_q' and result_register equals 'auth_result_q'
    if report.get("state_register") == GROUND_TRUTH_STATE_REG and report.get("result_register") == GROUND_TRUTH_RESULT_REG:
        print("[TEST] PASS: SR2")
    else:
        print("[TEST] FAIL: SR2: register names do not match ground truth")

    # Compute metrics
    # leakage_detection_accuracy: proportion of correctly identified vulnerable registers and cycles
    # For this task, the ground truth set is {vulnerable_cycle=2, state_register='state_q', result_register='auth_result_q'}
    # We count how many of these three items are correctly reported.
    correct_items = 0
    total_items = 3
    if report.get("vulnerable_cycle") == GROUND_TRUTH_CYCLE:
        correct_items += 1
    if report.get("state_register") == GROUND_TRUTH_STATE_REG:
        correct_items += 1
    if report.get("result_register") == GROUND_TRUTH_RESULT_REG:
        correct_items += 1
    leakage_detection_accuracy = correct_items / total_items

    # fault_coverage: whether the reported vulnerability covers the critical fault injection point
    # The critical point is the cycle where state transitions from COMPARE to DECIDE (cycle 2).
    # We consider it covered if vulnerable_cycle matches the ground truth.
    fault_coverage = 1.0 if report.get("vulnerable_cycle") == GROUND_TRUTH_CYCLE else 0.0

    # hardening_precision: precision of hardening suggestions derived from the vulnerability report.
    # Since the submission is only a vulnerability report (no explicit hardening suggestions),
    # we interpret this as the precision of the report itself: ratio of correct fields to total fields.
    # Total fields checked: vulnerable_cycle, state_register, result_register, explanation (non-empty).
    # Correct fields: those that satisfy their respective requirements.
    total_fields = 4
    correct_fields = 0
    if "vulnerable_cycle" in report and isinstance(report["vulnerable_cycle"], int) and report["vulnerable_cycle"] == GROUND_TRUTH_CYCLE:
        correct_fields += 1
    if isinstance(state_reg, str) and state_reg == GROUND_TRUTH_STATE_REG:
        correct_fields += 1
    if isinstance(result_reg, str) and result_reg == GROUND_TRUTH_RESULT_REG:
        correct_fields += 1
    if isinstance(explanation, str) and len(explanation.strip()) > 0:
        correct_fields += 1
    hardening_precision = correct_fields / total_fields

    # Print metrics
    print(f"METRIC: leakage_detection_accuracy={leakage_detection_accuracy:.4f}")
    print(f"METRIC: fault_coverage={fault_coverage:.4f}")
    print(f"METRIC: hardening_precision={hardening_precision:.4f}")

    # Determine exit code
    all_pass = True
    # FR1 already passed if we got here
    if not ("vulnerable_cycle" in report and isinstance(report["vulnerable_cycle"], int)):
        all_pass = False
    if not (isinstance(state_reg, str) and isinstance(result_reg, str) and state_reg in signal_names and result_reg in signal_names):
        all_pass = False
    if not (isinstance(explanation, str) and len(explanation.strip()) > 0):
        all_pass = False
    if report.get("vulnerable_cycle") != GROUND_TRUTH_CYCLE:
        all_pass = False
    if report.get("state_register") != GROUND_TRUTH_STATE_REG or report.get("result_register") != GROUND_TRUTH_RESULT_REG:
        all_pass = False

    if all_pass:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()