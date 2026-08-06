#!/usr/bin/env python3
"""
Main grader entry point for hw_reveng_fsm_recovery_001.

Behavioral grading: compiles submission/recovered_rtl.v together with the
reference gate-level netlist and a self-checking testbench, using
iverilog/vvp, and compares cycle-by-cycle output. One static fail-on-presence
scan is used for SR1 (gate-primitive reuse / verbatim netlist copy).
"""

import os
import re
import sys
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

NETLIST = os.path.join(ROOT, "inputs", "flattened_netlist.v")
PRIMS = os.path.join(ROOT, "inputs", "primitives.v")
STIM = os.path.join(ROOT, "inputs", "stimulus.txt")
BRIEF = os.path.join(ROOT, "inputs", "design_brief.md")
SUB = os.path.join(ROOT, "submission", "recovered_rtl.v")
TB = os.path.join(HERE, "tb_compare.v")

sys.path.insert(0, HERE)
from private import checks_static
from private import vectors

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3"]

results = {}


def emit_pass(rid):
    if rid not in results:
        results[rid] = True
        print("[TEST] PASS: %s" % rid)


def emit_fail(rid, reason):
    if rid not in results:
        results[rid] = False
        print("[TEST] FAIL: %s: %s" % (rid, reason))


def check_setup():
    required = [NETLIST, PRIMS, STIM, BRIEF, SUB]
    ok = True
    for p in required:
        if not os.path.isfile(p):
            print("[TEST] FAIL: SETUP: %s not found" % p)
            ok = False
    return ok


