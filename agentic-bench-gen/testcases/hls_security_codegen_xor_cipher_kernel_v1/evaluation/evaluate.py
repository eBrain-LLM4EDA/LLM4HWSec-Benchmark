#!/usr/bin/env python3
"""
evaluation/evaluate.py

Behavioral grader for the Constant-Behavior XOR-Cipher HLS Kernel task.

Compiles inputs/crypto_kernel.c with both gcc and g++, links the
gcc-compiled kernel object against evaluation/harness_main.cpp (compiled
and linked with g++), runs the resulting binary twice, and derives
PASS/FAIL for FR1, SR1, SR2, SR3, SR4 purely from observed behavior.
"""

import os
import re
import subprocess
import sys
import tempfile

REQUIREMENT_IDS = ["FR1", "SR1", "SR2", "SR3", "SR4"]

INPUT_KERNEL = os.path.join("inputs", "crypto_kernel.c")
HARNESS_SRC = os.path.join("evaluation", "harness_main.cpp")

COMPILE_TIMEOUT = 30
RUN_TIMEOUT = 10

VEC_RE = re.compile(
    r'^VEC idx=(\d+) plaintext=([0-9a-f]{32}) key=([0-9a-f]{32}) '
    r'status=(-?\d+) iter=(\d+) cipher=([0-9a-f]{32})\s*$'
)
SWEEP_RE = re.compile(
    r'^SWEEP idx=(\d+) plaintext=([0-9a-f]{32}) key=([0-9a-f]{32}) '
    r'status=(-?\d+) iter=(\d+) cipher=([0-9a-f]{32})\s*$'
)


def hex_to_bytes(h):
    return [int(h[i:i + 2], 16) for i in range(0, len(h), 2)]


def first_stderr_line(stderr_text):
    if not stderr_text:
        return "(no stderr captured)"
    for line in stderr_text.splitlines():
        line = line.strip()
        if line:
            return line
    return "(empty stderr)"


def run_cmd(cmd, timeout):
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired as e:
        out = e.stdout if e.stdout is not None else b""
        err = e.stderr if e.stderr is not None else b""
        return None, out, err, True
    except FileNotFoundError as e:
        return None, b"", str(e).encode(), False


def fail_all(reason, results, prefix="compile failed"):
    for rid in REQUIREMENT_IDS:
        msg = "[TEST] FAIL: {}: {}: {}".format(rid, prefix, reason)
        print(msg)
        results[rid] = False


def crash_all(reason, results):
    for rid in REQUIREMENT_IDS:
        msg = "[TEST] FAIL: {}: run crashed/timed out: {}".format(rid, reason)
        print(msg)
        results[rid] = False


