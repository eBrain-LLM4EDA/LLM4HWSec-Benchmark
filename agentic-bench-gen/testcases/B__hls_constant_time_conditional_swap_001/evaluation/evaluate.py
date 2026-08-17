#!/usr/bin/env python3
"""
evaluate.py - Grader for hls_constant_time_conditional_swap_001

Compiles inputs/ladder_swap.cpp together with evaluation/harness_main.cpp
into a SINGLE linked executable, runs the resulting binary in several
modes, and derives PASS/FAIL verdicts for FR1-FR4 and SR1-SR3 from
observed behavior (plus one fail-on-presence static scan for SR1).
"""

import os
import re
import subprocess
import sys
import tempfile

REQ_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3"]

INPUTS_DIR = "inputs"
EVAL_DIR = "evaluation"

LADDER_SRC = os.path.join(INPUTS_DIR, "ladder_swap.cpp")
DESIGN_BRIEF = os.path.join(INPUTS_DIR, "design_brief.md")
HARNESS_SRC = os.path.join(EVAL_DIR, "harness_main.cpp")

SIZES = [1, 2, 64, 4096]

results = {}


def emit_pass(req_id):
    results[req_id] = ("PASS", "")
    print("[TEST] PASS: %s" % req_id)


def emit_fail(req_id, reason):
    results[req_id] = ("FAIL", reason)
    print("[TEST] FAIL: %s: %s" % (req_id, reason))


def already_decided(req_id):
    return req_id in results


def fail_all_compile(reason):
    for req_id in REQ_IDS:
        if not already_decided(req_id):
            emit_fail(req_id, "compile failed: %s" % reason)


def run_proc(cmd, cwd=None, timeout=30):
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout.decode("utf-8", errors="replace"), proc.stderr.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return None, "", "TIMEOUT"
    except FileNotFoundError as e:
        return None, "", "FILE_NOT_FOUND: %s" % e


def main():
    # --- SETUP checks -------------------------------------------------
    if not os.path.isfile(LADDER_SRC):
        print("[TEST] FAIL: SETUP: %s not found" % LADDER_SRC)
        sys.exit(1)

    if not os.path.isfile(DESIGN_BRIEF):
        print("[TEST] FAIL: SETUP: %s not found" % DESIGN_BRIEF)
        sys.exit(1)

    if not os.path.isfile(HARNESS_SRC):
        print("[TEST] FAIL: SETUP: %s not found" % HARNESS_SRC)
        sys.exit(1)

    try:
        with open(LADDER_SRC, "r", encoding="utf-8", errors="replace") as f:
            source_text = f.read()
    except Exception as e:
        print("[TEST] FAIL: SETUP: could not read %s: %s" % (LADDER_SRC, e))
        sys.exit(1)

    tmpdir = tempfile.mkdtemp(prefix="ladder_swap_eval_")
    binary_path = os.path.join(tmpdir, "harness_bin")

    # Single g++ invocation compiling AND linking both translation units
    # together in one command, ensuring any correct submission of the
    # pinned signature links successfully (no separate object-file steps
    # with potentially mismatched declarations).
    compile_cmd = [
        "g++", "-std=c++17", "-Wall", "-Wextra", "-O0",
        "-o", binary_path,
        LADDER_SRC, HARNESS_SRC,
    ]

    rc, out, err = run_proc(compile_cmd, timeout=60)

    binary_ready = False

    if rc is None:
        # infra issue running the compiler itself (timeout or missing g++)
        reason = err if err else "compiler invocation failed"
        emit_fail("FR4", "compile failed: %s" % reason)
        fail_all_compile(reason)
    elif rc != 0:
        stderr_excerpt = err.strip()
        lines = stderr_excerpt.splitlines()
        excerpt = "\n".join(lines[-15:]) if len(lines) > 15 else stderr_excerpt
        emit_fail("FR4", "g++ exited %d: %s" % (rc, excerpt))
        fail_all_compile("g++ exited %d: %s" % (rc, excerpt))
    else:
        emit_pass("FR4")
        binary_ready = True

    # --- Functional probes (FR1, FR2, FR3) -----------------------------
    if binary_ready:
        try:
            run_functional_checks(binary_path)
        except Exception as e:
            for req_id in ("FR1", "FR2", "FR3"):
                if not already_decided(req_id):
                    emit_fail(req_id, "internal grader exception: %s" % e)

    # --- SR1: static fail-on-presence branch-on-secret scan -----------
    try:
        run_static_sr1(source_text)
    except Exception as e:
        if not already_decided("SR1"):
            emit_fail("SR1", "internal grader exception: %s" % e)

    # --- SR2: dynamic access-trace comparison --------------------------
    if binary_ready:
        try:
            run_sr2(binary_path)
        except Exception as e:
            if not already_decided("SR2"):
                emit_fail("SR2", "internal grader exception: %s" % e)

    # --- SR3: dynamic timing differential -------------------------------
    if binary_ready:
        try:
            run_sr3(binary_path)
        except Exception as e:
            if not already_decided("SR3"):
                emit_fail("SR3", "internal grader exception: %s" % e)

    # --- Ensure every requirement id has a marker -----------------------
    for req_id in REQ_IDS:
        if not already_decided(req_id):
            emit_fail(req_id, "requirement was never evaluated (internal grader gap)")

    # --- Final verdict ---------------------------------------------------
    any_fail = any(status == "FAIL" for status, _ in results.values())
    sys.exit(1 if any_fail else 0)


