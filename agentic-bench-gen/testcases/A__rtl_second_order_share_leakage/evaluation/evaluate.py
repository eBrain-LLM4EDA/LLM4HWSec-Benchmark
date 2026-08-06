import json
import os
import sys

# Hidden ground truth (must not be revealed to participants)
GROUND_TRUTH_PAIR = {"share0_stage2_q", "share1_stage2_q"}
GROUND_TRUTH_ALIGNMENT_KEYWORDS = ["same clock cycle", "same cycle", "simultaneously", "joint transition", "both registers update"]
GROUND_TRUTH_SECOND_ORDER_LEAKING = True

def emit(requirement_id, passed, reason=None):
    if passed:
        print(f"[TEST] PASS: {requirement_id}")
    else:
        msg = f"[TEST] FAIL: {requirement_id}"
        if reason:
            msg += f": {reason}"
        print(msg)

def main():
    all_passed = True

    # Check submission file existence
    submission_path = os.path.join("submission", "vulnerability_report.json")
    if not os.path.isfile(submission_path):
        emit("FR1", False, "submission/vulnerability_report.json not found")
        emit("FR2", False, "submission/vulnerability_report.json not found")
        emit("FR3", False, "submission/vulnerability_report.json not found")
        emit("FR4", False, "submission/vulnerability_report.json not found")
        emit("SR1", False, "submission/vulnerability_report.json not found")
        emit("SR2", False, "submission/vulnerability_report.json not found")
        emit("SR3", False, "submission/vulnerability_report.json not found")
        sys.exit(1)

    # FR1: Valid JSON
    try:
        with open(submission_path, "r") as f:
            report = json.load(f)
        emit("FR1", True)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        emit("FR1", False, f"JSON parse error: {e}")
        # Cannot proceed with further checks if JSON is invalid
        emit("FR2", False, "cannot check due to FR1 failure")
        emit("FR3", False, "cannot check due to FR1 failure")
        emit("FR4", False, "cannot check due to FR1 failure")
        emit("SR1", False, "cannot check due to FR1 failure")
        emit("SR2", False, "cannot check due to FR1 failure")
        emit("SR3", False, "cannot check due to FR1 failure")
        sys.exit(1)

    # FR2: leaking_register_pair field
    pair = report.get("leaking_register_pair")
    if not isinstance(pair, list) or len(pair) != 2 or not all(isinstance(r, str) for r in pair):
        emit("FR2", False, "leaking_register_pair must be an array of exactly two strings")
        all_passed = False
    else:
        # Optional: validate that the register names exist in the RTL (cross-check with inputs/masked_datapath.v)
        rtl_path = os.path.join("inputs", "masked_datapath.v")
        if os.path.isfile(rtl_path):
            with open(rtl_path, "r") as f:
                rtl_content = f.read()
            missing = [r for r in pair if r not in rtl_content]
            if missing:
                emit("FR2", False, f"register names not found in RTL: {missing}")
                all_passed = False
            else:
                emit("FR2", True)
        else:
            # If RTL file is missing (should not happen in normal operation), skip the cross-check
            emit("FR2", True)

    # FR3: first_order_analysis array
    first_order = report.get("first_order_analysis")
    if not isinstance(first_order, list):
        emit("FR3", False, "first_order_analysis must be an array")
        all_passed = False
    else:
        # Check that at least the two registers from the leaking pair are present with boolean safe fields
        if isinstance(pair, list) and len(pair) == 2:
            reg_names = set(pair)
            found = set()
            for entry in first_order:
                if isinstance(entry, dict) and "register" in entry and "safe" in entry:
                    if entry["register"] in reg_names and isinstance(entry["safe"], bool):
                        found.add(entry["register"])
            if reg_names.issubset(found):
                emit("FR3", True)
            else:
                missing_regs = reg_names - found
                emit("FR3", False, f"first_order_analysis missing required entries for registers: {missing_regs}")
                all_passed = False
        else:
            # If FR2 failed, we still check structure minimally
            if all(isinstance(e, dict) and "register" in e and "safe" in e and isinstance(e["safe"], bool) for e in first_order):
                emit("FR3", True)
            else:
                emit("FR3", False, "first_order_analysis entries must have register (string) and safe (boolean) fields")
                all_passed = False

    # FR4: second_order_analysis object
    second_order = report.get("second_order_analysis")
    if not isinstance(second_order, dict):
        emit("FR4", False, "second_order_analysis must be an object")
        all_passed = False
    else:
        leaking = second_order.get("leaking")
        explanation = second_order.get("explanation")
        if not isinstance(leaking, bool):
            emit("FR4", False, "second_order_analysis.leaking must be a boolean")
            all_passed = False
        elif not isinstance(explanation, str) or len(explanation.strip()) == 0:
            emit("FR4", False, "second_order_analysis.explanation must be a non-empty string")
            all_passed = False
        else:
            emit("FR4", True)

    # SR1: Correct leaking register pair
    if isinstance(pair, list) and len(pair) == 2:
        if set(pair) == GROUND_TRUTH_PAIR:
            emit("SR1", True)
        else:
            emit("SR1", False, f"expected {GROUND_TRUTH_PAIR}, got {set(pair)}")
            all_passed = False
    else:
        emit("SR1", False, "leaking_register_pair not valid (FR2 must pass first)")
        all_passed = False

    # SR2: Both registers appear safe under first-order analysis
    if isinstance(first_order, list):
        safe_regs = set()
        for entry in first_order:
            if isinstance(entry, dict) and entry.get("safe") is True:
                safe_regs.add(entry.get("register"))
        if GROUND_TRUTH_PAIR.issubset(safe_regs):
            emit("SR2", True)
        else:
            missing_safe = GROUND_TRUTH_PAIR - safe_regs
            emit("SR2", False, f"registers not marked safe: {missing_safe}")
            all_passed = False
    else:
        emit("SR2", False, "first_order_analysis not valid (FR3 must pass first)")
        all_passed = False

    # SR3: Alignment condition and second-order leakage
    alignment = report.get("alignment_condition")
    if not isinstance(alignment, str) or len(alignment.strip()) == 0:
        emit("SR3", False, "alignment_condition must be a non-empty string")
        all_passed = False
    else:
        # Check that alignment description contains keywords indicating temporal alignment
        alignment_lower = alignment.lower()
        if any(kw in alignment_lower for kw in GROUND_TRUTH_ALIGNMENT_KEYWORDS):
            # Also check second_order_analysis.leaking is true
            if isinstance(second_order, dict) and second_order.get("leaking") is True:
                emit("SR3", True)
            else:
                emit("SR3", False, "second_order_analysis.leaking must be true")
                all_passed = False
        else:
            emit("SR3", False, "alignment_condition does not describe the required temporal alignment")
            all_passed = False

    if all_passed:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()