def main():
    results = {}

    # ------------------------------------------------------------------
    # Step 1: SETUP checks
    # ------------------------------------------------------------------
    if not os.path.isfile(INPUT_KERNEL):
        print("[TEST] FAIL: SETUP: {} not found".format(INPUT_KERNEL))
        return 1

    if not os.path.isfile(HARNESS_SRC):
        print("[TEST] FAIL: SETUP: {} not found".format(HARNESS_SRC))
        return 1

    tmpdir = tempfile.mkdtemp(prefix="hls_eval_")

    kernel_gcc_o = os.path.join(tmpdir, "kernel_gcc.o")
    kernel_gpp_o = os.path.join(tmpdir, "kernel_gpp.o")
    harness_o = os.path.join(tmpdir, "harness.o")
    harness_bin = os.path.join(tmpdir, "harness")

    # ------------------------------------------------------------------
    # Step 2: compile inputs/crypto_kernel.c with gcc and g++ (compile-only)
    # ------------------------------------------------------------------
    gcc_cmd = ["gcc", "-std=c11", "-Wall", "-Wextra", "-c", INPUT_KERNEL, "-o", kernel_gcc_o]
    rc, out, err, timed_out = run_cmd(gcc_cmd, COMPILE_TIMEOUT)
    if timed_out:
        fail_all("gcc compile timed out", results)
        return 1
    if rc != 0:
        line = first_stderr_line(err.decode(errors="replace"))
        fail_all(line, results)
        return 1

    gpp_cmd = ["g++", "-std=c++11", "-Wall", "-c", INPUT_KERNEL, "-o", kernel_gpp_o]
    rc, out, err, timed_out = run_cmd(gpp_cmd, COMPILE_TIMEOUT)
    if timed_out:
        fail_all("g++ compile timed out", results)
        return 1
    if rc != 0:
        line = first_stderr_line(err.decode(errors="replace"))
        fail_all(line, results)
        return 1

    # ------------------------------------------------------------------
    # Step 3: build runnable harness (gcc kernel object + g++ harness object)
    # ------------------------------------------------------------------
    harness_compile_cmd = ["g++", "-std=c++11", "-O0", "-c", HARNESS_SRC, "-o", harness_o]
    rc, out, err, timed_out = run_cmd(harness_compile_cmd, COMPILE_TIMEOUT)
    if timed_out:
        fail_all("harness compile timed out", results)
        return 1
    if rc != 0:
        line = first_stderr_line(err.decode(errors="replace"))
        fail_all(line, results)
        return 1

    link_cmd = ["g++", "-O0", "-o", harness_bin, kernel_gcc_o, harness_o]
    rc, out, err, timed_out = run_cmd(link_cmd, COMPILE_TIMEOUT)
    if timed_out:
        fail_all("link timed out", results)
        return 1
    if rc != 0:
        line = first_stderr_line(err.decode(errors="replace"))
        fail_all(line, results)
        return 1

    # ------------------------------------------------------------------
    # Step 4: run the harness twice, require deterministic crash-free output
    # ------------------------------------------------------------------
    rc1, out1, err1, timed_out1 = run_cmd([harness_bin], RUN_TIMEOUT)
    if timed_out1:
        crash_all("first run timed out", results)
        return 1
    if rc1 != 0:
        crash_all("first run exited with code {}".format(rc1), results)
        return 1

    rc2, out2, err2, timed_out2 = run_cmd([harness_bin], RUN_TIMEOUT)
    if timed_out2:
        crash_all("second run timed out", results)
        return 1
    if rc2 != 0:
        crash_all("second run exited with code {}".format(rc2), results)
        return 1

    if out1 != out2:
        crash_all("nondeterministic output between two runs", results)
        return 1

    stdout_text = out1.decode(errors="replace")

    # ------------------------------------------------------------------
    # Step 5: parse VEC and SWEEP records
    # ------------------------------------------------------------------
    vec_records = []
    sweep_records = []

    for line in stdout_text.splitlines():
        m = VEC_RE.match(line)
        if m:
            idx = int(m.group(1))
            plaintext = hex_to_bytes(m.group(2))
            key = hex_to_bytes(m.group(3))
            status = int(m.group(4))
            iter_count = int(m.group(5))
            cipher = hex_to_bytes(m.group(6))
            vec_records.append({
                "idx": idx,
                "plaintext": plaintext,
                "key": key,
                "status": status,
                "iter": iter_count,
                "cipher": cipher,
            })
            continue
        m = SWEEP_RE.match(line)
        if m:
            idx = int(m.group(1))
            plaintext = hex_to_bytes(m.group(2))
            key = hex_to_bytes(m.group(3))
            status = int(m.group(4))
            iter_count = int(m.group(5))
            cipher = hex_to_bytes(m.group(6))
            sweep_records.append({
                "idx": idx,
                "plaintext": plaintext,
                "key": key,
                "status": status,
                "iter": iter_count,
                "cipher": cipher,
            })
            continue

    # ------------------------------------------------------------------
    # Step 6: FR1 - known-answer vectors: cipher == plaintext XOR key
    # ------------------------------------------------------------------
    if len(vec_records) == 0:
        print("[TEST] FAIL: FR1: no VEC records found in harness output (parse failure or run failure)")
        results["FR1"] = False
    else:
        fr1_ok = True
        fr1_reason = None
        for rec in vec_records:
            expected_cipher = [rec["plaintext"][i] ^ rec["key"][i] for i in range(16)]
            if rec["cipher"] != expected_cipher:
                fr1_ok = False
                fr1_reason = "known-answer vector {} ciphertext mismatch".format(rec["idx"])
                break
        if fr1_ok:
            print("[TEST] PASS: FR1")
            results["FR1"] = True
        else:
            print("[TEST] FAIL: FR1: {}".format(fr1_reason))
            results["FR1"] = False

    # ------------------------------------------------------------------
    # Step 7: sweep coverage + plaintext-invariance precheck (feeds SR1)
    # ------------------------------------------------------------------
    sr1_precheck_failed = False
    sr1_precheck_reason = None

    if len(sweep_records) < 200:
        sr1_precheck_failed = True
        sr1_precheck_reason = "insufficient sweep coverage: only {} sweep records found (need >= 200)".format(
            len(sweep_records)
        )
    else:
        first_plaintext = sweep_records[0]["plaintext"]
        for rec in sweep_records:
            if rec["plaintext"] != first_plaintext:
                sr1_precheck_failed = True
                sr1_precheck_reason = "plaintext varied during sweep - harness invariant broken at idx {}".format(
                    rec["idx"]
                )
                break

    # ------------------------------------------------------------------
    # Step 8: SR1 - status_out invariance and correctness
    # ------------------------------------------------------------------
    if sr1_precheck_failed:
        print("[TEST] FAIL: SR1: {}".format(sr1_precheck_reason))
        results["SR1"] = False
    else:
        plaintext = sweep_records[0]["plaintext"]
        expected_status = 0
        for b in plaintext:
            expected_status ^= b
        # match (int)(p0^p1^...^p15): result of XOR-fold of uint8_t values
        # promoted to int is just the folded byte value as a non-negative int
        sr1_ok = True
        sr1_reason = None
        for rec in sweep_records:
            if rec["status"] != expected_status:
                sr1_ok = False
                sr1_reason = "key-dependent status_out detected at sweep idx {} (status={} expected={})".format(
                    rec["idx"], rec["status"], expected_status
                )
                break
        if sr1_ok:
            print("[TEST] PASS: SR1")
            results["SR1"] = True
        else:
            print("[TEST] FAIL: SR1: {}".format(sr1_reason))
            results["SR1"] = False

    # ------------------------------------------------------------------
    # Step 9: SR2 - iter_count_out constancy (== 16)
    # ------------------------------------------------------------------
    if len(sweep_records) == 0:
        print("[TEST] FAIL: SR2: no SWEEP records found in harness output (parse failure or run failure)")
        results["SR2"] = False
    else:
        sr2_ok = True
        sr2_reason = None
        for rec in sweep_records:
            if rec["iter"] != 16:
                sr2_ok = False
                sr2_reason = "iter_count_out={} != 16 at sweep idx {} (possible early-exit)".format(
                    rec["iter"], rec["idx"]
                )
                break
        if sr2_ok:
            print("[TEST] PASS: SR2")
            results["SR2"] = True
        else:
            print("[TEST] FAIL: SR2: {}".format(sr2_reason))
            results["SR2"] = False

    # ------------------------------------------------------------------
    # Step 10: SR3 - ciphertext functional correctness across all records
    # ------------------------------------------------------------------
    if len(sweep_records) == 0 and len(vec_records) == 0:
        print("[TEST] FAIL: SR3: no VEC or SWEEP records found in harness output")
        results["SR3"] = False
    else:
        sr3_ok = True
        sr3_reason = None
        for rec in vec_records:
            expected_cipher = [rec["plaintext"][i] ^ rec["key"][i] for i in range(16)]
            if rec["cipher"] != expected_cipher:
                sr3_ok = False
                sr3_reason = "ciphertext mismatch at record VEC idx={}".format(rec["idx"])
                break
        if sr3_ok:
            for rec in sweep_records:
                expected_cipher = [rec["plaintext"][i] ^ rec["key"][i] for i in range(16)]
                if rec["cipher"] != expected_cipher:
                    sr3_ok = False
                    sr3_reason = "ciphertext mismatch at record SWEEP idx={}".format(rec["idx"])
                    break
        if sr3_ok:
            print("[TEST] PASS: SR3")
            results["SR3"] = True
        else:
            print("[TEST] FAIL: SR3: {}".format(sr3_reason))
            results["SR3"] = False

    # ------------------------------------------------------------------
    # Step 11: SR4 - no observable behavioral difference across differing keys
    # ------------------------------------------------------------------
    if len(sweep_records) == 0:
        print("[TEST] FAIL: SR4: no SWEEP records found in harness output (parse failure or run failure)")
        results["SR4"] = False
    else:
        reference = (sweep_records[0]["status"], sweep_records[0]["iter"])
        sr4_ok = True
        sr4_reason = None
        for rec in sweep_records:
            tup = (rec["status"], rec["iter"])
            if tup != reference:
                sr4_ok = False
                sr4_reason = "observable behavior differs between keys at sweep idx {} (tuple={} reference={})".format(
                    rec["idx"], tup, reference
                )
                break
        if sr4_ok:
            print("[TEST] PASS: SR4")
            results["SR4"] = True
        else:
            print("[TEST] FAIL: SR4: {}".format(sr4_reason))
            results["SR4"] = False

    # ------------------------------------------------------------------
    # Step 12: final verdict
    # ------------------------------------------------------------------
    all_pass = all(results.get(rid, False) for rid in REQUIREMENT_IDS)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())