def run_functional_checks(binary_path):
    rc, out, err = run_proc([binary_path, "functional"], timeout=30)

    if rc is None:
        reason = "run crashed/timed out: %s" % (err if err else "unknown")
        for req_id in ("FR1", "FR2", "FR3"):
            emit_fail(req_id, reason)
        return

    # Parse PROBE lines: "PROBE <name> <PASS|FAIL>"
    probe_re = re.compile(r'^PROBE\s+(\S+)\s+(PASS|FAIL)\s*$', re.MULTILINE)
    probes = {}
    for m in probe_re.finditer(out):
        name = m.group(1)
        status = m.group(2)
        probes[name] = status

    if rc != 0:
        crash_note = " (harness exit code %d)" % rc
    else:
        crash_note = ""

    swap_probe_re = re.compile(r'^swap_ctrl1_n(\d+)$')
    noop_probe_re = re.compile(r'^noop_ctrl0_n(\d+)$')

    swap_results = {}  # n -> status
    noop_results = {}  # n -> status

    for name, status in probes.items():
        m = swap_probe_re.match(name)
        if m:
            swap_results[int(m.group(1))] = status
            continue
        m = noop_probe_re.match(name)
        if m:
            noop_results[int(m.group(1))] = status
            continue

    # FR1: ctrl_bit == 1 swap correctness across all sizes
    missing_swap = [n for n in SIZES if n not in swap_results]
    bad_swap = [n for n in SIZES if swap_results.get(n) == "FAIL"]
    if missing_swap:
        emit_fail("FR1", "missing swap probe results for n=%s%s" % (missing_swap, crash_note))
    elif bad_swap:
        emit_fail("FR1", "swap mismatch for n=%s%s" % (bad_swap, crash_note))
    else:
        emit_pass("FR1")

    # FR2: ctrl_bit == 0 no-op correctness across all sizes
    missing_noop = [n for n in SIZES if n not in noop_results]
    bad_noop = [n for n in SIZES if noop_results.get(n) == "FAIL"]
    if missing_noop:
        emit_fail("FR2", "missing no-op probe results for n=%s%s" % (missing_noop, crash_note))
    elif bad_noop:
        emit_fail("FR2", "unexpected modification for n=%s%s" % (bad_noop, crash_note))
    else:
        emit_pass("FR2")

    # FR3: all sizes present, ran without crash, and both probes correct
    # per size (buffer overrun/memory corruption would typically show up
    # either as a crash -> rc is None/nonzero, or as incorrect results).
    all_sizes_ok = True
    fr3_reasons = []
    for n in SIZES:
        s_swap = swap_results.get(n)
        s_noop = noop_results.get(n)
        if s_swap is None or s_noop is None:
            all_sizes_ok = False
            fr3_reasons.append("n=%d: missing probe data" % n)
        elif s_swap == "FAIL" or s_noop == "FAIL":
            all_sizes_ok = False
            fr3_reasons.append("n=%d: probe failure" % n)

    if rc != 0:
        all_sizes_ok = False
        fr3_reasons.append("harness exited with code %d" % rc)

    if all_sizes_ok:
        emit_pass("FR3")
    else:
        emit_fail("FR3", "; ".join(fr3_reasons) if fr3_reasons else "unknown failure")


