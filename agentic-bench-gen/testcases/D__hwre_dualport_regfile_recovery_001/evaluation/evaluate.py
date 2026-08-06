#!/usr/bin/env python3
"""
evaluate.py - Behavioral evaluator for hwre_dualport_regfile_recovery_001

Reads inputs/{design_brief.md,gate_netlist.v,obfuscated_wrapper.v} for reference
only. Grades submission/recovered_rtl.v by:
  1. Static fail-on-presence scans for SR1/SR2 banned constructs.
  2. Compiling with evaluation/tb_regfile.v via iverilog and running vvp.
  3. Comparing the simulated PROBE stream against a pure-Python reference
     model driven by an identical deterministic LCG-based stimulus sequence.

All requirement verdicts are printed as:
  [TEST] PASS: <id>
  [TEST] FAIL: <id>: <reason>

Exit code 0 iff every requirement passes.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUTS_DIR = os.path.join(REPO_ROOT, "inputs")
EVAL_DIR = os.path.join(REPO_ROOT, "evaluation")
SUBMISSION_PATH = os.path.join(REPO_ROOT, "submission", "recovered_rtl.v")
TB_PATH = os.path.join(EVAL_DIR, "tb_regfile.v")

REQUIRED_INPUT_FILES = ["gate_netlist.v", "obfuscated_wrapper.v", "design_brief.md"]

ALL_REQ_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3"]

results = {}  # id -> (bool_pass, reason)


def emit(req_id, ok, reason=""):
    if ok:
        print("[TEST] PASS: %s" % req_id)
    else:
        print("[TEST] FAIL: %s: %s" % (req_id, reason))
    results[req_id] = (ok, reason)


def fail_all_behavioral(reason):
    """Used when compile/run infra fails: fail every behaviorally-graded
    requirement (not SETUP) with the given reason."""
    for rid in ["FR1", "FR2", "FR3", "FR4", "SR1", "SR3"]:
        if rid not in results:
            emit(rid, False, reason)


def check_setup():
    for fname in REQUIRED_INPUT_FILES:
        fpath = os.path.join(INPUTS_DIR, fname)
        if not os.path.isfile(fpath):
            print("[TEST] FAIL: SETUP: %s not found" % fpath)
            sys.exit(1)
    if not os.path.isfile(SUBMISSION_PATH):
        print("[TEST] FAIL: SETUP: %s not found" % SUBMISSION_PATH)
        sys.exit(1)
    if not os.path.isfile(TB_PATH):
        print("[TEST] FAIL: SETUP: %s not found" % TB_PATH)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Static fail-on-presence scans for SR1 / SR2
# ---------------------------------------------------------------------------

def strip_comments(text):
    # remove /* */ block comments
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    # remove // line comments
    text = re.sub(r"//.*", "", text)
    return text


def static_scan(source_text):
    """Returns dict req_id -> (ok, reason) for SR1/SR2 static presence checks."""
    src = strip_comments(source_text)
    out = {}

    # SR1: banned construct is an extra registered pipeline stage on the
    # read-output path, i.e. rdata0/rdata1 (or intermediate regs that alone
    # feed them) assigned inside an always @(posedge clk) block via <=.
    # Vulnerability pattern (hypothetical bad submission):
    #   always @(posedge clk) begin
    #       rdata0 <= mem[raddr0];
    #       rdata1 <= mem[raddr1];
    #   end
    sr1_pattern = re.compile(
        r"always\s*@\s*\(\s*posedge\s+\w+\s*\)[^;]*?"
        r"\b(rdata0|rdata1)\s*<=",
        re.DOTALL,
    )
    m = sr1_pattern.search(src)
    if m:
        out["SR1_static"] = (False, "extra clocked register found driving read output: %r" % m.group(0)[:80])
    else:
        out["SR1_static"] = (True, "")

    # SR2: banned construct is a combinational bypass mux that compares
    # raddr==waddr (or waddr==raddr) together with we, and combinationally
    # selects wdata to forward around the register array, racing the
    # clocked update.
    # Vulnerability pattern (hypothetical bad submission):
    #   assign rdata0 = (raddr0 == waddr && we) ? wdata : mem[raddr0];
    sr2_pattern = re.compile(
        r"(?:assign\s+)?(?:rdata0|rdata1)\s*=\s*"
        r"\(?\s*"
        r"\(?\s*(?:raddr0|raddr1)\s*==\s*waddr\s*\)?"
        r"\s*(?:&&|&)\s*we\b"
        r".*?\?",
        re.DOTALL,
    )
    m2 = sr2_pattern.search(src)
    # also catch the reversed comparison order waddr==raddr0/1
    sr2_pattern_rev = re.compile(
        r"(?:assign\s+)?(?:rdata0|rdata1)\s*=\s*"
        r"\(?\s*"
        r"\(?\s*waddr\s*==\s*(?:raddr0|raddr1)\s*\)?"
        r"\s*(?:&&|&)\s*we\b"
        r".*?\?",
        re.DOTALL,
    )
    m2r = sr2_pattern_rev.search(src)
    if m2 or m2r:
        hit = m2.group(0) if m2 else m2r.group(0)
        out["SR2_static"] = (False, "combinational write-bypass mux racing clocked update found: %r" % hit[:80])
    else:
        out["SR2_static"] = (True, "")

    return out


# ---------------------------------------------------------------------------
# Deterministic stimulus generation (shared logic replicated in Verilog TB)
# ---------------------------------------------------------------------------
# LCG parameters: x_{n+1} = (a*x_n + c) mod m, seed=42
LCG_A = 1103515245
LCG_C = 12345
LCG_M = 2147483648  # 2^31
LCG_SEED = 42

NUM_CYCLES = 600


def lcg_stream(seed, n):
    x = seed
    vals = []
    for _ in range(n):
        x = (LCG_A * x + LCG_C) % LCG_M
        vals.append(x)
    return vals


def build_stimulus():
    """Builds the exact same per-cycle stimulus as tb_regfile.v, driven by
    the LCG sequence. Returns a list of dicts with keys:
    rst, we, waddr, wdata, raddr0, raddr1
    Special phases are also encoded matching the testbench:
      - cycles 0..3: plain writes to addr 0..3 with fixed data values
        0x00, 0xFF, 0xA5, 0x3C respectively, we=1, rst=0,
        raddr0/raddr1 don't-care-but-set to 0.
      - cycle 4: reset pulse (rst=1), we=0
      - cycle 5: post-reset read-only cycle (we=0, rst=0), raddr sweep 0..3
        handled via subsequent randomized cycles anyway
      - cycles 6..599: randomized using LCG stream, with periodic forced
        collision cycles (every 10th cycle raddr0=waddr, every 13th cycle
        raddr1=waddr) to exercise FR3/SR2, and forced dual-independent-read
        cycles (every 7th cycle raddr0 != raddr1) to exercise FR4.
    """
    stim = []

    fixed_data = [0x00, 0xFF, 0xA5, 0x3C]
    for a in range(4):
        stim.append({
            "rst": 0, "we": 1, "waddr": a, "wdata": fixed_data[a],
            "raddr0": a, "raddr1": (a + 1) % 4,
        })

    # reset pulse cycle
    stim.append({"rst": 1, "we": 0, "waddr": 0, "wdata": 0,
                 "raddr0": 0, "raddr1": 1})

    # post-reset read-only cycle (no write), sweep addresses across raddr0/raddr1
    stim.append({"rst": 0, "we": 0, "waddr": 0, "wdata": 0,
                 "raddr0": 2, "raddr1": 3})

    remaining = NUM_CYCLES - len(stim)
    lcg_vals = lcg_stream(LCG_SEED, remaining * 6)  # 6 draws per cycle
    idx = 0
    for i in range(remaining):
        cyc_no = len(stim)
        we = lcg_vals[idx] % 2; idx += 1
        waddr = lcg_vals[idx] % 4; idx += 1
        wdata = lcg_vals[idx] % 256; idx += 1
        raddr0 = lcg_vals[idx] % 4; idx += 1
        raddr1 = lcg_vals[idx] % 4; idx += 1
        rst_roll = lcg_vals[idx] % 50; idx += 1
        rst = 1 if rst_roll == 0 else 0

        # force periodic collision on raddr0
        if cyc_no % 10 == 0:
            raddr0 = waddr
        # force periodic collision on raddr1
        if cyc_no % 13 == 0:
            raddr1 = waddr
        # force periodic dual-independent-read distinctness
        if cyc_no % 7 == 0 and raddr0 == raddr1:
            raddr1 = (raddr1 + 1) % 4

        stim.append({
            "rst": rst, "we": we, "waddr": waddr, "wdata": wdata,
            "raddr0": raddr0, "raddr1": raddr1,
        })

    return stim


def run_reference_model(stim):
    """Pure python reference model: 4x8 synchronous-write, combinational-read
    register file with synchronous active-high reset and natural write
    forwarding (registered array read after the edge). Returns a list of
    (rdata0, rdata1) sampled AFTER each rising edge (i.e. the standard
    post-edge combinational read value for that cycle)."""
    mem = [0, 0, 0, 0]
    out = []
    for cyc in stim:
        # apply edge semantics: reset takes priority, else write if we=1
        if cyc["rst"]:
            mem = [0, 0, 0, 0]
        elif cyc["we"]:
            mem[cyc["waddr"]] = cyc["wdata"] & 0xFF
        rdata0 = mem[cyc["raddr0"]]
        rdata1 = mem[cyc["raddr1"]]
        out.append((rdata0, rdata1))
    return out


def mem_state_before_edge(stim):
    """Returns list of mem-array snapshots (list of 4 bytes) representing the
    state BEFORE each cycle's edge is applied, used to compute the
    old-value the read port should see mid-cycle prior to the edge."""
    mem = [0, 0, 0, 0]
    snapshots = []
    for cyc in stim:
        snapshots.append(list(mem))
        if cyc["rst"]:
            mem = [0, 0, 0, 0]
        elif cyc["we"]:
            mem[cyc["waddr"]] = cyc["wdata"] & 0xFF
    return snapshots


# ---------------------------------------------------------------------------
# Generate stimulus file consumed by the Verilog testbench (shared source of
# truth so Python reference and TB stimulus never diverge).
# ---------------------------------------------------------------------------

def write_stimulus_file(stim, path):
    with open(path, "w") as f:
        f.write("%d\n" % len(stim))
        for cyc in stim:
            f.write("%d %d %d %d %d %d\n" % (
                cyc["rst"], cyc["we"], cyc["waddr"], cyc["wdata"],
                cyc["raddr0"], cyc["raddr1"]))


# ---------------------------------------------------------------------------
# Compile & simulate
# ---------------------------------------------------------------------------

def compile_and_run(tmpdir, stim_file_path):
    sim_path = os.path.join(tmpdir, "sim.vvp")
    compile_cmd = [
        "iverilog", "-g2012", "-o", sim_path,
        SUBMISSION_PATH, TB_PATH,
    ]
    try:
        cp = subprocess.run(
            compile_cmd, cwd=REPO_ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=60, text=True,
        )
    except subprocess.TimeoutExpired:
        return None, "iverilog compile timed out"
    if cp.returncode != 0:
        err = (cp.stderr or cp.stdout or "").strip()
        err_lines = [l for l in err.splitlines() if l.strip()]
        summary = " | ".join(err_lines[-8:]) if err_lines else "unknown compile error"
        return None, "compile failed: %s" % summary

    run_cmd = ["vvp", sim_path, "+STIMFILE=%s" % stim_file_path]
    try:
        rp = subprocess.run(
            run_cmd, cwd=REPO_ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=60, text=True,
        )
    except subprocess.TimeoutExpired:
        return None, "run crashed/timed out"
    if rp.returncode != 0 and "DONE" not in (rp.stdout or ""):
        err = (rp.stderr or "").strip()
        return None, "run crashed/timed out: %s" % (err[-300:] if err else "nonzero exit, no DONE marker")
    return rp.stdout, None


def parse_probes(stdout_text):
    """Parses lines of form:
       PROBE <cycle> <rdata0_hex> <rdata1_hex>
       PROBE_MID <cycle> <rdata0_hex> <rdata1_hex>
    Returns (probes_by_cycle, mid_probes_by_cycle, saw_done)."""
    probes = {}
    mids = {}
    saw_done = False
    probe_re = re.compile(r"^PROBE\s+(\d+)\s+([0-9A-Fa-f]{1,2})\s+([0-9A-Fa-f]{1,2})\s*$")
    mid_re = re.compile(r"^PROBE_MID\s+(\d+)\s+([0-9A-Fa-f]{1,2})\s+([0-9A-Fa-f]{1,2})\s*$")
    for line in stdout_text.splitlines():
        line = line.strip()
        m = probe_re.match(line)
        if m:
            cyc = int(m.group(1))
            v0 = int(m.group(2), 16)
            v1 = int(m.group(3), 16)
            probes[cyc] = (v0, v1)
            continue
        mm = mid_re.match(line)
        if mm:
            cyc = int(mm.group(1))
            v0 = int(mm.group(2), 16)
            v1 = int(mm.group(3), 16)
            mids[cyc] = (v0, v1)
            continue
        if line == "DONE" or line.endswith("DONE"):
            saw_done = True
    return probes, mids, saw_done


# ---------------------------------------------------------------------------
# Main grading logic
# ---------------------------------------------------------------------------

def main():
    check_setup()

    with open(SUBMISSION_PATH, "r") as f:
        source_text = f.read()

    static_results = static_scan(source_text)

    stim = build_stimulus()
    ref_out = run_reference_model(stim)
    pre_edge_snapshots = mem_state_before_edge(stim)

    # metric accumulators, filled in as sim data becomes available
    metrics = {
        "cycle_accurate_match_rate": 0.0,
        "word_recovery_rate": 0.0,
        "structural_match_accuracy": 0.0,
        "functional_equivalence": 0.0,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        stim_file_path = os.path.join(tmpdir, "stimulus.txt")
        write_stimulus_file(stim, stim_file_path)

        stdout_text, err = compile_and_run(tmpdir, stim_file_path)

        fr_flags = {}  # id -> bool, for functional_equivalence metric

        if err is not None:
            fail_all_behavioral(err)
            # still report static SR checks below since they don't depend on sim
        else:
            probes, mids, saw_done = parse_probes(stdout_text)

            if not saw_done:
                fail_all_behavioral("simulation did not emit DONE marker; possible crash/incomplete run")
            else:
                # ---- cycle_accurate_match_rate: fraction of all PROBE cycles matching ----
                total_cycles = len(stim)
                matched_cycles = 0
                for cyc_no in range(total_cycles):
                    got = probes.get(cyc_no)
                    exp = ref_out[cyc_no]
                    if got is not None and got == exp:
                        matched_cycles += 1
                metrics["cycle_accurate_match_rate"] = (
                    matched_cycles / float(total_cycles) if total_cycles > 0 else 0.0
                )

                # ---- word_recovery_rate: per-address targeted write-then-read ----
                word_hits = 0
                for a in range(4):
                    exp = ref_out[a]
                    got = probes.get(a)
                    if got is not None and got == exp:
                        word_hits += 1
                metrics["word_recovery_rate"] = word_hits / 4.0

                # ---- FR1: basic write-then-read for cycles 0..3 (fixed data) ----
                fr1_ok = True
                fr1_reason = ""
                for cyc_no in range(4):
                    exp = ref_out[cyc_no]
                    got = probes.get(cyc_no)
                    if got is None:
                        fr1_ok = False
                        fr1_reason = "missing PROBE for cycle %d" % cyc_no
                        break
                    if got != exp:
                        fr1_ok = False
                        fr1_reason = "cycle %d expected rdata=(0x%02X,0x%02X) got (0x%02X,0x%02X)" % (
                            cyc_no, exp[0], exp[1], got[0], got[1])
                        break
                emit("FR1", fr1_ok, fr1_reason)
                fr_flags["FR1"] = fr1_ok

                # ---- FR2: reset clears all 4 entries; check post-reset cycle ----
                reset_cycle = 4
                post_reset_cycle = 5
                fr2_ok = True
                fr2_reason = ""
                exp = ref_out[post_reset_cycle]
                got = probes.get(post_reset_cycle)
                if got is None:
                    fr2_ok = False
                    fr2_reason = "missing PROBE for post-reset cycle %d" % post_reset_cycle
                elif got != (0, 0) or exp != (0, 0):
                    fr2_ok = False
                    fr2_reason = "post-reset cycle %d expected all-zero reads, ref=(0x%02X,0x%02X) got=(0x%02X,0x%02X)" % (
                        post_reset_cycle, exp[0], exp[1], got[0], got[1])
                emit("FR2", fr2_ok, fr2_reason)
                fr_flags["FR2"] = fr2_ok

                # ---- FR3: same-address collision forwarding ----
                fr3_ok = True
                fr3_reason = ""
                collision_cycles_checked = 0
                for cyc_no, cyc in enumerate(stim):
                    if cyc["we"] == 1 and cyc["rst"] == 0:
                        exp = ref_out[cyc_no]
                        got = probes.get(cyc_no)
                        collided0 = (cyc["raddr0"] == cyc["waddr"])
                        collided1 = (cyc["raddr1"] == cyc["waddr"])
                        if collided0 or collided1:
                            collision_cycles_checked += 1
                            if got is None:
                                fr3_ok = False
                                fr3_reason = "missing PROBE for collision cycle %d" % cyc_no
                                break
                            if collided0 and got[0] != exp[0]:
                                fr3_ok = False
                                fr3_reason = ("collision cycle %d raddr0==waddr: expected new value 0x%02X "
                                              "got 0x%02X (old value semantics detected)") % (cyc_no, exp[0], got[0])
                                break
                            if collided1 and got[1] != exp[1]:
                                fr3_ok = False
                                fr3_reason = ("collision cycle %d raddr1==waddr: expected new value 0x%02X "
                                              "got 0x%02X (old value semantics detected)") % (cyc_no, exp[1], got[1])
                                break
                if fr3_ok and collision_cycles_checked == 0:
                    fr3_ok = False
                    fr3_reason = "no collision cycles were exercised by stimulus (test harness defect)"
                emit("FR3", fr3_ok, fr3_reason)
                fr_flags["FR3"] = fr3_ok

                # ---- FR4: dual independent read ports ----
                fr4_ok = True
                fr4_reason = ""
                indep_checked = 0
                for cyc_no, cyc in enumerate(stim):
                    if cyc["raddr0"] != cyc["raddr1"]:
                        exp = ref_out[cyc_no]
                        got = probes.get(cyc_no)
                        if got is None:
                            fr4_ok = False
                            fr4_reason = "missing PROBE for cycle %d" % cyc_no
                            break
                        indep_checked += 1
                        if got != exp:
                            fr4_ok = False
                            fr4_reason = "cycle %d independent-read mismatch expected=(0x%02X,0x%02X) got=(0x%02X,0x%02X)" % (
                                cyc_no, exp[0], exp[1], got[0], got[1])
                            break
                if fr4_ok and indep_checked == 0:
                    fr4_ok = False
                    fr4_reason = "no independent-read cycles were exercised by stimulus (test harness defect)"
                emit("FR4", fr4_ok, fr4_reason)
                fr_flags["FR4"] = fr4_ok

                # ---- SR1 (behavioral part): mid-cycle address toggle zero latency ----
                sr1_behavior_ok = True
                sr1_behavior_reason = ""
                if len(mids) == 0:
                    sr1_behavior_ok = False
                    sr1_behavior_reason = "no PROBE_MID lines observed; harness did not exercise mid-cycle toggling"
                else:
                    for cyc_no, (v0, v1) in mids.items():
                        # mid-cycle probe occurs AFTER the edge at cyc_no has committed,
                        # with addresses toggled to point at whatever the post-edge state holds.
                        # It must match the post-edge reference state for that same cycle
                        # at the (possibly different) mid-cycle addresses, which the TB
                        # encodes by re-using raddr0/raddr1 from the *next* stimulus cycle
                        # (cyc_no+1) applied combinationally to the *current* (cyc_no) mem state.
                        if cyc_no + 1 >= len(stim):
                            continue
                        next_cyc = stim[cyc_no + 1]
                        mem_snapshot = list(pre_edge_snapshots[cyc_no])
                        c = stim[cyc_no]
                        if c["rst"]:
                            mem_snapshot = [0, 0, 0, 0]
                        elif c["we"]:
                            mem_snapshot[c["waddr"]] = c["wdata"] & 0xFF
                        exp0 = mem_snapshot[next_cyc["raddr0"]]
                        exp1 = mem_snapshot[next_cyc["raddr1"]]
                        if (v0, v1) != (exp0, exp1):
                            sr1_behavior_ok = False
                            sr1_behavior_reason = (
                                "mid-cycle probe after cycle %d expected (0x%02X,0x%02X) "
                                "at toggled addresses but got (0x%02X,0x%02X); read appears "
                                "to require an extra clock edge (nonzero latency)"
                            ) % (cyc_no, exp0, exp1, v0, v1)
                            break

                sr1_static_ok, sr1_static_reason = static_results["SR1_static"]
                sr1_ok = sr1_behavior_ok and sr1_static_ok
                if not sr1_ok:
                    reason_parts = []
                    if not sr1_behavior_ok:
                        reason_parts.append(sr1_behavior_reason)
                    if not sr1_static_ok:
                        reason_parts.append(sr1_static_reason)
                    emit("SR1", False, "; ".join(reason_parts))
                else:
                    emit("SR1", True)

                # ---- SR3: reset must not leak stale data before first post-reset write ----
                sr3_ok = True
                sr3_reason = ""
                exp4 = ref_out[reset_cycle]
                got4 = probes.get(reset_cycle)
                if got4 is None:
                    sr3_ok = False
                    sr3_reason = "missing PROBE for reset-cycle %d" % reset_cycle
                elif got4 != (0, 0):
                    sr3_ok = False
                    sr3_reason = "reset cycle %d read ports show nonzero/stale data got=(0x%02X,0x%02X)" % (
                        reset_cycle, got4[0], got4[1])
                elif exp4 != (0, 0) or ref_out[post_reset_cycle] != (0, 0) or probes.get(post_reset_cycle) != (0, 0):
                    sr3_ok = False
                    sr3_reason = "reset-then-read did not yield all-zero on submission or reference"
                emit("SR3", sr3_ok, sr3_reason)

        # functional_equivalence: fraction of FR1-FR4 scenario booleans that passed
        fr_ids = ["FR1", "FR2", "FR3", "FR4"]
        fr_pass_count = sum(1 for rid in fr_ids if results.get(rid, (False, ""))[0])
        metrics["functional_equivalence"] = fr_pass_count / float(len(fr_ids))

    # ---- SR2: purely static fail-on-presence (independent of sim outcome) ----
    sr2_static_ok, sr2_static_reason = static_results["SR2_static"]
    emit("SR2", sr2_static_ok, sr2_static_reason)

    # structural_match_accuracy: 1.0 iff both static scans found no banned construct
    sr1_static_ok2, _ = static_results["SR1_static"]
    sr2_static_ok2, _ = static_results["SR2_static"]
    metrics["structural_match_accuracy"] = 1.0 if (sr1_static_ok2 and sr2_static_ok2) else 0.0

    # In case the sim/compile branch above failed before FR/SR1/SR3 were set
    # (fail_all_behavioral already covers FR1-4,SR1,SR3), ensure every id has
    # a recorded result.
    for rid in ALL_REQ_IDS:
        if rid not in results:
            emit(rid, False, "requirement was not evaluated (internal harness gap)")

    # Recompute functional_equivalence defensively in case the behavioral
    # branch never ran (compile/run failure path) -- reflect final FR states.
    fr_ids = ["FR1", "FR2", "FR3", "FR4"]
    fr_pass_count = sum(1 for rid in fr_ids if results.get(rid, (False, ""))[0])
    metrics["functional_equivalence"] = fr_pass_count / float(len(fr_ids))

    print("METRICS: %s" % json.dumps(metrics, sort_keys=True))

    all_pass = all(v[0] for v in results.values())
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()