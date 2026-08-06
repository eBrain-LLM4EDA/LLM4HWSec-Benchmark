#!/usr/bin/env python3
"""
evaluate.py -- Hamming(7,4) SEC decoder recovery grader.

Grades submission/recovered_rtl.v behaviorally against inputs/flattened_netlist.v
by compiling both together with evaluation/tb_top.v under iverilog, running the
resulting simulation under vvp, and comparing the exhaustive 128-codeword sweep
of outputs between the reference and the submission.
"""

import os
import re
import subprocess
import sys
import tempfile

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2"]

INPUT_NETLIST = "inputs/flattened_netlist.v"
INPUT_BRIEF = "inputs/design_brief.md"
SUBMISSION = "submission/recovered_rtl.v"
TESTBENCH = "evaluation/tb_top.v"

IVERILOG_TIMEOUT = 60
VVP_TIMEOUT = 60

VEC_RE = re.compile(
    r"^VEC\s+(\d+)\s+([01]{4})\s+([01]{7})\s+([01])\s+([01]{4})\s+([01]{7})\s+([01])\s*$"
)


def fail_all(reason):
    for rid in REQUIREMENT_IDS:
        print("[TEST] FAIL: %s: %s" % (rid, reason))
    sys.exit(1)


def main():
    # (1) verify input artifacts exist
    if not os.path.isfile(INPUT_NETLIST):
        print("[TEST] FAIL: SETUP: %s not found" % INPUT_NETLIST)
        sys.exit(1)
    if not os.path.isfile(INPUT_BRIEF):
        print("[TEST] FAIL: SETUP: %s not found" % INPUT_BRIEF)
        sys.exit(1)

    # (2) verify submission exists
    if not os.path.isfile(SUBMISSION):
        print("[TEST] FAIL: SETUP: %s not found" % SUBMISSION)
        sys.exit(1)

    if not os.path.isfile(TESTBENCH):
        print("[TEST] FAIL: SETUP: %s not found" % TESTBENCH)
        sys.exit(1)

    with open(SUBMISSION, "r", encoding="utf-8", errors="replace") as f:
        sub_source = f.read()

    # (3) static fail-on-presence scan for clocked always blocks
    # Vulnerability/banned-construct pattern: a clocked always block would
    # make the module sequential, violating the purely-combinational
    # interface contract (no clock, no internal state).
    clocked_always_pattern = re.compile(
        r"always\s*@\s*\(\s*(?:posedge|negedge)\s+\w+"
    )
    has_clocked_always = bool(clocked_always_pattern.search(sub_source))

    # (4) compile with iverilog
    with tempfile.TemporaryDirectory() as tmpdir:
        sim_path = os.path.join(tmpdir, "sim.vvp")
        compile_cmd = [
            "iverilog",
            "-g2012",
            "-o",
            sim_path,
            INPUT_NETLIST,
            SUBMISSION,
            TESTBENCH,
        ]
        try:
            compile_proc = subprocess.run(
                compile_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=IVERILOG_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            fail_all("compile failed: iverilog timed out")
            return
        except FileNotFoundError as e:
            fail_all("compile failed: iverilog not found: %s" % e)
            return

        if compile_proc.returncode != 0:
            stderr_text = compile_proc.stderr.decode("utf-8", errors="replace")
            summary = " | ".join(
                line.strip() for line in stderr_text.splitlines() if line.strip()
            )[:800]
            if not summary:
                summary = "iverilog exited with code %d, no stderr" % compile_proc.returncode
            fail_all("compile failed: %s" % summary)
            return

        # (5) run vvp
        run_cmd = ["vvp", sim_path]
        try:
            run_proc = subprocess.run(
                run_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=VVP_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            for rid in REQUIREMENT_IDS:
                print("[TEST] FAIL: %s: run crashed/timed out" % rid)
            sys.exit(1)
            return

        stdout_text = run_proc.stdout.decode("utf-8", errors="replace")

    # (6) parse VEC lines
    vectors = []
    for line in stdout_text.splitlines():
        m = VEC_RE.match(line.strip())
        if m:
            codeword_val = int(m.group(1))
            vectors.append(
                {
                    "codeword": codeword_val,
                    "ref_data": m.group(2),
                    "ref_corrected": m.group(3),
                    "ref_error": m.group(4),
                    "sub_data": m.group(5),
                    "sub_corrected": m.group(6),
                    "sub_error": m.group(7),
                }
            )

    if len(vectors) < 128:
        for rid in REQUIREMENT_IDS:
            print(
                "[TEST] FAIL: %s: run crashed/timed out (parsed %d/128 VEC lines)"
                % (rid, len(vectors))
            )
        sys.exit(1)
        return

    # De-duplicate by codeword in case of any repeated lines, keep first 128 distinct
    by_codeword = {}
    for v in vectors:
        if v["codeword"] not in by_codeword:
            by_codeword[v["codeword"]] = v

    if len(by_codeword) < 128:
        for rid in REQUIREMENT_IDS:
            print(
                "[TEST] FAIL: %s: run crashed/timed out (only %d distinct codewords observed)"
                % (rid, len(by_codeword))
            )
        sys.exit(1)
        return

    rows = [by_codeword[c] for c in range(128)]

    overall_pass = True

    # FR1: full exhaustive equivalence on all 128 codewords
    fr1_mismatches = []
    for v in rows:
        if (
            v["sub_data"] != v["ref_data"]
            or v["sub_corrected"] != v["ref_corrected"]
            or v["sub_error"] != v["ref_error"]
        ):
            fr1_mismatches.append(v["codeword"])

    if not fr1_mismatches:
        print("[TEST] PASS: FR1")
    else:
        overall_pass = False
        print(
            "[TEST] FAIL: FR1: %d/128 mismatches, e.g. codeword=%d"
            % (len(fr1_mismatches), fr1_mismatches[0])
        )

    # FR2: error-free codewords (reference error_detected == 0) pass through unchanged
    clean_rows = [v for v in rows if v["ref_error"] == "0"]
    fr2_mismatches = []
    for v in clean_rows:
        expected_corrected = format(v["codeword"], "07b")
        if v["sub_error"] != "0" or v["sub_corrected"] != expected_corrected:
            fr2_mismatches.append(v["codeword"])

    if len(clean_rows) == 0:
        overall_pass = False
        print("[TEST] FAIL: FR2: no error-free reference vectors found (unexpected reference behavior)")
    elif not fr2_mismatches:
        print("[TEST] PASS: FR2")
    else:
        overall_pass = False
        print(
            "[TEST] FAIL: FR2: %d/%d clean-codeword mismatches, e.g. codeword=%d"
            % (len(fr2_mismatches), len(clean_rows), fr2_mismatches[0])
        )

    # FR3: single-bit-error codewords (reference error_detected == 1) corrected properly
    err_rows = [v for v in rows if v["ref_error"] == "1"]
    fr3_mismatches = []
    for v in err_rows:
        if v["sub_error"] != "1" or v["sub_corrected"] != v["ref_corrected"]:
            fr3_mismatches.append(v["codeword"])

    if len(err_rows) == 0:
        overall_pass = False
        print("[TEST] FAIL: FR3: no single-error reference vectors found (unexpected reference behavior)")
    elif not fr3_mismatches:
        print("[TEST] PASS: FR3")
    else:
        overall_pass = False
        print(
            "[TEST] FAIL: FR3: %d/%d single-error mismatches, e.g. codeword=%d"
            % (len(fr3_mismatches), len(err_rows), fr3_mismatches[0])
        )

    # FR4: compiled/elaborated cleanly (already confirmed above) AND no clocked always block
    if has_clocked_always:
        overall_pass = False
        print(
            "[TEST] FAIL: FR4: submission contains a clocked always block "
            "(always @(posedge/negedge ...)), violating the purely-combinational interface"
        )
    else:
        print("[TEST] PASS: FR4")

    # SR1: parity/data-bit confusion detection on error-free subset
    sr1_mismatches = []
    for v in clean_rows:
        if v["sub_data"] != v["ref_data"]:
            sr1_mismatches.append(v["codeword"])

    if len(clean_rows) == 0:
        overall_pass = False
        print("[TEST] FAIL: SR1: no error-free reference vectors found to check data extraction")
    elif not sr1_mismatches:
        print("[TEST] PASS: SR1")
    else:
        overall_pass = False
        print(
            "[TEST] FAIL: SR1: %d/%d clean-codeword data mismatches, e.g. codeword=%d"
            % (len(sr1_mismatches), len(clean_rows), sr1_mismatches[0])
        )

    # SR2: syndrome-to-bit-position mapping detection on single-error subset
    sr2_mismatches = []
    for v in err_rows:
        if v["sub_corrected"] != v["ref_corrected"]:
            sr2_mismatches.append(v["codeword"])

    if len(err_rows) == 0:
        overall_pass = False
        print("[TEST] FAIL: SR2: no single-error reference vectors found to check syndrome mapping")
    elif not sr2_mismatches:
        print("[TEST] PASS: SR2")
    else:
        overall_pass = False
        print(
            "[TEST] FAIL: SR2: %d/%d single-error corrected_codeword mismatches, e.g. codeword=%d"
            % (len(sr2_mismatches), len(err_rows), sr2_mismatches[0])
        )

    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()