def run_static_sr1(source_text):
    if already_decided("SR1"):
        return

    # Strip comments and string literals to avoid false positives/negatives
    # from comments that merely mention ctrl_bit in prose.
    no_block_comments = re.sub(r'/\*.*?\*/', ' ', source_text, flags=re.DOTALL)
    no_comments = re.sub(r'//[^\n]*', ' ', no_block_comments)

    # Vulnerability in baseline: "if (ctrl_bit & 1u)"
    # Match any conditional construct (if/else if/while/for-condition/
    # ternary) whose evaluated condition textually references ctrl_bit,
    # either directly or through a simple intermediate boolean/int local
    # that was itself assigned directly from an expression containing
    # ctrl_bit just prior to the branch.
    branch_on_ctrl_bit = re.compile(
        r'(?:if|while)\s*\([^)]*\bctrl_bit\b[^)]*\)'
        r'|for\s*\([^;]*;[^;]*\bctrl_bit\b[^;]*;[^)]*\)'
        r'|\?[^:]*\bctrl_bit\b'  # crude ternary catch when ctrl_bit appears near '?'
        r'|\bctrl_bit\b[^;{}\n]{0,40}\?'  # ternary: ctrl_bit ... ? ...
    )

    m = branch_on_ctrl_bit.search(no_comments)
    if m:
        snippet = m.group(0).strip().replace("\n", " ")
        if len(snippet) > 80:
            snippet = snippet[:80] + "..."
        emit_fail("SR1", "branch conditioned on ctrl_bit found: '%s'" % snippet)
        return

    # Also catch the intermediate-variable pattern: a local variable
    # assigned directly from ctrl_bit (e.g. "int bit = ctrl_bit;" or
    # "unsigned b = ctrl_bit & 1u;") and later used inside an
    # if/while/ternary condition. We look for the assignment first, then
    # check whether that variable name subsequently appears inside a
    # conditional construct.
    assign_re = re.compile(
        r'\b(?:bool|int|unsigned(?:\s+int)?|uint32_t|unsigned\s+int|auto)\s+(\w+)\s*=\s*[^;]*\bctrl_bit\b[^;]*;'
    )
    suspect_vars = set(assign_re.findall(no_comments))

    if suspect_vars:
        for var in suspect_vars:
            cond_use_re = re.compile(
                r'(?:if|while)\s*\([^)]*\b' + re.escape(var) + r'\b[^)]*\)'
                r'|for\s*\([^;]*;[^;]*\b' + re.escape(var) + r'\b[^;]*;[^)]*\)'
                r'|\b' + re.escape(var) + r'\b[^;{}\n]{0,40}\?'
            )
            m2 = cond_use_re.search(no_comments)
            if m2:
                snippet = m2.group(0).strip().replace("\n", " ")
                if len(snippet) > 80:
                    snippet = snippet[:80] + "..."
                emit_fail(
                    "SR1",
                    "branch conditioned on '%s' derived from ctrl_bit found: '%s'" % (var, snippet),
                )
                return

    emit_pass("SR1")