def run_vvp(sim_path, vecfile, timeout=20):
    try:
        proc = subprocess.run(
            ["vvp", sim_path, "+VECFILE=%s" % vecfile],
            capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return None, None, "run timed out"
    except Exception as e:
        return None, None, "run crashed: %s" % e

    stdout = proc.stdout or ""
    m = re.search(r"RESULT\s+total=(\d+)\s+mismatches=(\d+)", stdout)
    if not m:
        return None, None, "no RESULT line in output"
    total = int(m.group(1))
    mismatches = int(m.group(2))
    return total, mismatches, None


def main():
    if not check_setup():
        sys.exit(1)

    with open(SUB, "r", encoding="utf-8", errors="replace") as f:
        sub_text = f.read()
    with open(NETLIST, "r", encoding="utf-8", errors="replace") as f:
        netlist_text = f.read()

    # ---------- Step 1: static checks (no compile needed) ----------
    ports = None
    try:
        ports = checks_static.extract_ports(sub_text)
    except checks_static.ParseError as e:
        emit_fail("FR1", str(e))
        emit_fail("SR2", str(e))
    else:
        expected = {"clk": "input", "rst": "input", "in": "input", "out": "output"}
        fr1_problem = None
        for name, direction in expected.items():
            if name not in ports:
                fr1_problem = "missing port %s" % name
                break
            got_dir, is_1bit = ports[name]
            if got_dir != direction:
                fr1_problem = "port %s has direction %s, expected %s" % (name, got_dir, direction)
                break
            if not is_1bit:
                fr1_problem = "port %s is not 1-bit wide" % name
                break
        if fr1_problem:
            emit_fail("FR1", fr1_problem)
        else:
            emit_pass("FR1")

        extra = set(ports.keys()) - set(expected.keys())
        if extra:
            emit_fail("SR2", "unexpected extra port(s): %s" % ", ".join(sorted(extra)))
        elif len(ports.keys()) != 4:
            emit_fail("SR2", "port set size != 4: %s" % ", ".join(sorted(ports.keys())))
        else:
            emit_pass("SR2")

    violations = checks_static.scan_banned(sub_text, netlist_text)
    if violations:
        emit_fail("SR1", "; ".join(violations))
    else:
        emit_pass("SR1")

    # ---------- Step 2: compile ----------
    tmpdir = tempfile.mkdtemp(prefix="hw_reveng_")
    sim_path = os.path.join(tmpdir, "sim.vvp")

    compile_cmd = [
        "iverilog", "-g2012", "-o", sim_path,
        SUB, PRIMS, NETLIST, TB
    ]
    compile_ok = False
    first_err = ""
    try:
        proc = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            stderr_lines = (proc.stderr or "").strip().splitlines()
            first_err = stderr_lines[0] if stderr_lines else "iverilog failed with no stderr output"
        else:
            compile_ok = True
    except subprocess.TimeoutExpired:
        first_err = "iverilog compile timed out"
    except FileNotFoundError:
        first_err = "iverilog not found on PATH"
    except Exception as e:
        first_err = "compile invocation error: %s" % e

    if not compile_ok:
        reason = "compile failed: %s" % first_err
        emit_fail("FR3", reason)
        emit_fail("FR2", reason)
        emit_fail("FR4", reason)
        emit_fail("SR3", reason)
        finish(tmpdir)
        return
    else:
        emit_pass("FR3")

    # ---------- Step 3: FR2 - shipped stimulus ----------
    total, mismatches, err = run_vvp(sim_path, STIM)
    if err:
        emit_fail("FR2", "run crashed/timed out: %s" % err)
    elif total is None or total == 0:
        emit_fail("FR2", "no cycles compared (total=%s)" % total)
    elif mismatches != 0:
        emit_fail("FR2", "output mismatch on %d/%d cycles for shipped stimulus" % (mismatches, total))
    else:
        emit_pass("FR2")

    # ---------- Step 4: FR4 - hidden pseudo-random sequences ----------
    fr4_failure = None
    try:
        rand_seqs = vectors.random_sequences()
    except Exception as e:
        fr4_failure = "vector generation error: %s" % e
        rand_seqs = []

    if fr4_failure is None:
        if len(rand_seqs) < 5:
            fr4_failure = "expected >=5 random sequences, got %d" % len(rand_seqs)

    if fr4_failure is None:
        for idx, seq in enumerate(rand_seqs):
            vecfile = os.path.join(tmpdir, "rand_%d.txt" % idx)
            vectors.write_vectors(vecfile, seq)
            total, mismatches, err = run_vvp(sim_path, vecfile)
            if err:
                fr4_failure = "sequence #%d run crashed/timed out: %s" % (idx, err)
                break
            if total is None or total == 0:
                fr4_failure = "sequence #%d: no cycles compared" % idx
                break
            if mismatches != 0:
                fr4_failure = "sequence #%d: mismatch on %d/%d cycles" % (idx, mismatches, total)
                break

    if fr4_failure:
        emit_fail("FR4", fr4_failure)
    else:
        emit_pass("FR4")

    # ---------- Step 5: SR3 - adversarial sequences ----------
    sr3_failure = None
    try:
        adv_seqs = vectors.adversarial_sequences()
    except Exception as e:
        sr3_failure = "vector generation error: %s" % e
        adv_seqs = []

    if sr3_failure is None:
        if len(adv_seqs) < 2:
            sr3_failure = "expected >=2 adversarial sequences, got %d" % len(adv_seqs)

    if sr3_failure is None:
        for idx, seq in enumerate(adv_seqs):
            vecfile = os.path.join(tmpdir, "adv_%d.txt" % idx)
            vectors.write_vectors(vecfile, seq)
            total, mismatches, err = run_vvp(sim_path, vecfile)
            if err:
                sr3_failure = "adversarial case #%d run crashed/timed out: %s" % (idx, err)
                break
            if total is None or total == 0:
                sr3_failure = "adversarial case #%d: no cycles compared" % idx
                break
            if mismatches != 0:
                sr3_failure = "adversarial case #%d: mismatch on %d/%d cycles" % (idx, mismatches, total)
                break

    if sr3_failure:
        emit_fail("SR3", sr3_failure)
    else:
        emit_pass("SR3")

    finish(tmpdir)


def finish(tmpdir):
    # Ensure every requirement produced a verdict, even if some earlier
    # unexpected exception path skipped it.
    for rid in REQUIREMENT_IDS:
        if rid not in results:
            emit_fail(rid, "requirement not evaluated (internal error)")

    try:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass

    if all(results.get(rid, False) for rid in REQUIREMENT_IDS):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        for rid in REQUIREMENT_IDS:
            if rid not in results:
                emit_fail(rid, "unhandled evaluator error: %s" % e)
        sys.exit(1)