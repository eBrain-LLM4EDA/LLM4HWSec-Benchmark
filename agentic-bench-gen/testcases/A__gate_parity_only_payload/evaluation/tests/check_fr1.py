#!/usr/bin/env python3
"""FR1 checker: validate JSON structure and required keys."""

import json
import os
import sys


def check_fr1():
    sub_path = os.path.join("submission", "trojan_report.json")
    if not os.path.isfile(sub_path):
        print(f"[TEST] FAIL: FR1: {sub_path} not found")
        return False

    try:
        with open(sub_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[TEST] FAIL: FR1: invalid JSON: {exc}")
        return False

    if not isinstance(data, dict):
        print("[TEST] FAIL: FR1: top-level JSON is not an object")
        return False

    keys = set(data.keys())
    required = {"label", "suspect_nodes"}
    if keys != required:
        print(f"[TEST] FAIL: FR1: expected keys {sorted(required)}, got {sorted(keys)}")
        return False

    print("[TEST] PASS: FR1")
    return True


if __name__ == "__main__":
    success = check_fr1()
    sys.exit(0 if success else 1)