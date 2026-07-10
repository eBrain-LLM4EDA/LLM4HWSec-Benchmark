#!/usr/bin/env python3
"""
evaluate.py - Main evaluation entry point for hls_constant_time_compare_001

Grades inputs/mac_verify.cpp (+ inputs/mac_verify.h) by:
  1. Static scan (SR1, SR2) of the verify() function body for data-dependent
     early loop exits (return/break/goto inside the comparison loop).
  2. Static scan (SR3) of mac_verify.h for interface conformance and
     mac_verify.cpp for dynamic/heap allocation constructs.
  3. Compiling inputs/mac_verify.cpp against evaluation/harness_main.cpp with
     g++ and running the resulting binary to derive FR1-FR4 and the
     behavioral half of SR3.
"""

import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUTS_DIR = os.path.join(REPO_ROOT, "inputs")
EVAL_DIR = os.path.join(REPO_ROOT, "evaluation")

MAC_VERIFY_CPP = os.path.join(INPUTS_DIR, "mac_verify.cpp")
MAC_VERIFY_H = os.path.join(INPUTS_DIR, "mac_verify.h")
HARNESS_MAIN = os.path.join(EVAL_DIR, "harness_main.cpp")

results = {}  # requirement_id -> (bool_ok, reason)


def record(req_id, ok, reason=""):
    results[req_id] = (ok, reason)
    if ok:
        print("[TEST] PASS: {}".format(req_id))
    else:
        print("[TEST] FAIL: {}: {}".format(req_id, reason))


def fail_all(req_ids, reason):
    for r in req_ids:
        record(r, False, reason)


