#!/usr/bin/env python3
"""
evaluate.py - main entry point for grading a side-channel leakage
vulnerability_report.json submission against the RTL artifacts under inputs/.

Run from the repository root (the directory containing inputs/ and
submission/):

    python evaluation/evaluate.py

This script:
  1. Verifies the required input artifacts exist under inputs/.
  2. Loads submission/vulnerability_report.json.
  3. Re-simulates the provided RTL/testbench to compute ground-truth
     Hamming-distance variance per register.
  4. Runs a fixed sequence of functional (FR) and security (SR) checks
     against the submission, printing standardized PASS/FAIL markers.
  5. Exits 0 iff every check passed, non-zero otherwise.
"""

import json
import os
import sys

# Make evaluation/private importable regardless of current working directory.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PRIVATE_DIR = os.path.join(_THIS_DIR, "private")
if _PRIVATE_DIR not in sys.path:
    sys.path.insert(0, _PRIVATE_DIR)

try:
    import analysis  # noqa: E402
except Exception as exc:  # pragma: no cover - infrastructure failure
    print("[TEST] FAIL: SETUP: could not import evaluation/private/analysis.py: %s" % exc)
    sys.exit(1)

REQUIRED_INPUT_FILES = [
    "inputs/round_datapath.v",
    "inputs/sbox_table.v",
    "inputs/testbench_hd_trace.v",
    "inputs/power_model.md",
    "inputs/design_brief.md",
]

SUBMISSION_PATH = "submission/vulnerability_report.json"

ALL_REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]


def main():
    overall_ok = True

    # Step 1: verify required input artifacts exist.
    missing = []
    for path in REQUIRED_INPUT_FILES:
        if not os.path.isfile(path):
            missing.append(path)

    if missing:
        for path in missing:
            print("[TEST] FAIL: SETUP: %s not found" % path)
        sys.exit(1)

    # Step 2: load submission JSON.
    submission = None
    if not os.path.isfile(SUBMISSION_PATH):
        print("[TEST] FAIL: SETUP: %s not found" % SUBMISSION_PATH)
        for req_id in ALL_REQUIREMENT_IDS:
            print("[TEST] FAIL: %s: submission unavailable" % req_id)
        sys.exit(1)

    try:
        with open(SUBMISSION_PATH, "r") as f:
            submission = json.load(f)
    except FileNotFoundError:
        print("[TEST] FAIL: SETUP: %s not found" % SUBMISSION_PATH)
        for req_id in ALL_REQUIREMENT_IDS:
            print("[TEST] FAIL: %s: submission unavailable" % req_id)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print("[TEST] FAIL: SETUP: %s invalid JSON: %s" % (SUBMISSION_PATH, exc))
        for req_id in ALL_REQUIREMENT_IDS:
            print("[TEST] FAIL: %s: submission unavailable" % req_id)
        sys.exit(1)
    except Exception as exc:
        print("[TEST] FAIL: SETUP: %s could not be read: %s" % (SUBMISSION_PATH, exc))
        for req_id in ALL_REQUIREMENT_IDS:
            print("[TEST] FAIL: %s: submission unavailable" % req_id)
        sys.exit(1)

    # Step 3: compute ground truth via re-simulation (best effort).
    gt = None
    try:
        gt = analysis.compute_ground_truth("inputs")
    except Exception as exc:
        gt = None
        _gt_error = str(exc)
    else:
        _gt_error = None

    # Step 4: run each requirement check in fixed order.
    checks = [
        ("FR1", getattr(analysis, "check_fr1", None)),
        ("FR2", getattr(analysis, "check_fr2", None)),
        ("FR3", getattr(analysis, "check_fr3", None)),
        ("FR4", getattr(analysis, "check_fr4", None)),
        ("SR1", getattr(analysis, "check_sr1", None)),
        ("SR2", getattr(analysis, "check_sr2", None)),
        ("SR3", getattr(analysis, "check_sr3", None)),
        ("SR4", getattr(analysis, "check_sr4", None)),
    ]

    for req_id, func in checks:
        if func is None:
            print("[TEST] FAIL: %s: SETUP: analysis.check_%s not implemented" % (req_id, req_id.lower()))
            overall_ok = False
            continue

        try:
            ok, reason = func(submission, gt, input_dir="inputs")
        except Exception as exc:
            ok = False
            reason = "unexpected error: %s" % exc

        if gt is None and not ok and reason and "simulation failed" not in reason and _gt_error is not None:
            # Ensure requirements that depend on gt surface the simulation
            # failure reason rather than an opaque KeyError/TypeError, when
            # the check implementation didn't already do so itself.
            pass

        if ok:
            print("[TEST] PASS: %s" % req_id)
        else:
            print("[TEST] FAIL: %s: %s" % (req_id, reason))
            overall_ok = False

    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()