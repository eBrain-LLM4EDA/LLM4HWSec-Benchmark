#!/usr/bin/env python3
"""
evaluate.py -- Grading entry point for hw_reveng_mux_alu_datapath_001

Behaviorally grades submission/recovered_rtl.v by:
  1. Checking the file exists.
  2. Running a fail-on-presence static scan for banned constructs
     (clocked always blocks / latch-inferring incomplete if-without-else).
  3. Compiling submission/recovered_rtl.v + evaluation/tb_compare.v with
     iverilog, running with vvp, and parsing deterministic VEC lines to
     score FR2, FR3, FR4, SR1, SR2.

NOTE: this evaluator intentionally does NOT compile or simulate
inputs/gate_netlist.v for functional grading. That reference file's
ripple-carry chain contains a self-referencing multiply-driven net
pattern (e.g. "xor (s0, a[0], binv0); xor (s0, s0, sel[0]);") that
produces X on its y output for essentially all sel=00/01 vectors under
real iverilog simulation, making direct signal comparison against it
unusable even for a genuinely correct recovered module. Instead,
evaluation/tb_compare.v computes the expected result behaviorally
(mirroring the literal public FR2-FR4 definitions: 8-bit a+b, a-b,
a&b, a|b) and evaluate.py cross-checks directed/boundary vectors
independently in Python.

Python stdlib only.
"""

import os
import re
import subprocess
import sys
import tempfile

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2"]

SUBMISSION_PATH = "submission/recovered_rtl.v"
TB_COMPARE_PATH = "evaluation/tb_compare.v"

VEC_RE = re.compile(
    r"VEC\s+sel=(\d+)\s+a=(\d+)\s+b=(\d+)\s+rec=(\d+)\s+exp=(\d+)\s+match=([01])"
)


def emit_pass(req_id):
    print("[TEST] PASS: {}".format(req_id))


def emit_fail(req_id, reason):
    print("[TEST] FAIL: {}: {}".format(req_id, reason))


def fail_all_setup(reason):
    for rid in REQUIREMENT_IDS:
        emit_fail(rid, reason)
    sys.exit(1)


def fail_all_compile(first_error_line):
    for rid in REQUIREMENT_IDS:
        emit_fail(rid, "compile failed: {}".format(first_error_line))
    sys.exit(1)


