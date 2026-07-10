#!/usr/bin/env python3
"""
evaluate.py - Main entry point for grading submission/recovered_key.json
against inputs/locked_netlist.v (Anti-SAT localization task).

Usage: python3 evaluation/evaluate.py
"""

import json
import os
import sys

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]

NETLIST_PATH = os.path.join("inputs", "locked_netlist.v")
SUBMISSION_PATH = os.path.join("submission", "recovered_key.json")


def _fail_all_setup(missing_path):
    print("[TEST] FAIL: SETUP: {} not found".format(missing_path))
    for rid in REQUIREMENT_IDS:
        print("[TEST] FAIL: {}: submission unavailable".format(rid))
    sys.exit(1)


def main():
    # Ensure our private checks module is importable regardless of cwd.
    this_dir = os.path.dirname(os.path.abspath(__file__))
    private_dir = os.path.join(this_dir, "private")
    if private_dir not in sys.path:
        sys.path.insert(0, private_dir)

    # Load netlist text.
    if not os.path.isfile(NETLIST_PATH):
        _fail_all_setup(NETLIST_PATH)
        return

    try:
        with open(NETLIST_PATH, "r") as f:
            netlist_text = f.read()
    except OSError:
        _fail_all_setup(NETLIST_PATH)
        return

    # Load submission file.
    if not os.path.isfile(SUBMISSION_PATH):
        _fail_all_setup(SUBMISSION_PATH)
        return

    try:
        with open(SUBMISSION_PATH, "r") as f:
            raw = f.read()
    except OSError:
        _fail_all_setup(SUBMISSION_PATH)
        return

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        _fail_all_setup(SUBMISSION_PATH)
        return

    if not isinstance(data, dict):
        _fail_all_setup(SUBMISSION_PATH)
        return

    try:
        import checks
    except Exception as e:
        # Infrastructure problem: our own harness module missing/broken.
        print("[TEST] FAIL: SETUP: evaluation/private/checks.py import failed: {}".format(e))
        for rid in REQUIREMENT_IDS:
            print("[TEST] FAIL: {}: submission unavailable".format(rid))
        sys.exit(1)
        return

    check_fns = [
        ("FR1", checks.check_fr1),
        ("FR2", checks.check_fr2),
        ("FR3", checks.check_fr3),
        ("FR4", checks.check_fr4),
        ("SR1", checks.check_sr1),
        ("SR2", checks.check_sr2),
        ("SR3", checks.check_sr3),
        ("SR4", checks.check_sr4),
    ]

    all_pass = True
    for rid, fn in check_fns:
        try:
            ok, reason = fn(data, netlist_text)
        except Exception as e:
            ok = False
            reason = "unexpected error during check: {}".format(e)

        if ok:
            print("[TEST] PASS: {}".format(rid))
        else:
            all_pass = False
            print("[TEST] FAIL: {}: {}".format(rid, reason))

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()