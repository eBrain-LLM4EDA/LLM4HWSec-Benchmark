#!/usr/bin/env python3
"""
evaluate.py -- grades submission/recovered_rtl.v against the pinned
quad_decoder interface using cycle-accurate simulation via iverilog/vvp,
compared against an independently-authored Python reference model.
"""

import os
import re
import subprocess
import sys
import tempfile

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3"]

INPUT_FILES = [
    "inputs/quadrature_netlist.v",
    "inputs/quadrature_wrapper.v",
    "inputs/design_brief.md",
]

SUBMISSION_FILE = "submission/recovered_rtl.v"
TB_FILE = "evaluation/tb_quad_decoder.v"

results = {}


def emit_pass(rid):
    results[rid] = ("PASS", "")
    print("[TEST] PASS: %s" % rid)


def emit_fail(rid, reason):
    results[rid] = ("FAIL", reason)
    print("[TEST] FAIL: %s: %s" % (rid, reason))


# -----------------------------------------------------------------------
# Stimulus sequence -- must exactly match the pattern array embedded in
# evaluation/tb_quad_decoder.v (segments FWD, REV, BOUNCE, ILL1, ILL2).
# Each entry is a (a, b) tuple.
# -----------------------------------------------------------------------
STIMULUS = [
    # FWD segment: 00,01,11,10,00,01,11,10,00  (indices 0..8)
    (0, 0), (0, 1), (1, 1), (1, 0), (0, 0), (0, 1), (1, 1), (1, 0), (0, 0),
    # REV segment: 00,10,11,01,00,10,11,01,00  (indices 9..17)
    (0, 0), (1, 0), (1, 1), (0, 1), (0, 0), (1, 0), (1, 1), (0, 1), (0, 0),
    # BOUNCE segment: 00,00,00 (indices 18..20)
    (0, 0), (0, 0), (0, 0),
    # ILL1 segment (indices 21..25): 00, 11(illegal jump), 11(hold), 10(legal fwd), 10(hold)
    (0, 0), (1, 1), (1, 1), (1, 0), (1, 0),
    # ILL2 segment (indices 26..30): 01(illegal jump from 10), 01(hold), 00(legal rev), 00(hold), 00(hold)
    (0, 1), (0, 1), (0, 0), (0, 0), (0, 0),
]

assert len(STIMULUS) == 31

# Segment index ranges (inclusive), matching the testbench comments.
SEG_FWD = (0, 8)
SEG_REV = (9, 17)
SEG_BOUNCE = (18, 20)
SEG_ILL1 = (21, 25)
SEG_ILL2 = (26, 30)


def wrap8(v):
    """Wrap an integer into signed 8-bit two's complement range."""
    v = v & 0xFF
    if v >= 128:
        v -= 256
    return v


def gray_forward_step(prev, cur):
    """True if (prev->cur) is a legal forward Gray step: 00->01->11->10->00."""
    order = [(0, 0), (0, 1), (1, 1), (1, 0)]
    idx = order.index(prev)
    nxt = order[(idx + 1) % 4]
    return cur == nxt


def gray_reverse_step(prev, cur):
    """True if (prev->cur) is a legal reverse Gray step: 00->10->11->01->00."""
    order = [(0, 0), (0, 1), (1, 1), (1, 0)]
    idx = order.index(prev)
    nxt = order[(idx - 1) % 4]
    return cur == nxt


