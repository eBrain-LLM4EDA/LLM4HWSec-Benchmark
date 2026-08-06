import json
import os
import re
import sys

# Import private ground truth
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'private'))
from ground_truth import CORRECT_KEY, GROUND_TRUTH_NETS

def extract_net_names(netlist_path):
    """Extract all net names declared in the netlist (wire/assign)."""
    nets = set()
    with open(netlist_path, 'r') as f:
        content = f.read()
    # Match wire declarations: wire [optional range] name;
    wire_pattern = r'wire\s+(?:\[\d+:\d+\]\s+)?(\w+)\s*;'
    for m in re.finditer(wire_pattern, content):
        nets.add(m.group(1))
    # Match assign statements: assign name = ...;
    assign_pattern = r'assign\s+(\w+)\s*='
    for m in re.finditer(assign_pattern, content):
        nets.add(m.group(1))
    # Also match module port connections (hierarchical names like lock_comp/xor_0)
    # We'll collect all identifiers that appear as net names in the netlist
    # For hierarchical names, we need to consider module instances and their internal nets.
    # Since the netlist is flat, we can extract all identifiers used in connections.
    # A simple approach: collect all identifiers that are not keywords.
    # But we'll rely on the fact that the netlist uses explicit wire declarations for all nets.
    # For hierarchical names like lock_comp/xor_0, we need to parse the module hierarchy.
    # We'll extract module instance names and their internal nets.
    # Pattern: module_name instance_name ( .port(net) );
    instance_pattern = r'(\w+)\s+(\w+)\s*\(([^)]+)\)'
    for m in re.finditer(instance_pattern, content):
        module_name = m.group(1)
        instance_name = m.group(2)
        ports = m.group(3)
        # Extract port connections: .port_name(net_name)
        port_conn_pattern = r'\.(\w+)\s*\(\s*(\w+)\s*\)'
        for pm in re.finditer(port_conn_pattern, ports):
            port = pm.group(1)
            net = pm.group(2)
            # Add both the flat net and the hierarchical path
            nets.add(net)
            nets.add(f"{instance_name}/{net}")
    # Also add nets from module internal declarations (inside submodules)
    # We'll parse all wire declarations inside any module
    module_pattern = r'module\s+(\w+)\s*\(([^)]*)\)\s*;(.*?)endmodule'
    for mm in re.finditer(module_pattern, content, re.DOTALL):
        mod_name = mm.group(1)
        mod_body = mm.group(3)
        # Find wire declarations inside this module
        for wm in re.finditer(wire_pattern, mod_body):
            nets.add(wm.group(1))
        # Also assign statements
        for am in re.finditer(assign_pattern, mod_body):
            nets.add(am.group(1))
    return nets

def main():
    submission_path = 'submission/recovered_key.json'
    netlist_path = 'inputs/locked_netlist.v'
    
    # Check submission file exists
    if not os.path.isfile(submission_path):
        print("[TEST] FAIL: SETUP: submission/recovered_key.json not found")
        sys.exit(1)
    
    # FR1: Valid JSON
    try:
        with open(submission_path, 'r') as f:
            data = json.load(f)
        print("[TEST] PASS: FR1")
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[TEST] FAIL: FR1: {str(e)}")
        # Cannot continue without valid JSON
        sys.exit(1)
    
    # FR2: recovered_key field
    recovered_key = data.get('recovered_key')
    if not isinstance(recovered_key, str) or not recovered_key:
        print("[TEST] FAIL: FR2: recovered_key must be a non-empty string")
    elif not all(c in '01' for c in recovered_key):
        print("[TEST] FAIL: FR2: recovered_key must contain only '0' and '1'")
    else:
        print("[TEST] PASS: FR2")
    
    # FR3: key_gate_nets field
    key_gate_nets = data.get('key_gate_nets')
    if not isinstance(key_gate_nets, list):
        print("[TEST] FAIL: FR3: key_gate_nets must be an array")
    else:
        # Extract valid net names from netlist
        valid_nets = extract_net_names(netlist_path)
        all_valid = True
        for net in key_gate_nets:
            if not isinstance(net, str):
                print(f"[TEST] FAIL: FR3: key_gate_nets contains non-string element: {net}")
                all_valid = False
                break
            if net not in valid_nets:
                print(f"[TEST] FAIL: FR3: net '{net}' not found in locked_netlist.v")
                all_valid = False
                break
        if all_valid:
            print("[TEST] PASS: FR3")
    
    # SR1: Exact key match
    if recovered_key == CORRECT_KEY:
        print("[TEST] PASS: SR1")
    else:
        print(f"[TEST] FAIL: SR1: recovered_key '{recovered_key}' does not match hidden key")
    
    # SR2: Key gate nets superset
    submitted_nets = set(key_gate_nets) if isinstance(key_gate_nets, list) else set()
    missing = GROUND_TRUTH_NETS - submitted_nets
    if not missing:
        print("[TEST] PASS: SR2")
    else:
        print(f"[TEST] FAIL: SR2: missing ground-truth nets: {missing}")
    
    # Determine exit code based on all checks
    # We need to re-check all conditions to decide exit code
    # Since we printed PASS/FAIL, we can track failures
    failures = []
    # Re-evaluate FR1 (already passed if we got here)
    # FR2
    if not (isinstance(recovered_key, str) and recovered_key and all(c in '01' for c in recovered_key)):
        failures.append('FR2')
    # FR3
    if not isinstance(key_gate_nets, list) or any(not isinstance(n, str) or n not in valid_nets for n in key_gate_nets):
        failures.append('FR3')
    # SR1
    if recovered_key != CORRECT_KEY:
        failures.append('SR1')
    # SR2
    if missing:
        failures.append('SR2')
    
    if failures:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == '__main__':
    main()