#!/usr/bin/env python3
"""SR2 checker: verify suspect_nodes contains at least one trigger cone gate."""

import json
import os
import sys


def check_sr2():
    sub_path = os.path.join("submission", "trojan_report.json")
    if not os.path.isfile(sub_path):
        print(f"[TEST] FAIL: SR2: {sub_path} not found")
        return False

    try:
        with open(sub_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[TEST] FAIL: SR2: invalid JSON: {exc}")
        return False

    nodes = data.get("suspect_nodes", [])
    if not isinstance(nodes, list):
        print("[TEST] FAIL: SR2: 'suspect_nodes' is not an array")
        return False

    gt_path = os.path.join("evaluation", "private", "ground_truth.json")
    try:
        with open(gt_path, "r", encoding="utf-8") as f:
            gt = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[TEST] FAIL: SR2: cannot load ground truth: {exc}")
        return False

    trigger_cone = gt.get("trigger_cone_gates", [])
    if not trigger_cone:
        print("[TEST] FAIL: SR2: ground truth missing trigger_cone_gates")
        return False

    if any(g in nodes for g in trigger_cone):
        print("[TEST] PASS: SR2")
        return True
    else:
        print("[TEST] FAIL: SR2: no trigger cone gate found in suspect_nodes")
        return False


if __name__ == "__main__":
    success = check_sr2()
    sys.exit(0 if success else 1)