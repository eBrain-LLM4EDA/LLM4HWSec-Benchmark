#!/usr/bin/env python3
"""SR1 checker: verify suspect_nodes contains the payload AND gate."""

import json
import os
import sys


def check_sr1():
    sub_path = os.path.join("submission", "trojan_report.json")
    if not os.path.isfile(sub_path):
        print(f"[TEST] FAIL: SR1: {sub_path} not found")
        return False

    try:
        with open(sub_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[TEST] FAIL: SR1: invalid JSON: {exc}")
        return False

    nodes = data.get("suspect_nodes", [])
    if not isinstance(nodes, list):
        print("[TEST] FAIL: SR1: 'suspect_nodes' is not an array")
        return False

    gt_path = os.path.join("evaluation", "private", "ground_truth.json")
    try:
        with open(gt_path, "r", encoding="utf-8") as f:
            gt = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[TEST] FAIL: SR1: cannot load ground truth: {exc}")
        return False

    required = gt.get("payload_gate")
    if not required:
        print("[TEST] FAIL: SR1: ground truth missing payload_gate")
        return False

    if required in nodes:
        print("[TEST] PASS: SR1")
        return True
    else:
        print(f"[TEST] FAIL: SR1: missing required payload gate '{required}'")
        return False


if __name__ == "__main__":
    success = check_sr1()
    sys.exit(0 if success else 1)