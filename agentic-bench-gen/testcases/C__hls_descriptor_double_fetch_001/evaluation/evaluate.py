#!/usr/bin/env python3
"""
evaluation/evaluate.py

Main grading entry point for task hls_descriptor_double_fetch_001.

Grades inputs/descriptor_transfer.cpp (paired with the unmodified
inputs/descriptor_transfer.h) IN PLACE by compiling it together with
evaluation/harness_main.cpp using g++, then executing the resulting binary
under several scenarios and parsing its deterministic RESULT: output lines.

Requirement ids checked: FR1, FR2, FR3, FR4, SR1, SR2, SR3.

Exit code: 0 if every requirement PASSes, 1 otherwise.
"""

import os
import subprocess
import sys
import tempfile

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3"]

INPUTS_DIR = "inputs"
EVAL_DIR = "evaluation"

HEADER_FILE = os.path.join(INPUTS_DIR, "descriptor_transfer.h")
SRC_FILE = os.path.join(INPUTS_DIR, "descriptor_transfer.cpp")
HARNESS_SRC = os.path.join(EVAL_DIR, "harness_main.cpp")

COMPILE_TIMEOUT_SEC = 30
RUN_TIMEOUT_SEC = 60

EXPECTED_SR_TRIALS = 300

results = {}  # requirement_id -> (bool passed, str reason_if_failed)


def emit(req_id, passed, reason=""):
    if req_id in results:
        return
    results[req_id] = (passed, reason)
    if passed:
        print("[TEST] PASS: {}".format(req_id))
    else:
        print("[TEST] FAIL: {}: {}".format(req_id, reason))


def fail_all_remaining(reason):
    for rid in REQUIREMENT_IDS:
        if rid not in results:
            emit(rid, False, reason)


def check_setup_files():
    missing = []
    if not os.path.isfile(HEADER_FILE):
        missing.append(HEADER_FILE)
    if not os.path.isfile(SRC_FILE):
        missing.append(SRC_FILE)
    if not os.path.isfile(HARNESS_SRC):
        missing.append(HARNESS_SRC)

    if missing:
        for path in missing:
            print("[TEST] FAIL: SETUP: {} not found".format(path))
        fail_all_remaining("SETUP: required file not found ({})".format(
            ", ".join(missing)))
        return False
    return True


def compile_submission(tmpdir):
    binary_path = os.path.join(tmpdir, "harness_bin")
    cmd = [
        "g++", "-std=c++11", "-O0", "-pthread",
        "-I", INPUTS_DIR,
        "-o", binary_path,
        SRC_FILE, HARNESS_SRC,
    ]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=COMPILE_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        return None, "compile timed out after {}s".format(COMPILE_TIMEOUT_SEC)

    if proc.returncode != 0:
        stderr_text = proc.stderr.decode("utf-8", errors="replace")
        lines = [l for l in stderr_text.splitlines() if l.strip()]
        excerpt = "\n".join(lines[:25])
        if len(excerpt) > 2000:
            excerpt = excerpt[:2000]
        return None, "compile failed: {}".format(excerpt)

    return binary_path, None


def run_scenario(binary_path, scenario):
    cmd = [binary_path, scenario]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=RUN_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        return None, "run crashed/timed out: scenario '{}' exceeded {}s".format(
            scenario, RUN_TIMEOUT_SEC)

    if proc.returncode != 0:
        stderr_text = proc.stderr.decode("utf-8", errors="replace").strip()
        return None, "run crashed/timed out: scenario '{}' exited with code {} ({})".format(
            scenario, proc.returncode, stderr_text[:500])

    stdout_text = proc.stdout.decode("utf-8", errors="replace")
    return stdout_text, None


def parse_result_lines(stdout_text, scenario_prefix):
    """
    Parses lines of the form:
      RESULT:<scenario>:key1=val1:key2=val2:...
    Returns a list of dicts, one per matching RESULT line, each containing
    the parsed key/value pairs (plus '_scenario' for the scenario token).
    """
    parsed = []
    for line in stdout_text.splitlines():
        line = line.strip()
        if not line.startswith("RESULT:"):
            continue
        parts = line.split(":")
        if len(parts) < 2:
            continue
        scenario_tok = parts[1]
        if scenario_tok != scenario_prefix:
            continue
        fields = {"_scenario": scenario_tok}
        for field in parts[2:]:
            if "=" in field:
                k, v = field.split("=", 1)
                fields[k] = v
        parsed.append(fields)
    return parsed


