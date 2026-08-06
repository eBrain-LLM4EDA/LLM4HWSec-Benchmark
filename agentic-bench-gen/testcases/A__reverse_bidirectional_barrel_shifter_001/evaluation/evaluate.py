#!/usr/bin/env python3
"""
evaluation/evaluate.py

Grades submission/recovered_rtl.v against inputs/net_shifter_flat.v by
exhaustive behavioral simulation (iverilog + vvp), using
evaluation/tb_top.v as the comparison testbench.

Requirement ids checked: FR1, FR2, FR3, FR4, SR1, SR2

SR2 is graded from a DEDICATED, independently-computed counter
(SR2_MISMATCHES/SR2_TOTAL) emitted by tb_top.v's own standalone pass
over the mode=01/direction=0/data_in[7]=1 vector subset, so its
detection is not contingent on the global exhaustive tally or on any
other requirement's outcome.
"""

import os
import re
import subprocess
import sys
import tempfile

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2"]

INPUT_NETLIST = "inputs/net_shifter_flat.v"
INPUT_BRIEF = "inputs/design_brief.md"
SUBMISSION = "submission/recovered_rtl.v"
TESTBENCH = "evaluation/tb_top.v"


def fail_all(reason):
    for rid in REQUIREMENT_IDS:
        print("[TEST] FAIL: %s: %s" % (rid, reason))


def fail_all_setup(missing_path):
    for rid in REQUIREMENT_IDS:
        print("[TEST] FAIL: SETUP: %s not found" % missing_path)


