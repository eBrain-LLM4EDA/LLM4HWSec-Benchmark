#!/usr/bin/env python3
"""
evaluate.py -- main entry point for grading submission/recovered_rtl.v
against the pinned pwm_deadtime_gen interface, via cycle-accurate
behavioral simulation against an independently authored reference
design (evaluation/reference_pwm.v) driven by evaluation/tb_top.v.

All grading is behavioral: the submission's source text is never
inspected. Only observed simulation waveforms (via PROBE lines printed
by the testbench) determine PASS/FAIL for each requirement.
"""

import os
import re
import subprocess
import sys
import tempfile

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2"]

INPUT_FILES = [
    "inputs/gate_netlist.v",
    "inputs/obfuscated_rtl.v",
    "inputs/design_brief.md",
]

SUBMISSION_FILE = "submission/recovered_rtl.v"
REFERENCE_FILE = "evaluation/reference_pwm.v"
TESTBENCH_FILE = "evaluation/tb_top.v"

PROBE_RE = re.compile(
    r'^\s*PROBE\s+(\S+)\s+(PASS|FAIL)\s*(.*)$'
)


def fail_all(reason):
    """Emit a FAIL for every requirement id with the given reason and exit 1."""
    for rid in REQUIREMENT_IDS:
        print("[TEST] FAIL: %s: %s" % (rid, reason))
    sys.exit(1)


def main():
    # ------------------------------------------------------------
    # Step 1: verify input artifacts exist (context only, no static
    # grading is performed on their contents).
    # ------------------------------------------------------------
    for f in INPUT_FILES:
        if not os.path.isfile(f):
            print("[TEST] FAIL: SETUP: %s not found" % f)
            sys.exit(1)

    # ------------------------------------------------------------
    # Step 2: verify submission exists.
    # ------------------------------------------------------------
    if not os.path.isfile(SUBMISSION_FILE):
        print("[TEST] FAIL: SETUP: %s not found" % SUBMISSION_FILE)
        sys.exit(1)

    # ------------------------------------------------------------
    # Step 3: verify harness files shipped with this evaluator exist.
    # ------------------------------------------------------------
    for f in [REFERENCE_FILE, TESTBENCH_FILE]:
        if not os.path.isfile(f):
            print("[TEST] FAIL: SETUP: %s not found" % f)
            sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        sim_path = os.path.join(tmpdir, "sim.vvp")

        # ------------------------------------------------------------
        # Step 4: compile submission + reference + testbench with iverilog.
        # ------------------------------------------------------------
        compile_cmd = [
            "iverilog",
            "-g2012",
            "-o", sim_path,
            SUBMISSION_FILE,
            REFERENCE_FILE,
            TESTBENCH_FILE,
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
            return
        except FileNotFoundError as e:
            fail_all("compile failed: could not invoke iverilog: %s" % e)
            return

        if compile_proc.returncode != 0:
            stderr_text = compile_proc.stderr.decode("utf-8", errors="replace")
            stdout_text = compile_proc.stdout.decode("utf-8", errors="replace")
            combined = (stderr_text + "\n" + stdout_text).strip()
            # keep it concise but informative
            lines = [l for l in combined.splitlines() if l.strip()]
            summary = " | ".join(lines[:8]) if lines else "iverilog exited nonzero with no output"
            if len(summary) > 500:
                summary = summary[:500] + "...(truncated)"
            fail_all("compile failed: %s" % summary)
            return

        # ------------------------------------------------------------
        # Step 5: run the simulation with vvp.
        # ------------------------------------------------------------
        run_cmd = ["vvp", sim_path]

        try:
            run_proc = subprocess.run(
                run_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            for rid in REQUIREMENT_IDS:
                print("[TEST] FAIL: %s: run crashed/timed out: vvp exceeded 30s" % rid)
            sys.exit(1)
        except FileNotFoundError as e:
            for rid in REQUIREMENT_IDS:
                print("[TEST] FAIL: %s: run crashed/timed out: could not invoke vvp: %s" % (rid, e))
            sys.exit(1)

        stdout_text = run_proc.stdout.decode("utf-8", errors="replace")
        stderr_text = run_proc.stderr.decode("utf-8", errors="replace")

        # ------------------------------------------------------------
        # Step 6: parse PROBE lines and aggregate per requirement id.
        # ------------------------------------------------------------
        probes_by_id = {rid: [] for rid in REQUIREMENT_IDS}

        for line in stdout_text.splitlines():
            m = PROBE_RE.match(line)
            if not m:
                continue
            probe_id = m.group(1)
            probe_status = m.group(2)
            probe_detail = m.group(3).strip()
            if probe_id in probes_by_id:
                probes_by_id[probe_id].append((probe_status, probe_detail))

        # If the process crashed/exited nonzero and produced no probes at
        # all, treat as run crash (not SETUP) for every requirement.
        if run_proc.returncode != 0 and all(
            len(probes_by_id[rid]) == 0 for rid in REQUIREMENT_IDS
        ):
            crash_summary = (stderr_text + " " + stdout_text).strip()
            if len(crash_summary) > 300:
                crash_summary = crash_summary[:300] + "...(truncated)"
            for rid in REQUIREMENT_IDS:
                print(
                    "[TEST] FAIL: %s: run crashed/timed out: vvp exited %d: %s"
                    % (rid, run_proc.returncode, crash_summary or "no output")
                )
            sys.exit(1)

        overall_pass = True

        for rid in REQUIREMENT_IDS:
            probes = probes_by_id[rid]
            if len(probes) == 0:
                print(
                    "[TEST] FAIL: %s: run crashed/timed out: no PROBE lines observed for %s"
                    % (rid, rid)
                )
                overall_pass = False
                continue

            failing = [(status, detail) for (status, detail) in probes if status != "PASS"]
            if len(failing) == 0:
                print("[TEST] PASS: %s" % rid)
            else:
                reason = failing[0][1] if failing[0][1] else "observed behavioral mismatch"
                print("[TEST] FAIL: %s: %s" % (rid, reason))
                overall_pass = False

        sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()