import json
import os
import re
import sys

# Import hidden ground truth
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'private'))
from ground_truth import GROUND_TRUTH_NET, GROUND_TRUTH_REG, BENIGN_REGISTERS, BENIGN_NETS

def extract_identifiers(verilog_path):
    """Extract wire and reg identifiers from a Verilog file."""
    identifiers = set()
    try:
        with open(verilog_path, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"[TEST] FAIL: SETUP: {verilog_path} not found")
        sys.exit(1)
    
    # Match wire declarations: wire [optional range] name;
    wire_pattern = r'wire\s+(?:\[\d+:\d+\]\s+)?(\w+)\s*;'
    # Match reg declarations: reg [optional range] name;
    reg_pattern = r'reg\s+(?:\[\d+:\d+\]\s+)?(\w+)\s*;'
    
    for match in re.finditer(wire_pattern, content):
        identifiers.add(match.group(1))
    for match in re.finditer(reg_pattern, content):
        identifiers.add(match.group(1))
    
    return identifiers

def main():
    all_passed = True
    
    # Check submission file exists
    submission_path = os.path.join('submission', 'vulnerability_report.json')
    if not os.path.exists(submission_path):
        print(f"[TEST] FAIL: SETUP: {submission_path} not found")
        sys.exit(1)
    
    # FR1: Valid JSON parseable
    try:
        with open(submission_path, 'r') as f:
            report = json.load(f)
        print("[TEST] PASS: FR1")
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[TEST] FAIL: FR1: {str(e)}")
        all_passed = False
        # Cannot continue without valid JSON
        sys.exit(1)
    
    # FR2: Required fields present and non-empty strings
    required_fields = ['recombination_net', 'recombination_register', 'leakage_type']
    fr2_passed = True
    for field in required_fields:
        if field not in report:
            print(f"[TEST] FAIL: FR2: missing field '{field}'")
            fr2_passed = False
        elif not isinstance(report[field], str) or not report[field].strip():
            print(f"[TEST] FAIL: FR2: field '{field}' is empty or not a string")
            fr2_passed = False
    
    if fr2_passed:
        print("[TEST] PASS: FR2")
    else:
        all_passed = False
    
    # Extract identifiers from RTL
    rtl_path = os.path.join('inputs', 'masked_sbox.v')
    identifiers = extract_identifiers(rtl_path)
    
    # FR3: Reported identifiers exist in netlist
    net = report.get('recombination_net', '')
    reg = report.get('recombination_register', '')
    
    fr3_passed = True
    if net not in identifiers:
        print(f"[TEST] FAIL: FR3: recombination_net '{net}' not found in RTL")
        fr3_passed = False
    if reg not in identifiers:
        print(f"[TEST] FAIL: FR3: recombination_register '{reg}' not found in RTL")
        fr3_passed = False
    
    if fr3_passed:
        print("[TEST] PASS: FR3")
    else:
        all_passed = False
    
    # SR1: recombination_net exactly matches ground truth
    if net == GROUND_TRUTH_NET:
        print("[TEST] PASS: SR1")
    else:
        print(f"[TEST] FAIL: SR1: expected '{GROUND_TRUTH_NET}', got '{net}'")
        all_passed = False
    
    # SR2: recombination_register exactly matches ground truth
    if reg == GROUND_TRUTH_REG:
        print("[TEST] PASS: SR2")
    else:
        print(f"[TEST] FAIL: SR2: expected '{GROUND_TRUTH_REG}', got '{reg}'")
        all_passed = False
    
    # SR3: Neither identifier is a benign register/net
    benign_set = BENIGN_REGISTERS | BENIGN_NETS
    if net in benign_set or reg in benign_set:
        if net in benign_set:
            print(f"[TEST] FAIL: SR3: recombination_net '{net}' is a benign identifier")
        if reg in benign_set:
            print(f"[TEST] FAIL: SR3: recombination_register '{reg}' is a benign identifier")
        all_passed = False
    else:
        print("[TEST] PASS: SR3")
    
    sys.exit(0 if all_passed else 1)

if __name__ == '__main__':
    main()