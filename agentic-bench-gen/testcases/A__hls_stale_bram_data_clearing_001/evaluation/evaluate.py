#!/usr/bin/env python3
"""
evaluation/evaluate.py

Main grader entry point for the packet_kernel.cpp stale-buffer-clearing task.

Compiles the submitted inputs/packet_kernel.cpp together with
evaluation/harness_main.cpp, runs the resulting binary in several modes,
and derives PASS/FAIL verdicts for each requirement (FR1-FR4, SR1-SR3)
purely from observed program behavior (plus a compile-warning check for FR4).
"""

import os
import subprocess
import sys
import tempfile

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3"]

INPUT_FILE = "inputs/packet_kernel.cpp"
HARNESS_FILE = "evaluation/harness_main.cpp"

results = {}


def record_pass(req_id):
    results[req_id] = (True, "")
    print("[TEST] PASS: %s" % req_id)


def record_fail(req_id, reason):
    results[req_id] = (False, reason)
    print("[TEST] FAIL: %s: %s" % (req_id, reason))


def transform(b, i):
    return ((b ^ 0xA5) + i) & 0xFF


def pattern_a(i):
    # matches harness_main.cpp fill_pattern_a: (i*7+3) mod 256
    return (i * 7 + 3) & 0xFF


def parse_hex_line(line, expected_prefix_words):
    """
    Given a line like 'LEN 32: aa bb cc ...', return list of ints.
    expected_prefix_words is unused directly but kept for clarity of intent.
    """
    if ":" not in line:
        return None
    _, hexpart = line.split(":", 1)
    hexpart = hexpart.strip()
    if not hexpart:
        return []
    toks = hexpart.split()
    try:
        return [int(t, 16) for t in toks]
    except ValueError:
        return None