def compute_reference(stimulus):
    """
    Independently-derived reference model of the pinned quad_decoder
    interface semantics (Moore outputs, synchronous active-high reset,
    1-cycle latency, Gray-code adjacency, single-cycle invalid pulse).

    Returns a list of (pos, dir, invalid) tuples, one per stimulus cycle,
    representing the OBSERVED values immediately after the rising edge
    that samples that stimulus entry (matching the testbench's PROBE
    timing: printed shortly after the posedge that samples pattern[i]).
    """
    pos = 0
    dir_ = 0
    invalid = 0
    prev_state = None  # S(N-1); None only before the very first sample

    out = []
    for (a, b) in stimulus:
        cur_state = (a, b)
        if prev_state is None:
            # First post-reset sample: there is no prior sampled state to
            # compare against yet from this stimulus stream (the design's
            # internal previous-state register was zeroed by reset, and
            # the very first post-reset edge compares reset-state (00)
            # against the first stimulus value). We model this as: the
            # state at reset release is (0,0), i.e. S(-1) = (0,0).
            prev_state = (0, 0)

        if cur_state == prev_state:
            # hold
            pass
        elif gray_forward_step(prev_state, cur_state):
            pos = wrap8(pos + 1)
            dir_ = 1
            invalid = 0
        elif gray_reverse_step(prev_state, cur_state):
            pos = wrap8(pos - 1)
            dir_ = 0
            invalid = 0
        else:
            # illegal two-bit jump: pos/dir hold, invalid asserts this cycle
            invalid = 1
            out.append((pos, dir_, invalid))
            prev_state = cur_state
            continue

        # legal transition or hold clears invalid
        invalid = 0
        out.append((pos, dir_, invalid))
        prev_state = cur_state

    return out


