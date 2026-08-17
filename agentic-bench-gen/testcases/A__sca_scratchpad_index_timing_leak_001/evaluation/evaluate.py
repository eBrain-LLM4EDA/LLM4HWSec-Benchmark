#!/usr/bin/env python3
"""
evaluate.py - Grader for side_channel_fault_analysis / scratchpad_lookup timing leak task.

Grades submission/vulnerability_report.json against inputs/scratchpad_lookup.v,
inputs/testbench_timing.v, inputs/design_brief.md (used for reference / ground
truth simulation), per FR1-FR4 and SR1-SR4.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]

INPUTS_DIR = "inputs"
EVAL_DIR = "evaluation"
SUBMISSION_PATH = os.path.join("submission", "vulnerability_report.json")

RTL_FILE = os.path.join(INPUTS_DIR, "scratchpad_lookup.v")
TB_TIMING_FILE = os.path.join(INPUTS_DIR, "testbench_timing.v")
DESIGN_BRIEF_FILE = os.path.join(INPUTS_DIR, "design_brief.md")
TB_LEAK_CHECK_FILE = os.path.join(EVAL_DIR, "tb_leak_check.v")

results = {}  # id -> (bool passed, str reason)


def record(req_id, passed, reason=""):
    results[req_id] = (passed, reason)
    if passed:
        print("[TEST] PASS: {}".format(req_id))
    else:
        print("[TEST] FAIL: {}: {}".format(req_id, reason))


def fail_all_setup(reason):
    for rid in REQUIREMENT_IDS:
        record(rid, False, "SETUP: " + reason)


def check_required_inputs_exist():
    missing = []
    for f in [RTL_FILE, TB_TIMING_FILE, DESIGN_BRIEF_FILE]:
        if not os.path.isfile(f):
            missing.append(f)
    if missing:
        for m in missing:
            print("[TEST] FAIL: SETUP: {} not found".format(m))
        fail_all_setup("required input artifact(s) missing: {}".format(", ".join(missing)))
        return False
    if not os.path.isfile(TB_LEAK_CHECK_FILE):
        print("[TEST] FAIL: SETUP: {} not found".format(TB_LEAK_CHECK_FILE))
        fail_all_setup("harness file missing: {}".format(TB_LEAK_CHECK_FILE))
        return False
    return True


def load_submission():
    if not os.path.isfile(SUBMISSION_PATH):
        print("[TEST] FAIL: SETUP: {} not found".format(SUBMISSION_PATH))
        fail_all_setup("{} not found".format(SUBMISSION_PATH))
        return None
    try:
        with open(SUBMISSION_PATH, "r") as f:
            data = json.load(f)
    except Exception as e:
        for rid in REQUIREMENT_IDS:
            record(rid, False, "submission is not valid JSON: {}".format(e))
        return None
    if not isinstance(data, dict):
        for rid in REQUIREMENT_IDS:
            record(rid, False, "submission JSON top-level must be an object")
        return None
    return data


def run_simulation():
    """Compile and run tb_leak_check.v with inputs/scratchpad_lookup.v via iverilog/vvp.
    Returns dict: {0: {cycles:int, data_out:{offset:val}}, 1: {...}} or None on failure,
    plus raw stdout for diagnostics.
    """
    tmpdir = tempfile.mkdtemp(prefix="sca_eval_")
    vvp_path = os.path.join(tmpdir, "sim.vvp")
    try:
        compile_cmd = ["iverilog", "-g2012", "-o", vvp_path, RTL_FILE, TB_LEAK_CHECK_FILE]
        cp = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=60)
        if cp.returncode != 0:
            return None, "iverilog compile failed: {}".format(cp.stderr.strip()[:500])
        rp = subprocess.run(["vvp", vvp_path], capture_output=True, text=True, timeout=60)
        if rp.returncode != 0 and not rp.stdout:
            return None, "vvp run failed: {}".format(rp.stderr.strip()[:500])
        return rp.stdout, None
    except subprocess.TimeoutExpired:
        return None, "simulation timed out"
    except FileNotFoundError as e:
        return None, "toolchain not available: {}".format(e)
    except Exception as e:
        return None, "simulation error: {}".format(e)


def parse_sim_output(stdout):
    """Parse lines like:
    RESULT index=00 index7=0 cycles=1 data_out=1
    Returns list of dicts.
    """
    results_list = []
    pattern = re.compile(
        r'RESULT\s+index=([0-9A-Fa-f]+)\s+index7=([01])\s+cycles=(\d+)\s+data_out=(\d+)'
    )
    for line in stdout.splitlines():
        m = pattern.search(line)
        if m:
            results_list.append({
                "index": int(m.group(1), 16),
                "index7": int(m.group(2)),
                "cycles": int(m.group(3)),
                "data_out": int(m.group(4)),
            })
    return results_list


def main():
    if not check_required_inputs_exist():
        sys.exit(1)

    submission = load_submission()

    # Run ground-truth simulation regardless (used by SR2); if it fails we still
    # grade FR/SR structurally where possible but SR2 depends on it.
    stdout, sim_err = run_simulation()
    sim_results = parse_sim_output(stdout) if stdout else []

    if submission is None:
        sys.exit(1)

    # ---------- FR1 ----------
    mut = submission.get("module_under_test", None)
    if isinstance(mut, str) and mut.strip() == "scratchpad_lookup":
        record("FR1", True)
    else:
        record("FR1", False,
               "module_under_test missing or not equal to 'scratchpad_lookup' (got: {!r})".format(mut))

    # ---------- FR2 ----------
    fcc = submission.get("functional_correctness_confirmed", None)
    if isinstance(fcc, bool):
        record("FR2", True)
    else:
        record("FR2", False,
               "functional_correctness_confirmed missing or not boolean (got: {!r})".format(fcc))

    # ---------- FR3 ----------
    lm = submission.get("latency_measurements", None)
    fr3_ok = False
    fr3_reason = ""
    parsed_lm = {}
    if isinstance(lm, list) and len(lm) == 2:
        all_valid = True
        bits_seen = []
        for entry in lm:
            if not isinstance(entry, dict):
                all_valid = False
                fr3_reason = "entry is not an object: {!r}".format(entry)
                break
            bsbv = entry.get("bank_select_bit_value", None)
            olc = entry.get("observed_latency_cycles", None)
            if not isinstance(bsbv, int) or isinstance(bsbv, bool) or bsbv not in (0, 1):
                all_valid = False
                fr3_reason = "bank_select_bit_value invalid: {!r}".format(bsbv)
                break
            if not isinstance(olc, int) or isinstance(olc, bool):
                all_valid = False
                fr3_reason = "observed_latency_cycles not integer: {!r}".format(olc)
                break
            bits_seen.append(bsbv)
            parsed_lm[bsbv] = olc
        if all_valid:
            if sorted(bits_seen) == [0, 1]:
                fr3_ok = True
            else:
                fr3_reason = "must contain exactly one entry for bank_select_bit_value=0 and one for =1, got {}".format(bits_seen)
    else:
        fr3_reason = "latency_measurements missing or not an array of exactly 2 objects (got: {!r})".format(lm)

    if fr3_ok:
        record("FR3", True)
    else:
        record("FR3", False, fr3_reason)

    # ---------- FR4 ----------
    rfv = submission.get("report_format_version", None)
    if isinstance(rfv, str) and rfv.strip() == "1.0":
        record("FR4", True)
    else:
        record("FR4", False,
               "report_format_version missing or not equal to '1.0' (got: {!r})".format(rfv))

    # ---------- SR1 ----------
    leaking_bits = submission.get("leaking_index_bits", None)
    sr1_ok = False
    sr1_reason = ""

    def normalize_bit(v):
        # Accept ints, strings like "7", "index[7]", "bit 7"
        if isinstance(v, bool):
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            m = re.search(r'(\d+)', v)
            if m:
                return int(m.group(1))
        return None

    if isinstance(leaking_bits, list) and len(leaking_bits) > 0:
        normalized = [normalize_bit(x) for x in leaking_bits]
        normalized = [n for n in normalized if n is not None]
        if 7 in normalized:
            other_bits = [n for n in normalized if n != 7]
            # Fine to also list bit 7 alongside others as long as 7 present.
            sr1_ok = True
        else:
            sr1_reason = "leaking_index_bits does not include bit 7 (got: {!r})".format(leaking_bits)
    else:
        sr1_reason = "leaking_index_bits missing, empty, or not a list (got: {!r})".format(leaking_bits)

    if sr1_ok:
        record("SR1", True)
    else:
        record("SR1", False, sr1_reason)

    # ---------- SR2 ----------
    # Ground truth: index7=0 -> 1 cycle, index7=1 -> 3 cycles.
    expected_cycles = {0: 1, 1: 3}
    sr2_ok = False
    sr2_reason = ""

    if sim_err is not None and not sim_results:
        sr2_reason = "could not establish ground-truth timing via simulation: {}".format(sim_err)
    else:
        observed = {}
        for r in sim_results:
            b = r["index7"]
            c = r["cycles"]
            if b in observed and observed[b] != c:
                # inconsistent observations for same bit value; keep first but note
                continue
            observed.setdefault(b, c)

        sim_matches_spec = True
        for b in (0, 1):
            if b not in observed:
                sim_matches_spec = False
                break
            if observed[b] != expected_cycles[b]:
                sim_matches_spec = False
                break

        # Use simulation-derived ground truth if it matches spec/expected values;
        # otherwise fall back to the documented expected_cycles from the spec
        # (design_brief.md / testbench_timing.v contract) since the RTL under
        # test in inputs/ is the intentionally-leaking baseline reference DUT
        # used purely to derive ground truth, not the submission.
        ground_truth = observed if (observed and sim_matches_spec) else expected_cycles

        if not fr3_ok:
            sr2_reason = "cannot verify latency_measurements values because FR3 structural check failed"
        else:
            mismatches = []
            for b in (0, 1):
                gt = ground_truth.get(b)
                got = parsed_lm.get(b)
                if got != gt:
                    mismatches.append(
                        "bit={} expected_cycles={} submitted_cycles={}".format(b, gt, got)
                    )
            if not mismatches:
                sr2_ok = True
            else:
                sr2_reason = "latency mismatch: " + "; ".join(mismatches)

    if sr2_ok:
        record("SR2", True)
    else:
        record("SR2", False, sr2_reason)

    # ---------- SR3 ----------
    ldp = submission.get("latency_divergent_paths", None)
    sr3_ok = False
    sr3_reason = ""

    # Vulnerability in baseline RTL: FSM states/case construct controlling divergence
    # localparam S_FAST_WAIT / S_SLOW_WAIT1/2/3 and case (index[7])
    rtl_construct_keywords = [
        r's_fast_wait',
        r's_slow_wait1',
        r's_slow_wait2',
        r's_slow_wait3',
        r's_slow_wait',
        r'case\s*\(\s*index\s*\[\s*7\s*\]\s*\)',
        r'index\s*\[\s*7\s*\]',
        r'bank_sel',
        r'fast[_ ]?bank',
        r'slow[_ ]?bank',
    ]
    combined_pattern = re.compile("|".join(rtl_construct_keywords), re.IGNORECASE)

    if isinstance(ldp, list) and len(ldp) > 0 and all(isinstance(x, str) for x in ldp):
        joined = " ".join(ldp).strip()
        if len(joined) < 5:
            sr3_reason = "latency_divergent_paths entries are empty/too vague"
        elif combined_pattern.search(joined):
            sr3_ok = True
        else:
            sr3_reason = "latency_divergent_paths does not reference concrete RTL constructs (e.g. S_FAST_WAIT/S_SLOW_WAIT/case(index[7])/bank names); got: {!r}".format(ldp)
    else:
        sr3_reason = "latency_divergent_paths missing, empty, or not a list of strings (got: {!r})".format(ldp)

    if sr3_ok:
        record("SR3", True)
    else:
        record("SR3", False, sr3_reason)

    # ---------- SR4 ----------
    mitigation = submission.get("mitigation", None)
    sr4_ok = False
    sr4_reason = ""

    positive_keywords = [
        r'constant[\s\-]?time',
        r'constant[\s\-]?latency',
        r'equaliz',
        r'equalis',
        r'pad(?:ding)?',
        r'fixed[\s\-]?latency',
        r'same\s+number\s+of\s+cycles',
        r'uniform\s+latency',
        r'dummy\s+wait',
        r'index[\s\-]?independent',
    ]
    negative_keywords = [
        r'remove\s+(?:the\s+)?slow\s+bank',
        r'delete\s+(?:the\s+)?slow\s+bank',
        r'skip\s+(?:the\s+)?fast\s+lookup',
        r'change\s+the\s+data\s+value',
        r'alter\s+data_out\s+value',
        r'disable\s+(?:the\s+)?(?:fast|slow)\s+bank',
        r'drop\s+(?:the\s+)?(?:fast|slow)\s+bank',
        r'return\s+(?:incorrect|wrong)\s+data',
    ]
    pos_pattern = re.compile("|".join(positive_keywords), re.IGNORECASE)
    neg_pattern = re.compile("|".join(negative_keywords), re.IGNORECASE)

    if isinstance(mitigation, dict):
        strat = mitigation.get("strategy", "")
        desc = mitigation.get("description", "")
        if not isinstance(strat, str):
            strat = ""
        if not isinstance(desc, str):
            desc = ""
        combined = (strat + " " + desc).strip()
        if len(combined) < 5:
            sr4_reason = "mitigation.strategy/description missing or empty"
        elif neg_pattern.search(combined):
            sr4_reason = "mitigation appears to propose breaking functional correctness (e.g. disabling a bank or changing data values): {!r}".format(combined)
        elif pos_pattern.search(combined):
            sr4_ok = True
        else:
            sr4_reason = "mitigation does not describe a constant-latency/timing-equalization strategy: {!r}".format(combined)
    else:
        sr4_reason = "mitigation missing or not an object with 'strategy'/'description' fields (got: {!r})".format(mitigation)

    if sr4_ok:
        record("SR4", True)
    else:
        record("SR4", False, sr4_reason)

    all_passed = all(v[0] for v in results.values())
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()