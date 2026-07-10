#!/usr/bin/env python3
"""
evaluate.py -- Main grader for hls_bram_bounds_enforcement_001

Grades inputs/scratchpad_kernel.cpp BEHAVIORALLY:
  1. Compiles it together with evaluation/private/harness_main.cpp.
  2. Runs the resulting binary once per test-vector id (as defined in
     evaluation/private/test_vectors.py), each invocation isolated in its
     own subprocess with a timeout.
  3. Parses the single status line the harness prints and compares it
     against the Python-computed ground-truth expectation.
  4. Emits exactly one [TEST] PASS/FAIL line per requirement id
     (FR1-FR4, SR1-SR5).

Harness output-line contract (produced by evaluation/private/harness_main.cpp):

    MEM_BEFORE <96 space-separated 8-hex-digit words> STATUS <int> RET <int> MEM_AFTER <96 space-separated 8-hex-digit words>

Memory layout (96 words total, index 0..95):
    words[0:16)   -> canary_before[16]   (init = 0xA5A50000 + i)
    words[16:80)  -> scratchpad[64]      (init = 1000 + 3*i)
    words[80:96)  -> canary_after[16]    (init = 0x5A5A0000 + i)

All hex words represent the raw 32-bit pattern of the (possibly signed)
int32_t value, masked to 0xFFFFFFFF for comparison purposes.

test_vectors.py contract:
    BUFFER_SIZE = 64
    TEST_CASES: list of dicts {"id": int, "op": int, "index": int, "write_val": int}
    REQUIREMENT_TEST_IDS: dict requirement_id -> list of test-case ids (ints)
    initial_words(): -> list[int] of 96 unsigned 32-bit ints (the MEM_BEFORE ground truth)
    expected_result(test_case_dict): -> {"status": int, "ret": int, "mem_after": list[int] of 96 unsigned 32-bit ints}
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import shutil

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4", "SR5"]

INPUTS_KERNEL = "inputs/scratchpad_kernel.cpp"
HARNESS_SRC = "evaluation/private/harness_main.cpp"
TEST_VECTORS_PY = "evaluation/private/test_vectors.py"

TOTAL_WORDS = 96
COMPILE_TIMEOUT_S = 30
RUN_TIMEOUT_S = 5

results = {}  # requirement_id -> (bool passed, reason string)


def emit(req_id, passed, reason=""):
    if passed:
        print("[TEST] PASS: %s" % req_id)
    else:
        print("[TEST] FAIL: %s: %s" % (req_id, reason))
    results[req_id] = passed


def fail_all_with(reason):
    for r in REQUIREMENT_IDS:
        emit(r, False, reason)


def setup_fail(missing_path):
    print("[TEST] FAIL: SETUP: %s not found" % missing_path)
    sys.exit(1)


def load_module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def mask32(v):
    return v & 0xFFFFFFFF


def parse_harness_line(line):
    tokens = line.split()
    try:
        i_before = tokens.index("MEM_BEFORE")
        i_status = tokens.index("STATUS")
        i_ret = tokens.index("RET")
        i_after = tokens.index("MEM_AFTER")
    except ValueError:
        return None

    mem_before_toks = tokens[i_before + 1:i_status]
    mem_after_toks = tokens[i_after + 1:]

    if len(mem_before_toks) != TOTAL_WORDS or len(mem_after_toks) != TOTAL_WORDS:
        return None

    try:
        mem_before = [int(t, 16) for t in mem_before_toks]
        mem_after = [int(t, 16) for t in mem_after_toks]
        status = int(tokens[i_status + 1])
        ret = int(tokens[i_ret + 1])
    except ValueError:
        return None

    return {"mem_before": mem_before, "mem_after": mem_after, "status": status, "ret": ret}


def run_one_test(binary_path, test_id):
    """Run harness with given test id, return (ok, parsed_dict_or_None, reason)."""
    try:
        proc = subprocess.run(
            [binary_path, str(test_id)],
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return False, None, "run crashed/timed out"

    if proc.returncode != 0:
        return False, None, "run crashed/timed out (exit code %d)" % proc.returncode

    parsed = None
    for line in proc.stdout.splitlines():
        p = parse_harness_line(line)
        if p is not None:
            parsed = p
            break

    if parsed is None:
        return False, None, "run crashed/timed out (malformed harness output)"

    return True, parsed, ""


def evaluate_test_case(binary_path, tv_module, test_case):
    """Return (ok, reason) for a single test case against a single requirement."""
    test_id = test_case["id"]
    ok, parsed, reason = run_one_test(binary_path, test_id)
    if not ok:
        return False, "test id %s: %s" % (test_id, reason)

    # MEM_BEFORE sanity check against the known re-initialized state.
    expected_before = [mask32(w) for w in tv_module.initial_words()]
    if parsed["mem_before"] != expected_before:
        return False, "test id %s: MEM_BEFORE mismatch (harness init state unexpected)" % test_id

    expected = tv_module.expected_result(test_case)
    exp_status = expected["status"]
    exp_ret = expected["ret"]
    exp_mem_after = [mask32(w) for w in expected["mem_after"]]

    if parsed["status"] != exp_status:
        return False, "test id %s: status=%d expected=%d" % (test_id, parsed["status"], exp_status)

    if parsed["ret"] != exp_ret:
        return False, "test id %s: ret=%d expected=%d" % (test_id, parsed["ret"], exp_ret)

    if parsed["mem_after"] != exp_mem_after:
        return False, "test id %s: memory state mismatch after call (corruption or unexpected side effect)" % test_id

    return True, ""


def main():
    # --- SETUP checks -------------------------------------------------
    if not os.path.isfile(INPUTS_KERNEL):
        setup_fail(INPUTS_KERNEL)
    if not os.path.isfile(HARNESS_SRC):
        setup_fail(HARNESS_SRC)
    if not os.path.isfile(TEST_VECTORS_PY):
        setup_fail(TEST_VECTORS_PY)

    tmpdir = tempfile.mkdtemp(prefix="hls_bounds_eval_")
    binary_path = os.path.join(tmpdir, "harness")

    try:
        # --- Compile ----------------------------------------------------
        compile_cmd = [
            "g++", "-std=c++11", "-O0", "-Wall",
            "-o", binary_path,
            INPUTS_KERNEL, HARNESS_SRC,
        ]

        try:
            proc = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=COMPILE_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            fail_all_with("compile failed: g++ invocation timed out")
            sys.exit(1)

        if proc.returncode != 0:
            stderr_lines = [l for l in proc.stderr.splitlines() if l.strip()]
            first_err = stderr_lines[0] if stderr_lines else "unknown compile error"
            fail_all_with("compile failed: %s" % first_err)
            sys.exit(1)

        if not os.path.isfile(binary_path):
            fail_all_with("compile failed: binary not produced")
            sys.exit(1)

        # --- Load shared test-vector module ------------------------------
        try:
            tv_module = load_module_from_path("test_vectors", TEST_VECTORS_PY)
        except Exception as e:
            fail_all_with("compile failed: could not load test_vectors.py (%s)" % e)
            sys.exit(1)

        try:
            test_cases_by_id = {tc["id"]: tc for tc in tv_module.TEST_CASES}
            requirement_test_ids = tv_module.REQUIREMENT_TEST_IDS
        except Exception as e:
            fail_all_with("compile failed: malformed test_vectors.py (%s)" % e)
            sys.exit(1)

        # --- Run per-requirement checks ----------------------------------
        for req_id in REQUIREMENT_IDS:
            test_ids = requirement_test_ids.get(req_id, [])
            if not test_ids:
                emit(req_id, False, "no test vectors mapped to this requirement")
                continue

            req_ok = True
            req_reason = ""
            for test_id in test_ids:
                test_case = test_cases_by_id.get(test_id)
                if test_case is None:
                    req_ok = False
                    req_reason = "test id %s: not defined in TEST_CASES" % test_id
                    break

                ok, reason = evaluate_test_case(binary_path, tv_module, test_case)
                if not ok:
                    req_ok = False
                    req_reason = reason
                    break

            emit(req_id, req_ok, req_reason)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    if all(results.get(r, False) for r in REQUIREMENT_IDS):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()