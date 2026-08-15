import json
import os
import sys

SUBMISSION_PATH = "submission/trojan_report.json"
UART_TX_PATH = "inputs/uart_tx.v"


def main():
    private_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "private")
    sys.path.insert(0, private_dir)

    try:
        import grader
        import grader_sr
    except Exception as e:
        print("[TEST] FAIL: SETUP: could not import grading modules from evaluation/private/: {}".format(e))
        sys.exit(1)

    # --- Harness self-check (NOT a grading step): confirm the ground-truth
    # anchors this harness relies on are actually present in the shipped
    # reference RTL. This guards against harness/ground-truth drift; it does
    # not evaluate the submission itself.
    if not os.path.isfile(UART_TX_PATH):
        print("[TEST] FAIL: SETUP: {} not found".format(UART_TX_PATH))
        sys.exit(1)

    try:
        with open(UART_TX_PATH, "r") as f:
            rtl_text = f.read()
    except Exception as e:
        print("[TEST] FAIL: SETUP: could not read {}: {}".format(UART_TX_PATH, e))
        sys.exit(1)

    required_anchors = ["key_shadow_reg", "status_dbg", "tx_data[7]", "tx_start"]
    missing_anchors = [a for a in required_anchors if a not in rtl_text]
    if missing_anchors:
        print(
            "[TEST] FAIL: SETUP: harness ground-truth anchors not found in {}: {}".format(
                UART_TX_PATH, missing_anchors
            )
        )
        sys.exit(1)

    # --- Load the participant's submission ---
    if not os.path.isfile(SUBMISSION_PATH):
        print("[TEST] FAIL: SETUP: {} not found".format(SUBMISSION_PATH))
        sys.exit(1)

    report = None
    parse_error = None
    try:
        with open(SUBMISSION_PATH, "r") as f:
            report = json.load(f)
    except Exception as e:
        parse_error = str(e)

    order = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]

    checks = {
        "FR1": grader.check_fr1,
        "FR2": grader.check_fr2,
        "FR3": grader.check_fr3,
        "FR4": grader.check_fr4,
        "SR1": grader_sr.check_sr1,
        "SR2": grader_sr.check_sr2,
        "SR3": grader_sr.check_sr3,
        "SR4": grader_sr.check_sr4,
    }

    all_passed = True
    for rid in order:
        if parse_error is not None:
            passed = False
            reason = "submission JSON could not be parsed: {}".format(parse_error)
        else:
            try:
                passed, reason = checks[rid](report)
            except Exception as e:
                passed = False
                reason = "grader raised exception while checking {}: {}".format(rid, e)

        if passed:
            print("[TEST] PASS: {}".format(rid))
        else:
            print("[TEST] FAIL: {}: {}".format(rid, reason))
            all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()