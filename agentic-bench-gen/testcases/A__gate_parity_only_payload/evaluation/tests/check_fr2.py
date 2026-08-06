#!/usr/bin/env python3
"""FR2 checker: validate that 'label' is 'Trojan' or 'Trojan-Free'."""

import json
import os
import sys


def check_fr2():
    sub_path = os.path.join("submission", "trojan_report.json")
    if not os.path.isfile(sub_path):
        print(f"[TEST] FAIL: FR2: {sub_path} not found")
        return False

    try:
        with open(sub_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[TEST] FAIL: FR2: invalid JSON: {exc}")
        return False

    label = data.get("label")
    if not isinstance(label, str):
        print(f"[TEST] FAIL: FR2: 'label' must be a string, got {type(label).__name__}")
        return False

    if label not in ("Trojan", "Trojan-Free"):
        print(f"[TEST] FAIL: FR2: 'label' must be 'Trojan' or 'Trojan-Free', got '{label}'")
        return False

    print("[TEST] PASS: FR2")
    return True


if __name__ == "__main__":
    success = check_fr2()
    sys.exit(0 if success else 1)