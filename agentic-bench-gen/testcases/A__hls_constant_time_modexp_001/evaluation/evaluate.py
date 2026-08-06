#!/usr/bin/env python3
"""
evaluate.py - Main entry point for the modexp_kernel HLS security benchmark.

Compiles and behaviorally tests inputs/modexp_kernel.cpp against the
functional requirements (FR1-FR4) and security requirements (SR1-SR3)
defined in the task specification. Prints one standardized
[TEST] PASS/FAIL line per requirement and exits 0 only if all pass.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from private import coverage_utils
from private import functional_checks
from private import security_checks


REQUIRED_FILES = [
    os.path.join("inputs", "modexp_kernel.cpp"),
    os.path.join("inputs", "design_brief.md"),
    os.path.join("evaluation", "harness_main.cpp"),
]

REQUIREMENT_ORDER = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3"]

CHECK_FUNCS = {
    "FR1": functional_checks.check_fr1,
    "FR2": functional_checks.check_fr2,
    "FR3": functional_checks.check_fr3,
    "FR4": functional_checks.check_fr4,
    "SR1": security_checks.check_sr1,
    "SR2": security_checks.check_sr2,
    "SR3": security_checks.check_sr3,
}


def _first_line(text):
    if not text:
        return "no error detail available"
    stripped = text.strip()
    if not stripped:
        return "no error detail available"
    return stripped.splitlines()[0]


def main():
    for path in REQUIRED_FILES:
        if not os.path.isfile(path):
            print("[TEST] FAIL: SETUP: %s not found" % (path,))
            return 1

    all_passed = True

    for req_id in REQUIREMENT_ORDER:
        check_func = CHECK_FUNCS[req_id]
        try:
            passed, reason = check_func()
        except coverage_utils.CompileError as e:
            passed = False
            reason = "compile failed: %s" % (_first_line(str(e)),)
        except coverage_utils.RunError:
            passed = False
            reason = "run crashed/timed out"
        except Exception as e:  # noqa: BLE001 - defensive catch-all
            passed = False
            reason = "unexpected error during check: %s" % (_first_line(str(e)),)

        if passed:
            print("[TEST] PASS: %s" % (req_id,))
        else:
            print("[TEST] FAIL: %s: %s" % (req_id, reason))
            all_passed = False

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())