def main():
    if not check_setup_files():
        return 1

    with tempfile.TemporaryDirectory() as tmpdir:
        binary_path, compile_err = compile_submission(tmpdir)

        if binary_path is None:
            fail_all_remaining(compile_err)
            return 1

        # If we got here, compile + link succeeded. Since the harness
        # references extern "C" run_transfer(Descriptor*, uint8_t*, uint32_t)
        # and struct Descriptor{ volatile uint32_t length; uint8_t data[256]; }
        # exactly as pinned in public_spec.interface, successful compilation
        # and linking is itself the behavioral proof that FR4 (interface /
        # struct fidelity) holds: any deviation would produce a compile or
        # link error above.
        emit("FR4", True)

        # ---- FR1 ----
        stdout_text, run_err = run_scenario(binary_path, "fr1")
        if run_err is not None:
            emit("FR1", False, run_err)
        else:
            recs = parse_result_lines(stdout_text, "fr1")
            if not recs:
                emit("FR1", False, "no RESULT:fr1 line produced by harness")
            else:
                r = recs[0]
                ret_ok = r.get("ret") == "32"
                bytes_ok = r.get("bytes") == "match"
                canary_ok = r.get("canary_ok") == "1"
                if ret_ok and bytes_ok and canary_ok:
                    emit("FR1", True)
                else:
                    emit("FR1", False,
                         "expected ret=32,bytes=match,canary_ok=1 but got {}".format(r))

        # ---- FR2 ----
        stdout_text, run_err = run_scenario(binary_path, "fr2")
        fr2_record = None
        if run_err is not None:
            emit("FR2", False, run_err)
        else:
            recs = parse_result_lines(stdout_text, "fr2")
            if not recs:
                emit("FR2", False, "no RESULT:fr2 line produced by harness")
            else:
                fr2_record = recs[0]
                ret_ok = fr2_record.get("ret") == "-1"
                unchanged_ok = fr2_record.get("bytes") == "unchanged"
                canary_ok = fr2_record.get("canary_ok") == "1"
                if ret_ok and unchanged_ok and canary_ok:
                    emit("FR2", True)
                else:
                    emit("FR2", False,
                         "expected ret=-1,bytes=unchanged,canary_ok=1 but got {}".format(
                             fr2_record))

        # ---- FR3 ----
        stdout_text, run_err = run_scenario(binary_path, "fr3")
        if run_err is not None:
            emit("FR3", False, run_err)
        else:
            recs = parse_result_lines(stdout_text, "fr3")
            if not recs:
                emit("FR3", False, "no RESULT:fr3 line produced by harness")
            else:
                r = recs[0]
                ret_ok = r.get("ret") == "0"
                unchanged_ok = r.get("bytes") == "unchanged"
                canary_ok = r.get("canary_ok") == "1"
                if ret_ok and unchanged_ok and canary_ok:
                    emit("FR3", True)
                else:
                    emit("FR3", False,
                         "expected ret=0,bytes=unchanged,canary_ok=1 but got {}".format(r))

        # ---- SR3 (rejection path: zero bytes copied, dest untouched) ----
        # Reuses the fr2 run/result captured above (length=500 > max_len=256,
        # no mutation involved) to independently anchor the rejection-path
        # contract.
        if fr2_record is not None:
            ret_ok = fr2_record.get("ret") == "-1"
            unchanged_ok = fr2_record.get("bytes") == "unchanged"
            canary_ok = fr2_record.get("canary_ok") == "1"
            if ret_ok and unchanged_ok and canary_ok:
                emit("SR3", True)
            else:
                emit("SR3", False,
                     "rejection path did not leave dest untouched / return!=-1: {}".format(
                         fr2_record))
        else:
            emit("SR3", False, "fr2 scenario did not produce a usable RESULT line")

        # ---- SR1 / SR2 (TOCTOU race trials) ----
        stdout_text, run_err = run_scenario(binary_path, "sr1_toctou")
        if run_err is not None:
            emit("SR1", False, run_err)
            emit("SR2", False, run_err)
        else:
            recs = parse_result_lines(stdout_text, "sr1_toctou")
            if not recs:
                emit("SR1", False, "no RESULT:sr1_toctou lines produced by harness")
                emit("SR2", False, "no RESULT:sr1_toctou lines produced by harness")
            else:
                expected_trials = EXPECTED_SR_TRIALS
                if len(recs) < expected_trials:
                    reason = ("expected {} sr1_toctou trials, only observed {}"
                              .format(expected_trials, len(recs)))
                    emit("SR1", False, reason)
                    emit("SR2", False, reason)
                else:
                    sr1_failures = []
                    sr2_failures = []
                    for r in recs:
                        trial = r.get("trial", "?")
                        ret = r.get("ret")
                        match200 = r.get("match200")
                        canary_ok = r.get("canary_ok")

                        # SR1: the read must behave as at-most-once — every
                        # trial's observed outcome (return value AND copied
                        # bytes) must be consistent with only the
                        # pre-mutation value (200) having ever been used.
                        if match200 != "1":
                            sr1_failures.append(
                                "trial={} ret={} match200={} (expected ret=200 and bytes[0:200] matching pattern)".format(
                                    trial, ret, match200))
                        if canary_ok != "1":
                            sr1_failures.append(
                                "trial={} canary_ok={} (guard/canary region beyond validated length was modified)".format(
                                    trial, canary_ok))

                        # SR2: the value validated and the value used to
                        # bound the copy must be identical in every trial —
                        # i.e. never a partial/hybrid outcome diverging from
                        # the pre-mutation validated length of 200.
                        if match200 != "1" or canary_ok != "1":
                            sr2_failures.append(
                                "trial={} ret={} match200={} canary_ok={} (copy bound diverged from validated length 200)".format(
                                    trial, ret, match200, canary_ok))

                    if sr1_failures:
                        emit("SR1", False,
                             "{} of {} trials violated single-read semantics; first: {}".format(
                                 len(sr1_failures), len(recs), sr1_failures[0]))
                    else:
                        emit("SR1", True)

                    if sr2_failures:
                        emit("SR2", False,
                             "{} of {} trials show validated value != value used for copy; first: {}".format(
                                 len(sr2_failures), len(recs), sr2_failures[0]))
                    else:
                        emit("SR2", True)

    # Ensure every requirement got a verdict (defensive; should already be
    # true by construction above).
    fail_all_remaining("requirement was not evaluated due to an internal harness gap")

    all_passed = all(passed for passed, _ in results.values())
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())