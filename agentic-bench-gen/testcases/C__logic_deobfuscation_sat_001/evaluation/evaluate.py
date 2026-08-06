import json
import os
import sys

def main():
    submission_path = os.path.join("submission", "recovered_key.json")
    all_pass = True

    # FR1: File exists and is valid JSON
    if not os.path.isfile(submission_path):
        print("[TEST] FAIL: FR1: submission/recovered_key.json not found")
        all_pass = False
        # Cannot continue without the file
        sys.exit(1)
    try:
        with open(submission_path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[TEST] FAIL: FR1: invalid JSON: {e}")
        all_pass = False
        sys.exit(1)
    except Exception as e:
        print(f"[TEST] FAIL: FR1: could not read file: {e}")
        all_pass = False
        sys.exit(1)
    print("[TEST] PASS: FR1")

    # FR2: Required fields with correct types
    required_fields = {
        "locked": bool,
        "key_bits": str,
        "key_gates": list
    }
    fr2_pass = True
    for field, expected_type in required_fields.items():
        if field not in data:
            print(f"[TEST] FAIL: FR2: missing field '{field}'")
            fr2_pass = False
        elif not isinstance(data[field], expected_type):
            print(f"[TEST] FAIL: FR2: field '{field}' has wrong type (expected {expected_type.__name__}, got {type(data[field]).__name__})")
            fr2_pass = False
    if fr2_pass:
        print("[TEST] PASS: FR2")
    else:
        all_pass = False

    # Extract values for further checks
    locked = data.get("locked")
    key_bits = data.get("key_bits")
    key_gates = data.get("key_gates")

    # FR3: If locked is false, key_bits must be empty string and key_gates must be empty array
    if locked is False:
        fr3_pass = True
        if key_bits != "":
            print(f"[TEST] FAIL: FR3: locked is false but key_bits is not empty (got '{key_bits}')")
            fr3_pass = False
        if key_gates != []:
            print(f"[TEST] FAIL: FR3: locked is false but key_gates is not empty (got {key_gates})")
            fr3_pass = False
        if fr3_pass:
            print("[TEST] PASS: FR3")
        else:
            all_pass = False
    else:
        # FR3 only applies when locked is false; if locked is true, we skip FR3 (or treat as not applicable)
        # According to spec, FR3 is a constraint that must hold when locked is false.
        # If locked is true, the constraint is vacuously satisfied.
        print("[TEST] PASS: FR3")

    # FR4: If locked is true, key_bits must be non-empty binary string and key_gates must be non-empty array of strings
    if locked is True:
        fr4_pass = True
        if not isinstance(key_bits, str) or key_bits == "":
            print(f"[TEST] FAIL: FR4: locked is true but key_bits is empty or not a string")
            fr4_pass = False
        elif not all(c in "01" for c in key_bits):
            print(f"[TEST] FAIL: FR4: key_bits contains non-binary characters (got '{key_bits}')")
            fr4_pass = False
        if not isinstance(key_gates, list) or len(key_gates) == 0:
            print(f"[TEST] FAIL: FR4: locked is true but key_gates is empty or not a list")
            fr4_pass = False
        else:
            if not all(isinstance(g, str) for g in key_gates):
                print(f"[TEST] FAIL: FR4: key_gates contains non-string elements")
                fr4_pass = False
        if fr4_pass:
            print("[TEST] PASS: FR4")
        else:
            all_pass = False
    else:
        # FR4 only applies when locked is true; if locked is false, vacuously satisfied
        print("[TEST] PASS: FR4")

    # SR1: key_gates must be empty (no false key gates)
    if isinstance(key_gates, list) and len(key_gates) == 0:
        print("[TEST] PASS: SR1")
    else:
        print(f"[TEST] FAIL: SR1: key_gates is not empty (got {key_gates})")
        all_pass = False

    # SR2: key_bits must be empty (no false key recovery)
    if isinstance(key_bits, str) and key_bits == "":
        print("[TEST] PASS: SR2")
    else:
        print(f"[TEST] FAIL: SR2: key_bits is not empty (got '{key_bits}')")
        all_pass = False

    if all_pass:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()