def main():
    # --- SETUP checks: required input files must exist ---
    missing = []
    for fname, fpath in [
        ("inputs/mac_verify.cpp", MAC_VERIFY_CPP),
        ("inputs/mac_verify.h", MAC_VERIFY_H),
    ]:
        if not os.path.isfile(fpath):
            missing.append(fname)

    if missing:
        for fname in missing:
            print("[TEST] FAIL: SETUP: {} not found".format(fname))
        sys.exit(1)

    if not os.path.isfile(HARNESS_MAIN):
        print("[TEST] FAIL: SETUP: evaluation/harness_main.cpp not found")
        sys.exit(1)

    # --- Load private static-check module ---
    sys.path.insert(0, os.path.join(EVAL_DIR, "private"))
    try:
        import static_checks  # noqa: E402
    except Exception as e:
        print("[TEST] FAIL: SETUP: could not load evaluation/private/static_checks.py: {}".format(e))
        sys.exit(1)

    try:
        with open(MAC_VERIFY_CPP, "r", encoding="utf-8", errors="replace") as f:
            source_text = f.read()
    except Exception as e:
        print("[TEST] FAIL: SETUP: could not read inputs/mac_verify.cpp: {}".format(e))
        sys.exit(1)

    try:
        with open(MAC_VERIFY_H, "r", encoding="utf-8", errors="replace") as f:
            header_text = f.read()
    except Exception as e:
        print("[TEST] FAIL: SETUP: could not read inputs/mac_verify.h: {}".format(e))
        sys.exit(1)

    # --- SR1 / SR2: static structural checks (independent of compilation) ---
    try:
        sr1_ok, sr1_reason = static_checks.check_sr1(source_text)
    except Exception as e:
        sr1_ok, sr1_reason = False, "static_checks.check_sr1 raised exception: {}".format(e)

    try:
        sr2_ok, sr2_reason = static_checks.check_sr2(source_text)
    except Exception as e:
        sr2_ok, sr2_reason = False, "static_checks.check_sr2 raised exception: {}".format(e)

    record("SR1", sr1_ok, sr1_reason)
    record("SR2", sr2_ok, sr2_reason)

    # --- SR3 static sub-checks: interface conformance and no dynamic alloc ---
    try:
        sr3_iface_ok, sr3_iface_reason = static_checks.check_sr3_interface(header_text)
    except Exception as e:
        sr3_iface_ok, sr3_iface_reason = False, "static_checks.check_sr3_interface raised exception: {}".format(e)

    try:
        sr3_alloc_ok, sr3_alloc_reason = static_checks.check_sr3_dynamic_alloc(source_text)
    except Exception as e:
        sr3_alloc_ok, sr3_alloc_reason = False, "static_checks.check_sr3_dynamic_alloc raised exception: {}".format(e)

    # --- Compile inputs/mac_verify.cpp + evaluation/harness_main.cpp ---
    behavioral_ids = ["FR1", "FR2", "FR3", "FR4", "SR3"]

    # If either static SR3 sub-check already fails, we still want to attempt
    # compilation/behavioral checks for the other requirements, but SR3's
    # final verdict must reflect the static failure regardless of the
    # behavioral outcome.
    sr3_static_ok = sr3_iface_ok and sr3_alloc_ok
    if not sr3_iface_ok:
        sr3_static_reason = sr3_iface_reason
    elif not sr3_alloc_ok:
        sr3_static_reason = sr3_alloc_reason
    else:
        sr3_static_reason = ""

    with tempfile.TemporaryDirectory() as tmpdir:
        binary_path = os.path.join(tmpdir, "harness")
        compile_cmd = [
            "g++",
            "-std=c++11",
            "-O2",
            "-I", INPUTS_DIR,
            "-o", binary_path,
            MAC_VERIFY_CPP,
            HARNESS_MAIN,
        ]

        try:
            compile_proc = subprocess.run(
                compile_cmd,
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            fail_all(behavioral_ids, "compile failed: timed out after 30s")
            finish_with_sr3_override(sr3_static_ok, sr3_static_reason)
            return
        except Exception as e:
            fail_all(behavioral_ids, "compile failed: {}".format(e))
            finish_with_sr3_override(sr3_static_ok, sr3_static_reason)
            return

        if compile_proc.returncode != 0:
            stderr_text = compile_proc.stderr.decode("utf-8", errors="replace")
            first_line = next(
                (line for line in stderr_text.splitlines() if line.strip()),
                "unknown compiler error",
            )
            fail_all(behavioral_ids, "compile failed: {}".format(first_line))
            finish_with_sr3_override(sr3_static_ok, sr3_static_reason)
            return

        # --- Run the compiled binary ---
        try:
            run_proc = subprocess.run(
                [binary_path],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            fail_all(behavioral_ids, "run crashed/timed out: execution exceeded 10s")
            finish_with_sr3_override(sr3_static_ok, sr3_static_reason)
            return
        except Exception as e:
            fail_all(behavioral_ids, "run crashed/timed out: {}".format(e))
            finish_with_sr3_override(sr3_static_ok, sr3_static_reason)
            return

        stdout_text = run_proc.stdout.decode("utf-8", errors="replace")

        if run_proc.returncode != 0:
            fail_all(
                behavioral_ids,
                "run crashed/timed out: exit code {}".format(run_proc.returncode),
            )
            finish_with_sr3_override(sr3_static_ok, sr3_static_reason)
            return

        # --- Parse harness output ---
        parsed = {}
        for line in stdout_text.splitlines():
            line = line.strip()
            if line.startswith("FR1_RESULT"):
                parts = line.split()
                if len(parts) == 3:
                    parsed["FR1"] = (parts[1], parts[2])
            elif line.startswith("FR2_RESULT"):
                parts = line.split()
                if len(parts) == 3:
                    parsed["FR2"] = (parts[1], parts[2])
            elif line.startswith("FR4_RESULT"):
                parts = line.split()
                if len(parts) == 3:
                    parsed["FR4"] = (parts[1], parts[2])
            elif line.startswith("SR3_ALLOC_COUNT"):
                parts = line.split()
                if len(parts) == 2:
                    parsed["SR3"] = parts[1]

        # FR1: pass == total, total >= 20
        if "FR1" in parsed:
            try:
                p, t = int(parsed["FR1"][0]), int(parsed["FR1"][1])
                if t < 20:
                    record("FR1", False, "FR1_RESULT total={} is below required minimum of 20".format(t))
                elif p != t:
                    record("FR1", False, "FR1_RESULT {}/{} identical-tag pairs verified true".format(p, t))
                else:
                    record("FR1", True)
            except ValueError:
                record("FR1", False, "malformed FR1_RESULT output: {}".format(parsed["FR1"]))
        else:
            record("FR1", False, "harness did not print FR1_RESULT line")

        # FR2: pass == total, total >= 16*20 (single-byte) + multi-byte cases
        if "FR2" in parsed:
            try:
                p, t = int(parsed["FR2"][0]), int(parsed["FR2"][1])
                if t < 16 * 20:
                    record("FR2", False, "FR2_RESULT total={} is below required minimum coverage".format(t))
                elif p != t:
                    record("FR2", False, "FR2_RESULT {}/{} mismatch cases correctly rejected".format(p, t))
                else:
                    record("FR2", True)
            except ValueError:
                record("FR2", False, "malformed FR2_RESULT output: {}".format(parsed["FR2"]))
        else:
            record("FR2", False, "harness did not print FR2_RESULT line")

        # FR3: compile succeeded and binary ran to completion (already established)
        record("FR3", True)

        # FR4: pass == total over fixed edge-case set
        if "FR4" in parsed:
            try:
                p, t = int(parsed["FR4"][0]), int(parsed["FR4"][1])
                if t < 6:
                    record("FR4", False, "FR4_RESULT total={} is below required minimum of 6 edge cases".format(t))
                elif p != t:
                    record("FR4", False, "FR4_RESULT {}/{} zero/0xFF edge cases correct".format(p, t))
                else:
                    record("FR4", True)
            except ValueError:
                record("FR4", False, "malformed FR4_RESULT output: {}".format(parsed["FR4"]))
        else:
            record("FR4", False, "harness did not print FR4_RESULT line")

        # SR3: combine static interface check, static no-dynamic-alloc check,
        # and behavioral alloc-count check.
        if not sr3_static_ok:
            record("SR3", False, sr3_static_reason)
        elif "SR3" in parsed:
            try:
                alloc_count = int(parsed["SR3"])
                if alloc_count == 0:
                    record("SR3", True)
                else:
                    record("SR3", False, "detected {} heap allocation(s) during verify() calls".format(alloc_count))
            except ValueError:
                record("SR3", False, "malformed SR3_ALLOC_COUNT output: {}".format(parsed["SR3"]))
        else:
            record("SR3", False, "harness did not print SR3_ALLOC_COUNT line")

    finish()


def finish_with_sr3_override(sr3_static_ok, sr3_static_reason):
    """Called when compile/run failed before behavioral SR3 could be
    evaluated. SR3's already-recorded FAIL (from fail_all) is overridden
    with the static reason only if the static checks are the actual cause;
    otherwise the compile/run failure reason (already recorded) stands."""
    if not sr3_static_ok:
        results["SR3"] = (False, sr3_static_reason)
        print("[TEST] FAIL: SR3: {}".format(sr3_static_reason))
    finish()


def finish():
    all_ok = all(ok for ok, _ in results.values())
    required_ids = {"FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3"}
    missing_ids = required_ids - set(results.keys())
    if missing_ids:
        for mid in missing_ids:
            print("[TEST] FAIL: {}: requirement was never evaluated".format(mid))
        all_ok = False
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()