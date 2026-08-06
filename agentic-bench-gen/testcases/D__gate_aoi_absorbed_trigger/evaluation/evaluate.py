#!/usr/bin/env python3
"""evaluate.py – Grade the submitted trojan_report.json against hidden ground truth."""

import json
import os
import sys
import re

# ----------------------------------------------------------------------
# Helper: parse the netlist to extract all cell instances and net names
# ----------------------------------------------------------------------
def parse_netlist(path):
    """Return (cells, nets) sets from a flat gate-level Verilog file."""
    cells = set()
    nets = set()
    try:
        with open(path, "r") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"[TEST] FAIL: SETUP: {path} not found")
        sys.exit(1)

    # Cell instances:  <cell_type> <instance_name> ( ... );
    # e.g.  AOI21 aoi_trig (.A0(...), ...);
    cell_pattern = re.compile(
        r'^\s*([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*\(', re.MULTILINE
    )
    for m in cell_pattern.finditer(text):
        cells.add(m.group(2))

    # Nets: wire declarations and continuous assignments
    # wire n1, n2, ...;
    wire_pattern = re.compile(r'^\s*wire\s+([^;]+);', re.MULTILINE)
    for m in wire_pattern.finditer(text):
        for name in m.group(1).split(','):
            name = name.strip()
            if name:
                nets.add(name)

    # Also catch nets that appear as port connections (inside parentheses)
    # This is a simple heuristic: any identifier that is not a keyword and
    # appears in a port list could be a net. We'll just add all identifiers
    # that look like net names (lowercase with optional underscores/digits).
    # To avoid false positives, we only add identifiers that appear in
    # port connection lists and are not already known cells.
    port_conn_pattern = re.compile(r'\.\w+\s*\(\s*(\w+)\s*\)')
    for m in port_conn_pattern.finditer(text):
        net_candidate = m.group(1)
        if net_candidate not in cells and re.match(r'^[a-z_]\w*$', net_candidate):
            nets.add(net_candidate)

    return cells, nets


# ----------------------------------------------------------------------
# Main grading logic
# ----------------------------------------------------------------------
def main():
    # Paths
    submission_path = "submission/trojan_report.json"
    netlist_path = "inputs/design.v"
    ground_truth_path = "evaluation/private/ground_truth.json"

    all_pass = True

    # ----------------------------------------------------------------
    # FR1: File exists and is valid JSON
    # ----------------------------------------------------------------
    if not os.path.isfile(submission_path):
        print(f"[TEST] FAIL: FR1: {submission_path} not found")
        all_pass = False
        # Cannot continue without the file
        sys.exit(1)

    try:
        with open(submission_path, "r") as f:
            report = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[TEST] FAIL: FR1: invalid JSON: {e}")
        all_pass = False
        sys.exit(1)
    except Exception as e:
        print(f"[TEST] FAIL: FR1: could not read file: {e}")
        all_pass = False
        sys.exit(1)

    print("[TEST] PASS: FR1")

    # ----------------------------------------------------------------
    # FR2: Exactly the four required top-level keys
    # ----------------------------------------------------------------
    required_keys = {"trigger_cells", "trigger_nets", "payload_cells", "payload_nets"}
    actual_keys = set(report.keys())
    if actual_keys != required_keys:
        missing = required_keys - actual_keys
        extra = actual_keys - required_keys
        msg = ""
        if missing:
            msg += f"missing keys: {sorted(missing)}; "
        if extra:
            msg += f"extra keys: {sorted(extra)}"
        print(f"[TEST] FAIL: FR2: {msg.strip()}")
        all_pass = False
    else:
        print("[TEST] PASS: FR2")

    # ----------------------------------------------------------------
    # FR3: Each key maps to a non-empty array of strings
    # ----------------------------------------------------------------
    fr3_ok = True
    for key in required_keys:
        val = report.get(key)
        if not isinstance(val, list) or len(val) == 0:
            print(f"[TEST] FAIL: FR3: '{key}' is not a non-empty array")
            fr3_ok = False
        else:
            for item in val:
                if not isinstance(item, str):
                    print(f"[TEST] FAIL: FR3: '{key}' contains non-string element: {item}")
                    fr3_ok = False
                    break
    if fr3_ok:
        print("[TEST] PASS: FR3")
    else:
        all_pass = False

    # ----------------------------------------------------------------
    # FR4: All reported names exist in the netlist
    # ----------------------------------------------------------------
    cells_in_netlist, nets_in_netlist = parse_netlist(netlist_path)

    fr4_ok = True
    for key in ["trigger_cells", "payload_cells"]:
        for name in report.get(key, []):
            if name not in cells_in_netlist:
                print(f"[TEST] FAIL: FR4: cell '{name}' not found in netlist")
                fr4_ok = False
    for key in ["trigger_nets", "payload_nets"]:
        for name in report.get(key, []):
            if name not in nets_in_netlist:
                print(f"[TEST] FAIL: FR4: net '{name}' not found in netlist")
                fr4_ok = False
    if fr4_ok:
        print("[TEST] PASS: FR4")
    else:
        all_pass = False

    # ----------------------------------------------------------------
    # Load hidden ground truth
    # ----------------------------------------------------------------
    try:
        with open(ground_truth_path, "r") as f:
            gt = json.load(f)
    except FileNotFoundError:
        print(f"[TEST] FAIL: SETUP: {ground_truth_path} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[TEST] FAIL: SETUP: invalid ground truth JSON: {e}")
        sys.exit(1)

    # ----------------------------------------------------------------
    # SR1: Trigger components match ground truth
    # ----------------------------------------------------------------
    sr1_ok = True
    gt_trigger_cells = set(gt["trigger_cells"])
    gt_trigger_nets = set(gt["trigger_nets"])
    reported_trigger_cells = set(report.get("trigger_cells", []))
    reported_trigger_nets = set(report.get("trigger_nets", []))

    missing_cells = gt_trigger_cells - reported_trigger_cells
    missing_nets = gt_trigger_nets - reported_trigger_nets
    if missing_cells:
        print(f"[TEST] FAIL: SR1: missing trigger cells: {sorted(missing_cells)}")
        sr1_ok = False
    if missing_nets:
        print(f"[TEST] FAIL: SR1: missing trigger nets: {sorted(missing_nets)}")
        sr1_ok = False
    if sr1_ok:
        print("[TEST] PASS: SR1")
    else:
        all_pass = False

    # ----------------------------------------------------------------
    # SR2: Payload components match ground truth
    # ----------------------------------------------------------------
    sr2_ok = True
    gt_payload_cells = set(gt["payload_cells"])
    gt_payload_nets = set(gt["payload_nets"])
    reported_payload_cells = set(report.get("payload_cells", []))
    reported_payload_nets = set(report.get("payload_nets", []))

    missing_cells = gt_payload_cells - reported_payload_cells
    missing_nets = gt_payload_nets - reported_payload_nets
    if missing_cells:
        print(f"[TEST] FAIL: SR2: missing payload cells: {sorted(missing_cells)}")
        sr2_ok = False
    if missing_nets:
        print(f"[TEST] FAIL: SR2: missing payload nets: {sorted(missing_nets)}")
        sr2_ok = False
    if sr2_ok:
        print("[TEST] PASS: SR2")
    else:
        all_pass = False

    # ----------------------------------------------------------------
    # Exit with appropriate code
    # ----------------------------------------------------------------
    if all_pass:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()