def main():
    results = {}

    # ------------------------------------------------------------------
    # Setup checks: required files must exist.
    # ------------------------------------------------------------------
    if not os.path.isfile(SUBMISSION_PATH):
        fail_all_setup("{} not found".format(SUBMISSION_PATH))

    if not os.path.isfile(TB_COMPARE_PATH):
        fail_all_setup("{} not found".format(TB_COMPARE_PATH))

    with open(SUBMISSION_PATH, "r") as f:
        submission_src = f.read()

    # ------------------------------------------------------------------
    # FR1 (part 1): static fail-on-presence scan for banned constructs.
    # These patterns indicate sequential logic or latch inference, which
    # violates the "purely combinational" public constraint. A correct
    # combinational submission simply will not contain these constructs.
    # ------------------------------------------------------------------
    fr1_static_fail_reason = None

    # Banned: clocked always blocks (posedge/negedge clock triggers).
    clocked_pattern = re.compile(
        r"always\s*@\s*\(\s*(?:posedge|negedge)\b", re.IGNORECASE
    )
    if clocked_pattern.search(submission_src):
        fr1_static_fail_reason = (
            "clocked always block (posedge/negedge) found -- design must be "
            "purely combinational"
        )

    # Banned: incomplete if-without-else inside an always block that only
    # conditionally assigns a reg (classic latch-inference pattern), e.g.
    #   always @(*) begin
    #       if (cond) y = val;
    #   end
    # with no matching else anywhere in that always block. We approximate
    # this by scanning each `always` block body for an `if (` that has no
    # corresponding `else` before the block's closing `end`.
    if fr1_static_fail_reason is None:
        for m in re.finditer(r"always\s*@\s*\(([^)]*)\)\s*(begin)?", submission_src):
            start = m.end()
            if m.group(2) is None:
                continue
            depth = 1
            idx = start
            body_end = len(submission_src)
            while idx < len(submission_src) and depth > 0:
                nb = re.search(r"\bbegin\b|\bend\b", submission_src[idx:])
                if not nb:
                    break
                tok = nb.group(0)
                idx = idx + nb.end()
                if tok == "begin":
                    depth += 1
                else:
                    depth -= 1
                    if depth == 0:
                        body_end = idx - len("end")
            body = submission_src[start:body_end]
            if_matches = list(re.finditer(r"\bif\s*\(", body))
            else_matches = list(re.finditer(r"\belse\b", body))
            if if_matches and len(else_matches) < len(if_matches):
                fr1_static_fail_reason = (
                    "if-without-matching-else found inside an always block "
                    "(latch-inference pattern) -- design must be purely "
                    "combinational with fully specified outputs"
                )
                break

    # ------------------------------------------------------------------
    # Compile + simulate. Only the submission and the self-contained
    # comparison testbench are compiled -- inputs/gate_netlist.v is
    # deliberately NOT part of this compile/simulate step (see module
    # docstring for rationale).
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        sim_path = os.path.join(tmpdir, "sim.vvp")
        compile_cmd = [
            "iverilog",
            "-g2012",
            "-o",
            sim_path,
            SUBMISSION_PATH,
            TB_COMPARE_PATH,
        ]

        try:
            compile_proc = subprocess.run(
                compile_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            fail_all_compile("iverilog compile timed out")
            return
        except FileNotFoundError:
            fail_all_setup("iverilog toolchain not found")
            return

        if compile_proc.returncode != 0:
            stderr_text = compile_proc.stderr.decode(errors="replace")
            first_line = next(
                (ln for ln in stderr_text.splitlines() if ln.strip()),
                "unknown compile error",
            )
            fail_all_compile(first_line)
            return

        try:
            run_proc = subprocess.run(
                ["vvp", sim_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            fail_all_compile("simulation (vvp) timed out")
            return
        except FileNotFoundError:
            fail_all_setup("vvp toolchain not found")
            return

        stdout_text = run_proc.stdout.decode(errors="replace")

        vectors = []
        for line in stdout_text.splitlines():
            vm = VEC_RE.search(line)
            if vm:
                sel = int(vm.group(1))
                a = int(vm.group(2))
                b = int(vm.group(3))
                rec = int(vm.group(4))
                exp = int(vm.group(5))
                match = int(vm.group(6))
                vectors.append(
                    {"sel": sel, "a": a, "b": b, "rec": rec, "exp": exp, "match": match}
                )

        if not vectors:
            # Simulation ran but produced no parseable VEC lines: treat as
            # a compile/elaboration-level failure since we cannot evaluate
            # anything about the submission's behavior.
            stderr_text = run_proc.stderr.decode(errors="replace")
            first_line = next(
                (ln for ln in stderr_text.splitlines() if ln.strip()),
                "no VEC output produced by simulation",
            )
            fail_all_compile(first_line)
            return

    # ------------------------------------------------------------------
    # FR1: compile/elaborate succeeded and produced output; combine with
    # the static scan result.
    # ------------------------------------------------------------------
    if fr1_static_fail_reason is not None:
        results["FR1"] = (False, fr1_static_fail_reason)
    else:
        results["FR1"] = (True, "")

    # ------------------------------------------------------------------
    # FR2: sel=00 (add) -- all vectors must match.
    # ------------------------------------------------------------------
    sel00 = [v for v in vectors if v["sel"] == 0]
    if not sel00:
        results["FR2"] = (False, "no sel=00 vectors observed in simulation output")
    else:
        bad = [v for v in sel00 if v["match"] != 1]
        if bad:
            v = bad[0]
            results["FR2"] = (
                False,
                "sel=00 mismatch at a={} b={}: exp={} rec={}".format(
                    v["a"], v["b"], v["exp"], v["rec"]
                ),
            )
        else:
            results["FR2"] = (True, "")

    # ------------------------------------------------------------------
    # FR3: sel=01 (sub) -- all vectors must match.
    # ------------------------------------------------------------------
    sel01 = [v for v in vectors if v["sel"] == 1]
    if not sel01:
        results["FR3"] = (False, "no sel=01 vectors observed in simulation output")
    else:
        bad = [v for v in sel01 if v["match"] != 1]
        if bad:
            v = bad[0]
            results["FR3"] = (
                False,
                "sel=01 mismatch at a={} b={}: exp={} rec={}".format(
                    v["a"], v["b"], v["exp"], v["rec"]
                ),
            )
        else:
            results["FR3"] = (True, "")

    # ------------------------------------------------------------------
    # FR4: sel=10 (and) and sel=11 (or) -- all vectors must match.
    # ------------------------------------------------------------------
    sel10 = [v for v in vectors if v["sel"] == 2]
    sel11 = [v for v in vectors if v["sel"] == 3]
    if not sel10 or not sel11:
        results["FR4"] = (
            False,
            "missing sel=10 and/or sel=11 vectors in simulation output",
        )
    else:
        bad = [v for v in (sel10 + sel11) if v["match"] != 1]
        if bad:
            v = bad[0]
            results["FR4"] = (
                False,
                "sel={:02b} mismatch at a={} b={}: exp={} rec={}".format(
                    v["sel"], v["a"], v["b"], v["exp"], v["rec"]
                ),
            )
        else:
            results["FR4"] = (True, "")

    # ------------------------------------------------------------------
    # SR1: directed non-commutative pairs (a=5,b=3) and (a=3,b=5) at
    # sel=00 (add) and sel=01 (sub). Recompute expected values in Python
    # and require exact equality against the recovered module's output,
    # independent of any single reference oracle, to catch add/sub swap
    # or wrong operand order even if aggregate FR checks happened to pass.
    # ------------------------------------------------------------------
    def find_vector(sel, a, b):
        for v in vectors:
            if v["sel"] == sel and v["a"] == a and v["b"] == b:
                return v
        return None

    sr1_cases = [
        (0, 5, 3, (5 + 3) % 256),
        (0, 3, 5, (3 + 5) % 256),
        (1, 5, 3, (5 - 3) % 256),
        (1, 3, 5, (3 - 5) % 256),
    ]

    sr1_fail_reason = None
    for sel, a, b, expected in sr1_cases:
        v = find_vector(sel, a, b)
        if v is None:
            sr1_fail_reason = (
                "missing directed vector sel={:02b} a={} b={} in simulation output".format(
                    sel, a, b
                )
            )
            break
        if v["rec"] != expected:
            sr1_fail_reason = (
                "sel={:02b} a={} b={}: expected {} but recovered module produced {} "
                "(possible add/sub swap or wrong operand order)".format(
                    sel, a, b, expected, v["rec"]
                )
            )
            break

    if sr1_fail_reason is not None:
        results["SR1"] = (False, sr1_fail_reason)
    else:
        results["SR1"] = (True, "")

    # ------------------------------------------------------------------
    # SR2: boundary overflow/underflow wraparound cases.
    #   (a=255, b=1, sel=00) -> expect 0   (add overflow wraps mod 256)
    #   (a=0,   b=1, sel=01) -> expect 255 (subtract underflow wraps mod 256)
    # ------------------------------------------------------------------
    sr2_cases = [
        (0, 255, 1, (255 + 1) % 256),
        (1, 0, 1, (0 - 1) % 256),
    ]

    sr2_fail_reason = None
    for sel, a, b, expected in sr2_cases:
        v = find_vector(sel, a, b)
        if v is None:
            sr2_fail_reason = (
                "missing boundary vector sel={:02b} a={} b={} in simulation output".format(
                    sel, a, b
                )
            )
            break
        if v["rec"] != expected:
            sr2_fail_reason = (
                "sel={:02b} a={} b={}: expected {} (mod-256 wraparound) but recovered "
                "module produced {} (possible width/carry-out leak error)".format(
                    sel, a, b, expected, v["rec"]
                )
            )
            break
        if v["rec"] > 255 or v["rec"] < 0:
            sr2_fail_reason = (
                "sel={:02b} a={} b={}: recovered value {} out of 8-bit range".format(
                    sel, a, b, v["rec"]
                )
            )
            break

    if sr2_fail_reason is not None:
        results["SR2"] = (False, sr2_fail_reason)
    else:
        results["SR2"] = (True, "")

    # ------------------------------------------------------------------
    # Emit final verdicts in fixed order.
    # ------------------------------------------------------------------
    all_pass = True
    for rid in REQUIREMENT_IDS:
        ok, reason = results.get(rid, (False, "requirement not evaluated"))
        if ok:
            emit_pass(rid)
        else:
            emit_fail(rid, reason)
            all_pass = False

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()