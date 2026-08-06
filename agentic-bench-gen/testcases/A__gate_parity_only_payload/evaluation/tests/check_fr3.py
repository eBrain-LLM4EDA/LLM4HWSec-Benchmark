#!/usr/bin/env python3
"""FR3 checker: validate suspect_nodes identifiers exist in design.v."""

import json
import os
import re
import sys


def extract_identifiers(verilog_path):
    """Return a set of all wire/gate instance names found in the Verilog file."""
    identifiers = set()
    try:
        with open(verilog_path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        print(f"WARNING: cannot read {verilog_path}: {exc}", file=sys.stderr)
        return identifiers

    # Instance names: module_name instance_name ( ... );
    for m in re.finditer(r'\b\w+\s+(\w+)\s*\(', text):
        identifiers.add(m.group(1))
    # Wire declarations: wire name;
    for m in re.finditer(r'wire\s+(\w+)\s*;', text):
        identifiers.add(m.group(1))
    # Multi-bit wires: wire [7:0] name;
    for m in re.finditer(r'wire\s+\[\d+:\d+\]\s+(\w+)\s*;', text):
        identifiers.add(m.group(1))
    # Output port declarations: output wire name;
    for m in re.finditer(r'output\s+(?:wire\s+)?(\w+)\s*;', text):
        identifiers.add(m.group(1))
    # Input port declarations: input wire name;
    for m in re.finditer(r'input\s+(?:wire\s+)?(\w+)\s*;', text):
        identifiers.add(m.group(1))
    return identifiers


def check_fr3():
    sub_path = os.path.join("submission", "trojan_report.json")
    if not os.path.isfile(sub_path):
        print(f"[TEST] FAIL: FR3: {sub_path} not found")
        return False

    try:
        with open(sub_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[TEST] FAIL: FR3: invalid JSON: {exc}")
        return False

    nodes = data.get("suspect_nodes")
    if not isinstance(nodes, list):
        print(f"[TEST] FAIL: FR3: 'suspect_nodes' must be an array, got {type(nodes).__name__}")
        return False
    if not all(isinstance(n, str) for n in nodes):
        print("[TEST] FAIL: FR3: all entries in 'suspect_nodes' must be strings")
        return False

    design_path = os.path.join("inputs", "design.v")
    if not os.path.isfile(design_path):
        print(f"[TEST] FAIL: FR3: {design_path} not found")
        return False

    valid_ids = extract_identifiers(design_path)
    invalid = [n for n in nodes if n not in valid_ids]
    if invalid:
        print(f"[TEST] FAIL: FR3: invalid identifiers: {', '.join(invalid)}")
        return False

    print("[TEST] PASS: FR3")
    return True


if __name__ == "__main__":
    success = check_fr3()
    sys.exit(0 if success else 1)