def main():
    # (1) Verify input file exists.
    if not os.path.isfile(INPUT_FILE):
        print("[TEST] FAIL: SETUP: %s not found" % INPUT_FILE)
        return 1

    if not os.path.isfile(HARNESS_FILE):
        print("[TEST] FAIL: SETUP: %s not found" % HARNESS_FILE)
        return 1

    tmpdir = tempfile.mkdtemp(prefix="pk_eval_")
    binary_path = os.path.join(tmpdir, "harness")

    compile_cmd = [
        "g++", "-std=c++11", "-O0", "-Wall", "-Wextra",
        "-o", binary_path,
        INPUT_FILE, HARNESS_FILE,
    ]

    try:
        proc = subprocess.run(
            compile_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        for rid in REQUIREMENT_IDS:
            record_fail(rid, "compile failed: compilation timed out")
        return 1

    stderr_text = proc.stderr.decode("utf-8", errors="replace")
    stderr_lines = [l for l in stderr_text.splitlines() if l.strip()]

    if proc.returncode != 0:
        first_line = stderr_lines[0] if stderr_lines else "unknown compiler error"
        for rid in REQUIREMENT_IDS:
            record_fail(rid, "compile failed: %s" % first_line)
        return 1

    # (3) FR4: compile succeeded; check for warnings.
    # g++ warning lines typically contain "warning:"
    warning_lines = [l for l in stderr_lines if "warning:" in l]
    if warning_lines:
        record_fail("FR4", "compile produced warnings: %s" % warning_lines[0])
    else:
        record_pass("FR4")

    # Helper to run the harness binary in a given mode.
    def run_harness(args, timeout_s):
        try:
            p = subprocess.run(
                [binary_path] + args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_s,
            )
            return p
        except subprocess.TimeoutExpired:
            return None

    # (4) fr_vectors mode.
    fr_lengths = [0, 1, 8, 17, 31, 32]
    fr_run = run_harness(["fr_vectors"], 10)

    fr_data = {}  # length -> list of 32 ints
    fr_crashed = False
    fr_crash_reason = ""

    if fr_run is None:
        fr_crashed = True
        fr_crash_reason = "run crashed/timed out"
    elif fr_run.returncode != 0:
        fr_crashed = True
        stderr_txt = fr_run.stderr.decode("utf-8", errors="replace").strip()
        first_err = stderr_txt.splitlines()[0] if stderr_txt else "nonzero exit code"
        fr_crash_reason = "run crashed/timed out: %s" % first_err
    else:
        stdout_txt = fr_run.stdout.decode("utf-8", errors="replace")
        lines = [l for l in stdout_txt.splitlines() if l.strip()]
        for line in lines:
            if line.startswith("LEN "):
                # format: "LEN <n>: <hex...>"
                try:
                    header, _ = line.split(":", 1)
                    n = int(header.split()[1])
                except (ValueError, IndexError):
                    continue
                bytes_list = parse_hex_line(line, None)
                if bytes_list is not None:
                    fr_data[n] = bytes_list

    if fr_crashed:
        record_fail("FR1", fr_crash_reason)
        record_fail("FR2", fr_crash_reason)
        record_fail("FR3", fr_crash_reason)
        record_fail("SR3", fr_crash_reason)
    else:
        # Verify all expected lengths present with 32 bytes each.
        missing_or_malformed = [
            n for n in fr_lengths
            if n not in fr_data or len(fr_data[n]) != 32
        ]

        if missing_or_malformed:
            reason = "missing or malformed output for length(s) %s" % missing_or_malformed
            record_fail("FR1", reason)
            record_fail("FR2", reason)
            record_fail("FR3", reason)
            record_fail("SR3", reason)
        else:
            in_buf = [pattern_a(i) for i in range(32)]

            # FR1: length=32 exact match.
            expected_32 = [transform(in_buf[i], i) for i in range(32)]
            actual_32 = fr_data[32]
            if actual_32 != expected_32:
                mismatches = [i for i in range(32) if actual_32[i] != expected_32[i]]
                record_fail(
                    "FR1",
                    "length=32 mismatch at index %d: expected 0x%02x got 0x%02x"
                    % (mismatches[0], expected_32[mismatches[0]], actual_32[mismatches[0]]),
                )
            else:
                record_pass("FR1")

            # FR2: length=0 all zero.
            actual_0 = fr_data[0]
            nonzero_idx = [i for i in range(32) if actual_0[i] != 0]
            if nonzero_idx:
                record_fail(
                    "FR2",
                    "length=0 output byte at index %d is nonzero: 0x%02x"
                    % (nonzero_idx[0], actual_0[nonzero_idx[0]]),
                )
            else:
                record_pass("FR2")

            # FR3: all six lengths correct prefix + zero suffix.
            fr3_fail_reason = None
            for n in fr_lengths:
                actual = fr_data[n]
                for i in range(32):
                    if i < n:
                        expected_byte = transform(in_buf[i], i)
                    else:
                        expected_byte = 0
                    if actual[i] != expected_byte:
                        fr3_fail_reason = (
                            "length=%d mismatch at index %d: expected 0x%02x got 0x%02x"
                            % (n, i, expected_byte, actual[i])
                        )
                        break
                if fr3_fail_reason:
                    break

            if fr3_fail_reason:
                record_fail("FR3", fr3_fail_reason)
            else:
                record_pass("FR3")

            # SR3: length=17 bytes [0,17) equal transform exactly.
            actual_17 = fr_data[17]
            sr3_fail_reason = None
            for i in range(17):
                expected_byte = transform(in_buf[i], i)
                if actual_17[i] != expected_byte:
                    sr3_fail_reason = (
                        "length=17 index %d: expected transform 0x%02x got 0x%02x"
                        % (i, expected_byte, actual_17[i])
                    )
                    break
            if sr3_fail_reason:
                record_fail("SR3", sr3_fail_reason)
            else:
                record_pass("SR3")

    # (5) sr1 mode: run twice, second_length=0 and second_length=4.
    sr1_overall_fail = None

    for second_length in [0, 4]:
        run = run_harness(["sr1", str(second_length)], 10)
        if run is None:
            sr1_overall_fail = "run crashed/timed out"
            break
        if run.returncode != 0:
            stderr_txt = run.stderr.decode("utf-8", errors="replace").strip()
            first_err = stderr_txt.splitlines()[0] if stderr_txt else "nonzero exit code"
            sr1_overall_fail = "run crashed/timed out: %s" % first_err
            break

        stdout_txt = run.stdout.decode("utf-8", errors="replace")
        lines = [l for l in stdout_txt.splitlines() if l.strip()]
        sr1_line = None
        for line in lines:
            if line.startswith("SR1 "):
                sr1_line = line
                break

        if sr1_line is None:
            sr1_overall_fail = "SR1 output line not found for second_length=%d" % second_length
            break

        bytes_list = parse_hex_line(sr1_line, None)
        if bytes_list is None or len(bytes_list) != 32:
            sr1_overall_fail = "malformed SR1 output for second_length=%d" % second_length
            break

        nonzero_idx = [i for i in range(second_length, 32) if bytes_list[i] != 0]
        if nonzero_idx:
            sr1_overall_fail = (
                "second_length=%d: stale nonzero byte at index %d: 0x%02x"
                % (second_length, nonzero_idx[0], bytes_list[nonzero_idx[0]])
            )
            break

    if sr1_overall_fail:
        record_fail("SR1", sr1_overall_fail)
    else:
        record_pass("SR1")

    # (6) sr2_sweep mode.
    sr2_fail_reason = None

    steps = [
        (32, 0xFF),
        (0, 1),
        (1, 2),
        (8, 3),
        (17, 4),
        (31, 5),
        (32, 6),
        (4, 7),
        (0, 8),
        (32, 9),
    ]

    def sweep_in_buf(pattern_id):
        if pattern_id == 0xFF:
            return [0xFF] * 32
        return [(i * 13 + pattern_id * 17 + 5) & 0xFF for i in range(32)]

    sweep_run = run_harness(["sr2_sweep"], 10)

    if sweep_run is None:
        sr2_fail_reason = "sr2_sweep: run crashed/timed out"
    elif sweep_run.returncode != 0:
        stderr_txt = sweep_run.stderr.decode("utf-8", errors="replace").strip()
        first_err = stderr_txt.splitlines()[0] if stderr_txt else "nonzero exit code"
        sr2_fail_reason = "sr2_sweep: run crashed/timed out: %s" % first_err
    else:
        stdout_txt = sweep_run.stdout.decode("utf-8", errors="replace")
        lines = [l for l in stdout_txt.splitlines() if l.strip()]
        call_lines = [l for l in lines if l.startswith("CALL ")]

        if len(call_lines) != len(steps):
            sr2_fail_reason = (
                "sr2_sweep: expected %d CALL lines, got %d" % (len(steps), len(call_lines))
            )
        else:
            for idx, line in enumerate(call_lines):
                try:
                    header, _ = line.split(":", 1)
                    parts = header.split()
                    # header format: CALL <idx> LEN <len>
                    call_len = int(parts[3])
                except (ValueError, IndexError):
                    sr2_fail_reason = "sr2_sweep: malformed header at call %d" % idx
                    break

                expected_length, pattern_id = steps[idx]
                if call_len != expected_length:
                    sr2_fail_reason = (
                        "sr2_sweep: call %d expected length %d, got %d"
                        % (idx, expected_length, call_len)
                    )
                    break

                bytes_list = parse_hex_line(line, None)
                if bytes_list is None or len(bytes_list) != 32:
                    sr2_fail_reason = "sr2_sweep: malformed output bytes at call %d" % idx
                    break

                in_buf = sweep_in_buf(pattern_id)

                mismatch = None
                for i in range(32):
                    if i < call_len:
                        expected_byte = transform(in_buf[i], i)
                    else:
                        expected_byte = 0
                    if bytes_list[i] != expected_byte:
                        mismatch = (i, expected_byte, bytes_list[i])
                        break

                if mismatch is not None:
                    i, expected_byte, actual_byte = mismatch
                    kind = "stale/leftover" if i >= call_len else "transform"
                    sr2_fail_reason = (
                        "sr2_sweep: call %d (len=%d) %s mismatch at index %d: expected 0x%02x got 0x%02x"
                        % (idx, call_len, kind, i, expected_byte, actual_byte)
                    )
                    break

    # (7) sr_random100 mode.
    if sr2_fail_reason is None:
        rand_run = run_harness(["sr_random100"], 15)

        if rand_run is None:
            sr2_fail_reason = "sr_random100: run crashed/timed out"
        elif rand_run.returncode != 0:
            stderr_txt = rand_run.stderr.decode("utf-8", errors="replace").strip()
            first_err = stderr_txt.splitlines()[0] if stderr_txt else "nonzero exit code"
            sr2_fail_reason = "sr_random100: run crashed/timed out: %s" % first_err
        else:
            stdout_txt = rand_run.stdout.decode("utf-8", errors="replace")
            lines = [l for l in stdout_txt.splitlines() if l.strip()]
            rcall_lines = [l for l in lines if l.startswith("RCALL ")]

            if len(rcall_lines) != 100:
                sr2_fail_reason = (
                    "sr_random100: expected 100 RCALL lines, got %d" % len(rcall_lines)
                )
            else:
                for idx, line in enumerate(rcall_lines):
                    try:
                        header, _ = line.split(":", 1)
                        parts = header.split()
                        # header format: RCALL <idx> LEN <len>
                        call_len = int(parts[3])
                    except (ValueError, IndexError):
                        sr2_fail_reason = "sr_random100: malformed header at call %d" % idx
                        break

                    if call_len < 0 or call_len > 32:
                        sr2_fail_reason = (
                            "sr_random100: call %d has out-of-range length %d" % (idx, call_len)
                        )
                        break

                    bytes_list = parse_hex_line(line, None)
                    if bytes_list is None or len(bytes_list) != 32:
                        sr2_fail_reason = "sr_random100: malformed output bytes at call %d" % idx
                        break

                    nonzero_idx = [i for i in range(call_len, 32) if bytes_list[i] != 0]
                    if nonzero_idx:
                        sr2_fail_reason = (
                            "sr_random100: call %d (len=%d) stale nonzero byte at index %d: 0x%02x"
                            % (idx, call_len, nonzero_idx[0], bytes_list[nonzero_idx[0]])
                        )
                        break

    if sr2_fail_reason:
        record_fail("SR2", sr2_fail_reason)
    else:
        record_pass("SR2")

    all_pass = all(results.get(rid, (False, "missing"))[0] for rid in REQUIREMENT_IDS)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())