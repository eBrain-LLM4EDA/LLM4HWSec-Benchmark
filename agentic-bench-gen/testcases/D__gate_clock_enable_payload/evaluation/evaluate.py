import json
import sys
import os

# Import hidden ground truth
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'private'))
from ground_truth import EXPECTED_TROJAN_DETECTED, EXPECTED_SUSPECT_NODES

def main():
    submission_path = os.path.join('submission', 'trojan_report.json')
    all_pass = True

    # FR1: File exists and is valid JSON
    if not os.path.exists(submission_path):
        print("[TEST] FAIL: FR1: submission/trojan_report.json not found")
        all_pass = False
    else:
        try:
            with open(submission_path, 'r') as f:
                data = json.load(f)
            print("[TEST] PASS: FR1")
        except json.JSONDecodeError as e:
            print(f"[TEST] FAIL: FR1: invalid JSON: {e}")
            all_pass = False
            # Cannot continue with other checks if JSON is invalid
            sys.exit(1)

    # FR2: 'trojan_detected' must be a boolean
    if 'trojan_detected' not in data:
        print("[TEST] FAIL: FR2: missing 'trojan_detected' field")
        all_pass = False
    elif not isinstance(data['trojan_detected'], bool):
        print(f"[TEST] FAIL: FR2: 'trojan_detected' must be boolean, got {type(data['trojan_detected']).__name__}")
        all_pass = False
    else:
        print("[TEST] PASS: FR2")

    # FR3: 'suspect_nodes' must be a list of strings
    if 'suspect_nodes' not in data:
        print("[TEST] FAIL: FR3: missing 'suspect_nodes' field")
        all_pass = False
    elif not isinstance(data['suspect_nodes'], list):
        print(f"[TEST] FAIL: FR3: 'suspect_nodes' must be a list, got {type(data['suspect_nodes']).__name__}")
        all_pass = False
    else:
        all_strings = all(isinstance(node, str) for node in data['suspect_nodes'])
        if not all_strings:
            print("[TEST] FAIL: FR3: 'suspect_nodes' must contain only strings")
            all_pass = False
        else:
            print("[TEST] PASS: FR3")

    # If any FR failed, we may still attempt SR checks if data is usable
    # SR1: suspect_nodes must contain the trigger cone output net
    if 'suspect_nodes' in data and isinstance(data['suspect_nodes'], list):
        suspect_nodes = data['suspect_nodes']
        if EXPECTED_SUSPECT_NODES[0] in suspect_nodes:
            print("[TEST] PASS: SR1")
        else:
            print(f"[TEST] FAIL: SR1: missing trigger node '{EXPECTED_SUSPECT_NODES[0]}'")
            all_pass = False

        # SR2: suspect_nodes must contain the payload gate
        if EXPECTED_SUSPECT_NODES[1] in suspect_nodes:
            print("[TEST] PASS: SR2")
        else:
            print(f"[TEST] FAIL: SR2: missing payload node '{EXPECTED_SUSPECT_NODES[1]}'")
            all_pass = False
    else:
        # If suspect_nodes is missing or not a list, SR checks cannot pass
        print("[TEST] FAIL: SR1: cannot check, suspect_nodes invalid")
        print("[TEST] FAIL: SR2: cannot check, suspect_nodes invalid")
        all_pass = False

    if all_pass:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()