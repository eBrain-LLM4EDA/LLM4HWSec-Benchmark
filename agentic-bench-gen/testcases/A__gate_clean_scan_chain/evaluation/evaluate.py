import json
import os
import sys
import re

# Fix import path so we can import from evaluation.private
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.private.scan_whitelist import SCAN_WHITELIST

def extract_netlist_identifiers(netlist_path):
    """Extract all valid identifiers (instance names, wire names) from the netlist."""
    identifiers = set()
    try:
        with open(netlist_path, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"[TEST] FAIL: SETUP: {netlist_path} not found")
        sys.exit(1)
    
    # Match module instance names: <module_name> <instance_name> (
    instance_pattern = re.compile(r'\b\w+\s+(\w+)\s*\(')
    # Match wire declarations: wire [range] name;
    wire_pattern = re.compile(r'\bwire\s+(?:\[\d+:\d+\]\s+)?(\w+)\s*;')
    # Match input/output port names
    port_pattern = re.compile(r'\b(?:input|output)\s+(?:wire\s+)?(?:\[\d+:\d+\]\s+)?(\w+)\s*[,;]')
    
    for match in instance_pattern.finditer(content):
        identifiers.add(match.group(1))
    for match in wire_pattern.finditer(content):
        identifiers.add(match.group(1))
    for match in port_pattern.finditer(content):
        identifiers.add(match.group(1))
    
    # Also add top-level ports explicitly
    top_ports = ['clk', 'rst_n', 'test_mode', 'scan_in', 'data_in', 'data_out', 'scan_out']
    identifiers.update(top_ports)
    
    return identifiers

def main():
    submission_path = "submission/trojan_report.json"
    netlist_path = "inputs/scan_controller.v"
    
    # Check submission file exists
    if not os.path.exists(submission_path):
        print(f"[TEST] FAIL: SETUP: {submission_path} not found")
        sys.exit(1)
    
    # FR1: Valid JSON
    try:
        with open(submission_path, 'r') as f:
            report = json.load(f)
        print("[TEST] PASS: FR1")
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[TEST] FAIL: FR1: {str(e)}")
        # Cannot proceed with other checks if JSON is invalid
        sys.exit(1)
    
    # FR2: Required fields with correct types
    fr2_pass = True
    if not isinstance(report.get('infected'), bool):
        print("[TEST] FAIL: FR2: 'infected' field missing or not boolean")
        fr2_pass = False
    if not isinstance(report.get('trigger_nodes'), list) or not all(isinstance(n, str) for n in report['trigger_nodes']):
        print("[TEST] FAIL: FR2: 'trigger_nodes' field missing or not array of strings")
        fr2_pass = False
    if not isinstance(report.get('payload_nodes'), list) or not all(isinstance(n, str) for n in report['payload_nodes']):
        print("[TEST] FAIL: FR2: 'payload_nodes' field missing or not array of strings")
        fr2_pass = False
    if fr2_pass:
        print("[TEST] PASS: FR2")
    
    # FR3: Consistency between infected flag and arrays
    infected = report.get('infected')
    trigger_nodes = report.get('trigger_nodes', [])
    payload_nodes = report.get('payload_nodes', [])
    
    fr3_pass = True
    if infected is False:
        if trigger_nodes or payload_nodes:
            print("[TEST] FAIL: FR3: infected is false but trigger_nodes or payload_nodes is non-empty")
            fr3_pass = False
    elif infected is True:
        if not trigger_nodes or not payload_nodes:
            print("[TEST] FAIL: FR3: infected is true but trigger_nodes or payload_nodes is empty")
            fr3_pass = False
    if fr3_pass:
        print("[TEST] PASS: FR3")
    
    # FR4: All reported node names must exist in the netlist
    netlist_ids = extract_netlist_identifiers(netlist_path)
    all_reported = set(trigger_nodes) | set(payload_nodes)
    invalid_nodes = [n for n in all_reported if n not in netlist_ids]
    if invalid_nodes:
        print(f"[TEST] FAIL: FR4: invalid node names: {', '.join(invalid_nodes)}")
    else:
        print("[TEST] PASS: FR4")
    
    # SR1: No legitimate scan-control nodes flagged
    flagged_whitelist = [n for n in all_reported if n in SCAN_WHITELIST]
    if flagged_whitelist:
        print(f"[TEST] FAIL: SR1: legitimate scan-control nodes flagged: {', '.join(flagged_whitelist)}")
    else:
        print("[TEST] PASS: SR1")
    
    # SR2: payload_nodes must be empty (ground truth is clean)
    if payload_nodes:
        print(f"[TEST] FAIL: SR2: payload_nodes is non-empty: {payload_nodes}")
    else:
        print("[TEST] PASS: SR2")
    
    # Determine exit code
    failed = False
    if not fr2_pass:
        failed = True
    if not fr3_pass:
        failed = True
    if invalid_nodes:
        failed = True
    if flagged_whitelist:
        failed = True
    if payload_nodes:
        failed = True
    
    if failed:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()