def run_sr2(binary_path):
    if already_decided("SR2"):
        return

    n = 128
    rc, out, err = run_proc([binary_path, "access_trace", str(n)], timeout=30)

    if rc is None:
        emit_fail("SR2", "run crashed/timed out: %s" % (err if err else "unknown"))
        return

    if rc != 0:
        emit_fail("SR2", "harness exited with code %d during access_trace: %s" % (rc, err.strip()[:200]))
        return

    line_re = re.compile(
        r'^ACCESS_TRACE\s+ctrl=(\d+)\s+n=(\d+)\s+indices_visited=(\d+)\s+fingerprint=([0-9a-fA-F]+)\s*$',
        re.MULTILINE,
    )

    entries = {}
    for m in line_re.finditer(out):
        ctrl = int(m.group(1))
        n_val = int(m.group(2))
        visited = int(m.group(3))
        entries[ctrl] = {"n": n_val, "visited": visited}

    if 0 not in entries or 1 not in entries:
        emit_fail("SR2", "missing ACCESS_TRACE output lines (got: %s)" % out[:300])
        return

    e0 = entries[0]
    e1 = entries[1]

    # Structural comparison: same n, same number of indices visited
    # (i.e. the loop touched every index in the same fixed order for
    # both control values). The fingerprint's numeric value is allowed
    # to differ since it encodes which specific elements changed, but
    # the shape (n, visited count) must be identical -- if a branch
    # skipped the whole loop for one ctrl value, "visited" or "n" would
    # differ, or the harness would report entirely different structure.
    if e0["n"] != e1["n"]:
        emit_fail("SR2", "access pattern size differs: ctrl=0 n=%d vs ctrl=1 n=%d" % (e0["n"], e1["n"]))
        return

    if e0["visited"] != e1["visited"]:
        emit_fail(
            "SR2",
            "index visitation count differs: ctrl=0 visited=%d vs ctrl=1 visited=%d"
            % (e0["visited"], e1["visited"]),
        )
        return

    emit_pass("SR2")


def run_sr3(binary_path):
    if already_decided("SR3"):
        return

    n = 4096
    trials = 401
    rc, out, err = run_proc([binary_path, "timing", str(n), str(trials)], timeout=60)

    if rc is None:
        emit_fail("SR3", "run crashed/timed out: %s" % (err if err else "unknown"))
        return

    if rc != 0:
        emit_fail("SR3", "harness exited with code %d during timing: %s" % (rc, err.strip()[:200]))
        return

    line_re = re.compile(
        r'^TIMING\s+ctrl=(\d+)\s+n=(\d+)\s+trials=(\d+)\s+median_us=([0-9.eE+-]+)\s*$',
        re.MULTILINE,
    )

    medians = {}
    for m in line_re.finditer(out):
        ctrl = int(m.group(1))
        median_us = float(m.group(4))
        medians[ctrl] = median_us

    if 0 not in medians or 1 not in medians:
        emit_fail("SR3", "missing TIMING output lines (got: %s)" % out[:300])
        return

    t0 = medians[0]
    t1 = medians[1]

    # Guard against zero/near-zero timings producing a spurious huge ratio.
    floor_us = 0.01
    t0_adj = max(t0, floor_us)
    t1_adj = max(t1, floor_us)

    ratio = max(t0_adj, t1_adj) / min(t0_adj, t1_adj)
    threshold = 3.0

    if ratio > threshold:
        emit_fail(
            "SR3",
            "timing differs too much between ctrl values: ctrl=0 median=%.4fus ctrl=1 median=%.4fus ratio=%.2fx (threshold=%.1fx)"
            % (t0, t1, ratio, threshold),
        )
        return

    emit_pass("SR3")


if __name__ == "__main__":
    main()