def main():
    # --- Step 1: verify reference input artifacts exist ---
    if not os.path.isfile(INPUT_NETLIST):
        fail_all_setup(INPUT_NETLIST)
        return 1
    if not os.path.isfile(INPUT_BRIEF):
        fail_all_setup(INPUT_BRIEF)
        return 1

    # --- Step 2: verify submission exists ---
    if not os.path.isfile(SUBMISSION):
        fail_all_setup(SUBMISSION)
        return 1

    # sanity: our own harness testbench must exist too (infra, not participant issue)
    if not os.path.isfile(TESTBENCH):
        fail_all_setup(TESTBENCH)
        return 1

    tmpdir = tempfile.mkdtemp(prefix="barrel_shifter_eval_")
    vvp_path = os.path.join(tmpdir, "sim.vvp")

    # --- Step 3: compile with iverilog ---
    compile_cmd = [
        "iverilog",
        "-g2012",
        "-o", vvp_path,
        INPUT_NETLIST,
        SUBMISSION,
        TESTBENCH,
    ]

    try:
        compile_proc = subprocess.run(
            compile_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        fail_all("compile failed: iverilog timed out after 30s")
        return 1
    except FileNotFoundError:
        fail_all("compile failed: iverilog executable not found")
        return 1

    if compile_proc.returncode != 0:
        stderr_text = compile_proc.stderr.decode("utf-8", errors="replace")
        stdout_text = compile_proc.stdout.decode("utf-8", errors="replace")
        combined = (stderr_text + "\n" + stdout_text).strip()
        summary_lines = [l for l in combined.splitlines() if l.strip()]
        summary = " | ".join(summary_lines[:8]) if summary_lines else "unknown iverilog error"
        if len(summary) > 500:
            summary = summary[:500] + "...(truncated)"
        fail_all("compile failed: %s" % summary)
        return 1

    # --- Step 4: run vvp ---
    run_cmd = ["vvp", vvp_path]
    try:
        run_proc = subprocess.run(
            run_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        fail_all("run crashed/timed out: vvp timed out after 60s")
        return 1
    except FileNotFoundError:
        fail_all("run crashed/timed out: vvp executable not found")
        return 1

    stdout_text = run_proc.stdout.decode("utf-8", errors="replace")
    stderr_text = run_proc.stderr.decode("utf-8", errors="replace")

    if run_proc.returncode != 0:
        combined = (stdout_text + "\n" + stderr_text).strip()
        summary_lines = [l for l in combined.splitlines() if l.strip()]
        summary = " | ".join(summary_lines[-8:]) if summary_lines else "vvp exited nonzero with no output"
        if len(summary) > 500:
            summary = summary[:500] + "...(truncated)"
        fail_all("run crashed/timed out: %s" % summary)
        return 1

    # --- Step 5: parse summary lines (three independent regexes) ---
    total_re = re.compile(
        r'TOTAL_VECTORS=(\d+)\s+MISMATCHES=(\d+)\s+FIRST_MISMATCH=(NONE|[\d,]+)'
    )
    mode11_re = re.compile(
        r'MODE11_MISMATCHES=(\d+)\s+MODE11_TOTAL=(\d+)'
    )
    sr2_re = re.compile(
        r'SR2_MISMATCHES=(\d+)\s+SR2_TOTAL=(\d+)'
    )

    total_match = total_re.search(stdout_text)
    mode11_match = mode11_re.search(stdout_text)
    sr2_match = sr2_re.search(stdout_text)

    if total_match is None or mode11_match is None or sr2_match is None:
        tail = "\n".join(stdout_text.strip().splitlines()[-15:])
        fail_all(
            "run crashed/timed out: could not parse simulation summary output; "
            "tail of stdout: %s" % tail
        )
        return 1

    total_vectors = int(total_match.group(1))
    mismatches = int(total_match.group(2))
    first_mismatch = total_match.group(3)

    mode11_mismatches = int(mode11_match.group(1))
    mode11_total = int(mode11_match.group(2))

    sr2_mismatches = int(sr2_match.group(1))
    sr2_total = int(sr2_match.group(2))

    # --- Step 6: static fail-on-presence scan for unconstrained 'x' under mode=11 ---
    # This can only ever push SR1 from PASS -> FAIL as a belt-and-suspenders
    # signal; it never causes a PASS on its own (behavioral MODE11_MISMATCHES
    # is still the primary and required determinant).
    static_x_flag = False
    try:
        with open(SUBMISSION, "r", encoding="utf-8", errors="replace") as f:
            src = f.read()
    except OSError:
        src = ""

    if src:
        # Vulnerability pattern this guards against: a case item for mode==2'b11
        # (or equivalent literal forms) followed within a few lines by an
        # assignment of an 'x'-containing literal to data_out, e.g.:
        #   2'b11: data_out = 8'bxxxxxxxx;
        # or
        #   2'b11: data_out = 8'hxx;
        case_item_pattern = re.compile(
            r"2\s*'\s*b\s*11\s*:|2\s*'\s*b11\s*:|mode\s*==\s*2\s*'\s*b\s*11"
        )
        x_literal_pattern = re.compile(
            r"data_out\s*=\s*\d*\s*'\s*[bhBH][0-9a-fA-F_xXzZ]*[xX][0-9a-fA-F_xXzZ]*\s*;"
        )

        for m in case_item_pattern.finditer(src):
            start = m.end()
            window = src[start:start + 200]
            if x_literal_pattern.search(window):
                static_x_flag = True
                break

    # --- Step 7: derive verdicts ---
    results = {}

    global_pass = (mismatches == 0)
    if global_pass:
        for rid in ("FR1", "FR2", "FR3", "FR4"):
            results[rid] = (True, "")
    else:
        reason = (
            "exhaustive comparison found %d/%d mismatching vector(s); "
            "first mismatch (data_in,amount,direction,mode)=%s"
            % (mismatches, total_vectors, first_mismatch)
        )
        for rid in ("FR1", "FR2", "FR3", "FR4"):
            results[rid] = (False, reason)

    sr1_pass = (mode11_mismatches == 0) and (not static_x_flag)
    if sr1_pass:
        results["SR1"] = (True, "")
    else:
        reasons = []
        if mode11_mismatches != 0:
            reasons.append(
                "%d/%d mode=11 vectors diverge from reference netlist's resolved behavior"
                % (mode11_mismatches, mode11_total)
            )
        if static_x_flag:
            reasons.append(
                "submission source assigns an unconstrained 'x' literal to data_out "
                "under a mode==2'b11 case branch"
            )
        results["SR1"] = (False, "; ".join(reasons))

    # SR2 is graded EXCLUSIVELY from the dedicated, independently-computed
    # SR2_MISMATCHES/SR2_TOTAL counter emitted by tb_top.v's own standalone
    # Pass 3 sweep over the mode=01/direction=0/data_in[7]=1 subset. This
    # value is not derived from, gated by, or contingent upon the global
    # MISMATCHES tally (Pass 1) or any other requirement's result, so a
    # mutant that corrupts only this left-shift path is detected here
    # directly regardless of whether FR1-FR4/SR1 also fail or pass.
    sr2_pass = (sr2_mismatches == 0) and (sr2_total > 0)
    if sr2_pass:
        results["SR2"] = (True, "")
    else:
        if sr2_total == 0:
            results["SR2"] = (
                False,
                "SR2 subset counter reported SR2_TOTAL=0; expected a nonzero "
                "number of mode=01,direction=0,data_in[7]=1 vectors to have "
                "been probed by the dedicated SR2 sweep"
            )
        else:
            results["SR2"] = (
                False,
                "%d/%d mode=01,direction=0(left),data_in[7]=1 vectors diverge from "
                "reference (likely sign-extension instead of zero-fill on left shift), "
                "per dedicated independent SR2 subset counter"
                % (sr2_mismatches, sr2_total),
            )

    # --- Emit markers ---
    all_pass = True
    for rid in REQUIREMENT_IDS:
        passed, reason = results[rid]
        if passed:
            print("[TEST] PASS: %s" % rid)
        else:
            all_pass = False
            print("[TEST] FAIL: %s: %s" % (rid, reason))

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())