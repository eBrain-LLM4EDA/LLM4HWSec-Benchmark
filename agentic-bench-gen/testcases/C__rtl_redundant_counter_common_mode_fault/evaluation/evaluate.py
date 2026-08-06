import json
import sys
import os

# Hidden ground truth
EXPECTED_COMMON_MODE_NODE = "shared_count_en"
EXPECTED_FAILURE_KEYWORDS = [
    "both counters stall",
    "counters remain equal",
    "timeout prevented",
    "timeout never asserts",
    "equality monitor remains satisfied"
]

def check_fr1(submission_path):
    """FR1: submission/vulnerability_report.json exists and is valid JSON."""
    if not os.path.isfile(submission_path):
        print("[TEST] FAIL: FR1: submission/vulnerability_report.json not found")
        return False, None
    try:
        with open(submission_path, 'r') as f:
            data = json.load(f)
        print("[TEST] PASS: FR1")
        return True, data
    except json.JSONDecodeError as e:
        print(f"[TEST] FAIL: FR1: invalid JSON: {e}")
        return False, None
    except Exception as e:
        print(f"[TEST] FAIL: FR1: could not read file: {e}")
        return False, None

def check_fr2(data):
    """FR2: common_mode_node field is present and non-empty string."""
    if data is None:
        return False
    node = data.get("common_mode_node")
    if isinstance(node, str) and node.strip():
        print("[TEST] PASS: FR2")
        return True
    else:
        print("[TEST] FAIL: FR2: common_mode_node missing, null, or empty")
        return False

def check_fr3(data):
    """FR3: failure_mechanism field is present and non-empty string."""
    if data is None:
        return False
    mech = data.get("failure_mechanism")
    if isinstance(mech, str) and mech.strip():
        print("[TEST] PASS: FR3")
        return True
    else:
        print("[TEST] FAIL: FR3: failure_mechanism missing, null, or empty")
        return False

def check_sr1(data):
    """SR1: common_mode_node matches shared enable signal (bare or hierarchical)."""
    if data is None:
        return False
    node = data.get("common_mode_node", "").strip()
    # Accept bare name or any hierarchical name ending with .shared_count_en
    if node == EXPECTED_COMMON_MODE_NODE or node.endswith("." + EXPECTED_COMMON_MODE_NODE):
        print("[TEST] PASS: SR1")
        return True
    else:
        print(f"[TEST] FAIL: SR1: expected '{EXPECTED_COMMON_MODE_NODE}' or hierarchical name ending with '.{EXPECTED_COMMON_MODE_NODE}', got '{node}'")
        return False

def check_sr2(data):
    """SR2: failure_mechanism describes fault stalling both counters and preventing timeout."""
    if data is None:
        return False
    mech = data.get("failure_mechanism", "").lower()
    # Check for presence of at least one key phrase
    found_keywords = [kw for kw in EXPECTED_FAILURE_KEYWORDS if kw in mech]
    if len(found_keywords) >= 1:
        print("[TEST] PASS: SR2")
        return True
    else:
        print(f"[TEST] FAIL: SR2: failure_mechanism does not adequately describe the fault effect (found keywords: {found_keywords})")
        return False

def main():
    submission_path = "submission/vulnerability_report.json"
    
    # FR1 must pass to continue with content checks
    fr1_ok, data = check_fr1(submission_path)
    if not fr1_ok:
        # If FR1 fails, we cannot check other requirements meaningfully,
        # but we still emit FAIL markers for them to ensure baseline fails.
        print("[TEST] FAIL: FR2: cannot check due to FR1 failure")
        print("[TEST] FAIL: FR3: cannot check due to FR1 failure")
        print("[TEST] FAIL: SR1: cannot check due to FR1 failure")
        print("[TEST] FAIL: SR2: cannot check due to FR1 failure")
        sys.exit(1)
    
    results = []
    results.append(check_fr2(data))
    results.append(check_fr3(data))
    results.append(check_sr1(data))
    results.append(check_sr2(data))
    
    if all(results):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()