def main():
    # -------------------------------------------------------------------
    # SETUP checks
    # -------------------------------------------------------------------
    for f in INPUT_FILES:
        if not os.path.isfile(f):
            print("[TEST] FAIL: SETUP: %s not found" % f)
            sys.exit(1)

    if not os.path.isfile(SUBMISSION_FILE):
        print("[TEST] FAIL: SETUP: %s not found" % SUBMISSION_FILE)
        sys.exit(1)

    if not os.path.isfile(TB_FILE):
        print("[TEST] FAIL: SETUP: %s not found" % TB_FILE)
        sys.exit(1)

    # -------------------------------------------------------------------
    # SR3: static fail-on-presence scan
    # Vulnerability in baseline-style backdoors would look like forcing
    # outputs or terminating simulation early, e.g. constructs such as:
    #   "$stop;" / "$finish;" inside the submitted module, "force pos = ...",
    #   "$deposit(...)", or "`ifdef TESTBENCH ... `endif" guarding fake logic.
    # None of these constructs should appear in submission/recovered_rtl.v.
    # -------------------------------------------------------------------
    try:
        with open(SUBMISSION_FILE, "r") as fh:
            submission_src = fh.read()
    except Exception as e:
        emit_fail("SR3", "could not read submission file: %s" % e)
        submission_src = ""

    forbidden_patterns = [
        (r'\$stop\b', "$stop"),
        (r'\$finish\b', "$finish"),
        (r'\bforce\s+\w', "force <signal>"),
        (r'\$deposit\s*\(', "$deposit("),
        (r'`ifdef\s+TESTBENCH', "`ifdef TESTBENCH"),
    ]

    sr3_hit = None
    for pattern, label in forbidden_patterns:
        if re.search(pattern, submission_src):
            sr3_hit = label
            break

    if sr3_hit is not None:
        emit_fail("SR3", "forbidden construct found in submission: %s" % sr3_hit)
    elif "SR3" not in results:
        emit_pass("SR3")

    # -------------------------------------------------------------------
    # Compile submission + testbench with iverilog
    # -------------------------------------------------------------------
    tmpdir = tempfile.mkdtemp(prefix="quad_decoder_eval_")
    sim_path = os.path.join(tmpdir, "sim.vvp")

    compile_cmd = [
        "iverilog", "-g2012", "-o", sim_path,
        SUBMISSION_FILE, TB_FILE,
    ]

    compile_ok = True
    compile_err_summary = ""
    try:
        proc = subprocess.run(
            compile_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        if proc.returncode != 0:
            compile_ok = False
            stderr_text = proc.stderr.decode("utf-8", errors="replace")
            stdout_text = proc.stdout.decode("utf-8", errors="replace")
            combined = (stderr_text + "\n" + stdout_text).strip()
            lines = [l for l in combined.splitlines() if l.strip()]
            compile_err_summary = " | ".join(lines[:8]) if lines else "iverilog returned nonzero with no output"
    except subprocess.TimeoutExpired:
        compile_ok = False
        compile_err_summary = "iverilog compilation timed out"
    except FileNotFoundError:
        compile_ok = False
        compile_err_summary = "iverilog not found on PATH"
    except Exception as e:
        compile_ok = False
        compile_err_summary = "unexpected error invoking iverilog: %s" % e

    behavioral_ids = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2"]

    if not compile_ok:
        for rid in behavioral_ids:
            emit_fail(rid, "compile failed: %s" % compile_err_summary)
        finalize_and_exit()
        return

    # -------------------------------------------------------------------
    # Run simulation with vvp
    # -------------------------------------------------------------------
    run_ok = True
    run_err_summary = ""
    stdout_text = ""
    try:
        proc = subprocess.run(
            ["vvp", sim_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        stdout_text = proc.stdout.decode("utf-8", errors="replace")
        stderr_text = proc.stderr.decode("utf-8", errors="replace")
        if proc.returncode != 0 and "PROBE:DONE" not in stdout_text:
            run_ok = False
            combined = (stderr_text + "\n" + stdout_text).strip()
            lines = [l for l in combined.splitlines() if l.strip()]
            run_err_summary = " | ".join(lines[-8:]) if lines else "vvp returned nonzero with no output"
    except subprocess.TimeoutExpired:
        run_ok = False
        run_err_summary = "simulation timed out"
    except FileNotFoundError:
        run_ok = False
        run_err_summary = "vvp not found on PATH"
    except Exception as e:
        run_ok = False
        run_err_summary = "unexpected error invoking vvp: %s" % e

    if not run_ok:
        for rid in behavioral_ids:
            emit_fail(rid, "run crashed/timed out: %s" % run_err_summary)
        finalize_and_exit()
        return

    if "PROBE:DONE" not in stdout_text:
        for rid in behavioral_ids:
            emit_fail(rid, "run crashed/timed out: simulation did not reach PROBE:DONE")
        finalize_and_exit()
        return

    # -------------------------------------------------------------------
    # Parse PROBE lines: PROBE:S<idx>:<cycle>:<pos>:<dir>:<invalid>
    # -------------------------------------------------------------------
    probe_re = re.compile(r'^PROBE:S(\d+):(-?\d+):(-?\d+):([01]):([01])$')
    observed = {}
    for line in stdout_text.splitlines():
        line = line.strip()
        m = probe_re.match(line)
        if m:
            idx = int(m.group(1))
            pos_val = int(m.group(3))
            dir_val = int(m.group(4))
            invalid_val = int(m.group(5))
            observed[idx] = (pos_val, dir_val, invalid_val)

    expected_seq = compute_reference(STIMULUS)

    missing = [i for i in range(len(STIMULUS)) if i not in observed]
    if missing:
        reason = "missing PROBE lines for indices %s" % missing[:5]
        for rid in behavioral_ids:
            emit_fail(rid, reason)
        finalize_and_exit()
        return

    def cycles_match(lo, hi):
        """Return list of mismatch descriptions for indices lo..hi inclusive."""
        mismatches = []
        for i in range(lo, hi + 1):
            exp = expected_seq[i]
            obs = observed[i]
            if exp != obs:
                mismatches.append(
                    "idx=%d expected(pos=%d,dir=%d,invalid=%d) observed(pos=%d,dir=%d,invalid=%d)"
                    % (i, exp[0], exp[1], exp[2], obs[0], obs[1], obs[2])
                )
        return mismatches

    # ---------------- FR1: forward run segment ----------------
    mism = cycles_match(SEG_FWD[0], SEG_FWD[1])
    if mism:
        emit_fail("FR1", "forward-run mismatch: " + mism[0])
    else:
        emit_pass("FR1")

    # ---------------- FR2: reverse run segment ----------------
    mism = cycles_match(SEG_REV[0], SEG_REV[1])
    if mism:
        emit_fail("FR2", "reverse-run mismatch: " + mism[0])
    else:
        emit_pass("FR2")

    # ---------------- FR3: stationary/bounce segment ----------------
    mism = cycles_match(SEG_BOUNCE[0], SEG_BOUNCE[1])
    if mism:
        emit_fail("FR3", "bounce-segment mismatch: " + mism[0])
    else:
        emit_pass("FR3")

    # ---------------- FR4: illegal diagonal jump behavior ----------------
    # Covers both ILL1 (00->11) and ILL2 (10->01, the other diagonal pair)
    # segments: invalid pulses exactly one cycle, pos/dir unaffected by the
    # illegal transition itself.
    mism = cycles_match(SEG_ILL1[0], SEG_ILL1[1])
    mism += cycles_match(SEG_ILL2[0], SEG_ILL2[1])
    if mism:
        emit_fail("FR4", "illegal-jump segment mismatch: " + mism[0])
    else:
        emit_pass("FR4")

    # ---------------- SR1: pos/dir unchanged across illegal edge ----------------
    # For each illegal-jump index (21 for ILL1, 26 for ILL2), pos and dir at
    # that index and the index immediately after must equal the values from
    # the cycle immediately BEFORE the illegal index.
    sr1_failures = []
    illegal_indices = [22, 26]  # index of the cycle where the illegal jump lands
    # NOTE: index 22 is where pattern jumps 00->11 (illegal); the "before"
    # reference is index 21. Index 26 is where pattern jumps 10->01
    # (illegal); the "before" reference is index 25.
    before_map = {22: 21, 26: 25}
    for ill_idx in illegal_indices:
        before_idx = before_map[ill_idx]
        after_idx = ill_idx + 1
        exp_pos_before, exp_dir_before, _ = expected_seq[before_idx]
        obs_pos_before, obs_dir_before, _ = observed[before_idx]
        obs_pos_ill, obs_dir_ill, _ = observed[ill_idx]
        obs_pos_after, obs_dir_after, _ = observed[after_idx]

        if obs_pos_ill != obs_pos_before or obs_dir_ill != obs_dir_before:
            sr1_failures.append(
                "at illegal idx=%d pos/dir changed: before(pos=%d,dir=%d) illegal(pos=%d,dir=%d)"
                % (ill_idx, obs_pos_before, obs_dir_before, obs_pos_ill, obs_dir_ill)
            )
        if obs_pos_after != obs_pos_before or obs_dir_after != obs_dir_before:
            sr1_failures.append(
                "at idx=%d (cycle after illegal idx=%d) pos/dir changed: before(pos=%d,dir=%d) after(pos=%d,dir=%d)"
                % (after_idx, ill_idx, obs_pos_before, obs_dir_before, obs_pos_after, obs_dir_after)
            )

    if sr1_failures:
        emit_fail("SR1", sr1_failures[0])
    else:
        emit_pass("SR1")

    # ---------------- SR2: invalid asserted exactly 1 cycle ----------------
    sr2_failures = []
    for ill_idx in illegal_indices:
        obs_invalid_ill = observed[ill_idx][2]
        if obs_invalid_ill != 1:
            sr2_failures.append(
                "invalid not asserted at illegal idx=%d (observed invalid=%d)"
                % (ill_idx, obs_invalid_ill)
            )
            continue

        # Determine how many subsequent stimulus cycles are available before
        # the next illegal index or end of stimulus, to check invalid clears
        # and stays clear for >=3 cycles (bounded by available data).
        next_illegal = None
        for other in illegal_indices:
            if other > ill_idx:
                next_illegal = other
                break
        limit = (next_illegal - 1) if next_illegal is not None else (len(STIMULUS) - 1)

        check_upto = min(ill_idx + 3, limit)
        consecutive_high = 0
        idx = ill_idx
        while idx <= limit and observed[idx][2] == 1:
            consecutive_high += 1
            idx += 1
        if consecutive_high != 1:
            sr2_failures.append(
                "invalid asserted for %d consecutive cycles starting at idx=%d (expected exactly 1)"
                % (consecutive_high, ill_idx)
            )
            continue

        for j in range(ill_idx + 1, check_upto + 1):
            if observed[j][2] != 0:
                sr2_failures.append(
                    "invalid unexpectedly asserted at idx=%d following illegal idx=%d (sticky/re-assert)"
                    % (j, ill_idx)
                )

    if sr2_failures:
        emit_fail("SR2", sr2_failures[0])
    else:
        emit_pass("SR2")

    finalize_and_exit()


def finalize_and_exit():
    for rid in REQUIREMENT_IDS:
        if rid not in results:
            # Should never happen, but guard against silent omission.
            emit_fail(rid, "requirement was not evaluated")

    any_fail = any(status == "FAIL" for status, _ in results.values())
    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()