#!/usr/bin/env python3

import json
import os
import sys
import re

# ----------------------------------------------------------------------
# Helper: read input artifacts
# ----------------------------------------------------------------------
def read_public_key_width():
    path = "inputs/public_key_width.txt"
    if not os.path.exists(path):
        print(f"[TEST] FAIL: SETUP: {path} not found")
        sys.exit(1)
    with open(path, "r") as f:
        content = f.read().strip()
    try:
        return int(content)
    except ValueError:
        print(f"[TEST] FAIL: SETUP: {path} does not contain a valid integer")
        sys.exit(1)

# ----------------------------------------------------------------------
# Main grading logic
# ----------------------------------------------------------------------
def main():
    submission_path = "submission/recovered_key.json"
    if not os.path.exists(submission_path):
        print(f"[TEST] FAIL: FR1: {submission_path} not found")
        sys.exit(1)

    # Read expected key width
    expected_key_width = read_public_key_width()

    # Load submission JSON
    try:
        with open(submission_path, "r") as f:
            submission = json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[TEST] FAIL: FR1: invalid JSON: {e}")
        sys.exit(1)

    # --- FR1: Top-level keys exist ---
    if not isinstance(submission, dict):
        print("[TEST] FAIL: FR1: submission is not a JSON object")
        sys.exit(1)
    if "lock_gates" not in submission or "recovered_key" not in submission:
        print("[TEST] FAIL: FR1: missing required top-level keys 'lock_gates' and/or 'recovered_key'")
        sys.exit(1)
    print("[TEST] PASS: FR1")

    # --- FR2: recovered_key format ---
    recovered_key = submission["recovered_key"]
    if not isinstance(recovered_key, str):
        print("[TEST] FAIL: FR2: recovered_key is not a string")
        sys.exit(1)
    if len(recovered_key) != expected_key_width:
        print(f"[TEST] FAIL: FR2: recovered_key length {len(recovered_key)} != expected {expected_key_width}")
        sys.exit(1)
    if not re.fullmatch(r'[01]+', recovered_key):
        print("[TEST] FAIL: FR2: recovered_key contains characters other than '0' and '1'")
        sys.exit(1)
    print("[TEST] PASS: FR2")

    # --- FR3: lock_gates array structure ---
    lock_gates = submission["lock_gates"]
    if not isinstance(lock_gates, list):
        print("[TEST] FAIL: FR3: lock_gates is not an array")
        sys.exit(1)
    if len(lock_gates) != 4:
        print(f"[TEST] FAIL: FR3: lock_gates array length {len(lock_gates)} != 4")
        sys.exit(1)

    allowed_classifications = {"XOR", "XNOR", "MUX_0", "MUX_1"}
    for i, gate in enumerate(lock_gates):
        if not isinstance(gate, dict):
            print(f"[TEST] FAIL: FR3: lock_gates[{i}] is not an object")
            sys.exit(1)
        if "gate_label" not in gate or not isinstance(gate["gate_label"], str) or gate["gate_label"].strip() == "":
            print(f"[TEST] FAIL: FR3: lock_gates[{i}] missing or invalid gate_label")
            sys.exit(1)
        if "classification" not in gate or gate["classification"] not in allowed_classifications:
            print(f"[TEST] FAIL: FR3: lock_gates[{i}] missing or invalid classification")
            sys.exit(1)
        if "key_bit" not in gate or gate["key_bit"] not in (0, 1):
            print(f"[TEST] FAIL: FR3: lock_gates[{i}] missing or invalid key_bit")
            sys.exit(1)
    print("[TEST] PASS: FR3")

    # --- SR1: Correct classification of each lock gate ---
    # Build a lookup from gate_label to classification
    submitted_gates = {g["gate_label"]: g for g in lock_gates}

    # Import hidden ground truth (private module)
    try:
        from evaluation.private.ground_truth import GROUND_TRUTH_LOCK_GATES
    except ImportError as e:
        print(f"[TEST] FAIL: SETUP: cannot import ground truth: {e}")
        sys.exit(1)

    for gt_gate in GROUND_TRUTH_LOCK_GATES:
        label = gt_gate["gate_label"]
        expected_class = gt_gate["classification"]
        if label not in submitted_gates:
            print(f"[TEST] FAIL: SR1: missing gate_label '{label}' in submission")
            sys.exit(1)
        actual_class = submitted_gates[label]["classification"]
        if actual_class != expected_class:
            print(f"[TEST] FAIL: SR1: gate '{label}' classified as '{actual_class}', expected '{expected_class}'")
            sys.exit(1)
    print("[TEST] PASS: SR1")

    # --- SR2: Correct key recovery ---
    try:
        from evaluation.private.ground_truth import GROUND_TRUTH_KEY
    except ImportError as e:
        print(f"[TEST] FAIL: SETUP: cannot import ground truth: {e}")
        sys.exit(1)

    # Check full recovered_key string
    if recovered_key != GROUND_TRUTH_KEY:
        print(f"[TEST] FAIL: SR2: recovered_key '{recovered_key}' != ground truth '{GROUND_TRUTH_KEY}'")
        sys.exit(1)

    # Check each gate's key_bit
    for gt_gate in GROUND_TRUTH_LOCK_GATES:
        label = gt_gate["gate_label"]
        expected_bit = gt_gate["key_bit"]
        actual_bit = submitted_gates[label]["key_bit"]
        if actual_bit != expected_bit:
            print(f"[TEST] FAIL: SR2: gate '{label}' key_bit {actual_bit} != expected {expected_bit}")
            sys.exit(1)
    print("[TEST] PASS: SR2")

    # All checks passed
    sys.exit(0)

if __name__ == "__main__":
    main()