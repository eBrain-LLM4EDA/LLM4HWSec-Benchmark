#!/usr/bin/env python3
"""
evaluate.py - Grader for sca_fault_spn_lastround_dfa_001

Grades submission/vulnerability_report.json against:
  - FR1-FR4: structural / format requirements
  - SR1-SR4: substantive correctness requirements (against hidden ground truth,
             with an independent DFA cross-check for SR3 derived purely from
             inputs/spn_core.v and inputs/trace_pairs.json).

Exits 0 iff every requirement PASSes; exits non-zero otherwise.
"""

import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUTS_DIR = os.path.join(REPO_ROOT, "inputs")
SUBMISSION_PATH = os.path.join(REPO_ROOT, "submission", "vulnerability_report.json")

# ---------------------------------------------------------------------------
# Hidden ground truth (pinned here; not disclosed in participant-facing docs)
# ---------------------------------------------------------------------------
GT_VULNERABLE_REGISTER = "state_q"
GT_VULNERABLE_CYCLE_OFFSET = 1
GT_AFFECTED_NIBBLE_INDEX = 0
GT_RECOVERED_SUBKEY_NIBBLE_INDEX = 0
GT_RECOVERED_SUBKEY_NIBBLE_VALUE = "9"

RESULTS = []  # list of (req_id, passed_bool, message)


def record(req_id, passed, message=""):
    if passed:
        print("[TEST] PASS: {}".format(req_id))
    else:
        print("[TEST] FAIL: {}: {}".format(req_id, message))
    RESULTS.append((req_id, passed, message))


def fail_setup(req_id, message):
    print("[TEST] FAIL: SETUP: {}".format(message))
    RESULTS.append((req_id, False, message))


# ---------------------------------------------------------------------------
# DFA reference logic (embedded; mirrors evaluation/dfa_reference.py contract)
# ---------------------------------------------------------------------------

def parse_sbox_from_verilog(text):
    """
    Regex-extract the 4-bit S-box mapping from Verilog source of the form:
        4'h0: sbox4 = 4'hE;
    Returns dict int->int (0..15 -> 0..15). Raises ValueError if incomplete.
    """
    pattern = re.compile(
        r"4'[hH]([0-9a-fA-F])\s*:\s*sbox4\s*=\s*4'[hH]([0-9a-fA-F])\s*;"
    )
    mapping = {}
    for m in pattern.finditer(text):
        inp = int(m.group(1), 16)
        outp = int(m.group(2), 16)
        mapping[inp] = outp
    if len(mapping) < 16:
        raise ValueError(
            "Could not parse full 16-entry S-box from spn_core.v (found {} entries)".format(
                len(mapping)
            )
        )
    return mapping


def invert_sbox(sbox):
    inv = {}
    for k, v in sbox.items():
        inv[v] = k
    if len(inv) != 16:
        raise ValueError("S-box is not a bijection; cannot invert")
    return inv


def load_traces(trace_json):
    """
    Extract list of (correct_ct, faulty_ct) 16-bit ints from the trace_pairs.json
    structure. Tolerant of the 'traces' key and hex-string values.
    """
    if isinstance(trace_json, dict) and "traces" in trace_json:
        raw = trace_json["traces"]
    elif isinstance(trace_json, list):
        raw = trace_json
    else:
        raise ValueError("Unrecognized trace_pairs.json structure")

    traces = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        cct = entry.get("correct_ciphertext")
        fct = entry.get("faulty_ciphertext")
        if cct is None or fct is None:
            continue
        cct_i = int(str(cct), 16) if isinstance(cct, str) else int(cct)
        fct_i = int(str(fct), 16) if isinstance(fct, str) else int(fct)
        traces.append((cct_i, fct_i))
    if not traces:
        raise ValueError("No usable trace pairs found in trace_pairs.json")
    return traces


def brute_force_nibble0(traces, sbox):
    """
    For each of the 16 candidate final_key nibble0 values k, test whether the
    hypothesis "the fault corrupted nibble0 of the pre-final-substitution state,
    with final_key nibble0 == k" is consistent across ALL trace pairs.

    Since ciphertext_nibble0 = sbox(state_nibble0) XOR final_key_nibble0, the
    final_key XOR cancels in the correct/faulty difference at the S-box OUTPUT
    level:
        sbox_out_correct = ciphertext_nibble0_correct XOR k
        sbox_out_faulty  = ciphertext_nibble0_faulty  XOR k
    Recovering the pre-substitution (state) values via the inverse S-box:
        state_correct = inv_sbox[sbox_out_correct]
        state_faulty  = inv_sbox[sbox_out_faulty]
    A candidate k is consistent with a trace iff:
        - state_correct != state_faulty (fault is nonzero, as guaranteed by
          the fault model).
    We eliminate a candidate k if it produces a zero pre-substitution
    difference on any trace (impossible under the stated nonzero-fault
    model) -- that is the falsifiable constraint available from ciphertext
    pairs alone under this fault model.

    Returns: (list of surviving candidate ints in range 0..15)
    """
    inv_sbox = invert_sbox(sbox)
    survivors = []
    for k in range(16):
        consistent = True
        for (cct, fct) in traces:
            ct_n0_correct = cct & 0xF
            ct_n0_faulty = fct & 0xF
            sbox_out_correct = ct_n0_correct ^ k
            sbox_out_faulty = ct_n0_faulty ^ k
            state_correct = inv_sbox[sbox_out_correct]
            state_faulty = inv_sbox[sbox_out_faulty]
            if state_correct == state_faulty:
                # This candidate implies a zero-difference fault on this trace,
                # contradicting the documented nonzero single-nibble fault model.
                consistent = False
                break
        if consistent:
            survivors.append(k)
    return survivors


# ---------------------------------------------------------------------------
# Load input artifacts
# ---------------------------------------------------------------------------

def load_input_file(filename):
    path = os.path.join(INPUTS_DIR, filename)
    if not os.path.isfile(path):
        return None, "{} not found".format(os.path.join("inputs", filename))
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read(), None
    except Exception as e:
        return None, "failed to read {}: {}".format(filename, e)


def main():
    all_req_ids = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]

    # ------------------------------------------------------------------
    # Load submission
    # ------------------------------------------------------------------
    if not os.path.isfile(SUBMISSION_PATH):
        for rid in all_req_ids:
            fail_setup(rid, "submission/vulnerability_report.json not found")
        sys.exit(1)

    try:
        with open(SUBMISSION_PATH, "r", encoding="utf-8") as f:
            raw_text = f.read()
    except Exception as e:
        for rid in all_req_ids:
            fail_setup(rid, "failed to read submission/vulnerability_report.json: {}".format(e))
        sys.exit(1)

    try:
        report = json.loads(raw_text)
    except Exception as e:
        for rid in all_req_ids:
            fail_setup(rid, "submission/vulnerability_report.json is not valid JSON: {}".format(e))
        sys.exit(1)

    if not isinstance(report, dict):
        for rid in all_req_ids:
            fail_setup(rid, "submission/vulnerability_report.json top level is not a JSON object")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Load reference input artifacts (needed for SR2/SR3 cross-checks)
    # ------------------------------------------------------------------
    spn_core_text, err_core = load_input_file("spn_core.v")
    if err_core:
        fail_setup("SETUP_SPN_CORE", err_core)
    trace_text, err_trace = load_input_file("trace_pairs.json")
    if err_trace:
        fail_setup("SETUP_TRACE_PAIRS", err_trace)

    # These are also part of the public artifact set; presence isn't strictly
    # required for grading but we validate they exist per the file contract.
    _, err_top = load_input_file("spn_top.v")
    if err_top:
        fail_setup("SETUP_SPN_TOP", err_top)
    _, err_fm = load_input_file("fault_model.md")
    if err_fm:
        fail_setup("SETUP_FAULT_MODEL", err_fm)
    _, err_db = load_input_file("design_brief.md")
    if err_db:
        fail_setup("SETUP_DESIGN_BRIEF", err_db)

    if err_core or err_trace:
        # Cannot proceed with DFA cross-check; still evaluate FR checks below,
        # but SR2/SR3 depend on these artifacts.
        pass

    # ==================================================================
    # FR1: all 7 required fields present with correct types
    # ==================================================================
    required_fields = {
        "vulnerable_register": str,
        "vulnerable_cycle_offset": int,
        "affected_nibble_index": int,
        "recovered_subkey_nibble_index": int,
        "recovered_subkey_nibble_value": str,
        "analysis_method": str,
        "hardening_recommendations": list,
    }

    fr1_missing = []
    fr1_wrong_type = []
    for field, expected_type in required_fields.items():
        if field not in report:
            fr1_missing.append(field)
        else:
            val = report[field]
            # bool is a subclass of int in Python; reject bools for int fields
            if expected_type is int:
                if isinstance(val, bool) or not isinstance(val, int):
                    fr1_wrong_type.append(field)
            elif expected_type is str:
                if not isinstance(val, str):
                    fr1_wrong_type.append(field)
            elif expected_type is list:
                if not isinstance(val, list):
                    fr1_wrong_type.append(field)

    if fr1_missing or fr1_wrong_type:
        reasons = []
        if fr1_missing:
            reasons.append("missing fields: {}".format(", ".join(fr1_missing)))
        if fr1_wrong_type:
            reasons.append("wrong type fields: {}".format(", ".join(fr1_wrong_type)))
        record("FR1", False, "; ".join(reasons))
    else:
        record("FR1", True)

    fr1_ok = not (fr1_missing or fr1_wrong_type)

    # ==================================================================
    # FR2: affected_nibble_index and recovered_subkey_nibble_index in [0,3]
    # ==================================================================
    if not fr1_ok or "affected_nibble_index" not in report or "recovered_subkey_nibble_index" not in report:
        record("FR2", False, "required integer fields missing/malformed (see FR1)")
    else:
        ani = report.get("affected_nibble_index")
        rsni = report.get("recovered_subkey_nibble_index")
        ani_ok = isinstance(ani, int) and not isinstance(ani, bool) and 0 <= ani <= 3
        rsni_ok = isinstance(rsni, int) and not isinstance(rsni, bool) and 0 <= rsni <= 3
        if ani_ok and rsni_ok:
            record("FR2", True)
        else:
            reasons = []
            if not ani_ok:
                reasons.append("affected_nibble_index={!r} not int in 0-3".format(ani))
            if not rsni_ok:
                reasons.append("recovered_subkey_nibble_index={!r} not int in 0-3".format(rsni))
            record("FR2", False, "; ".join(reasons))

    # ==================================================================
    # FR3: recovered_subkey_nibble_value is exactly one hex char
    # ==================================================================
    if not fr1_ok or "recovered_subkey_nibble_value" not in report:
        record("FR3", False, "recovered_subkey_nibble_value missing/malformed (see FR1)")
    else:
        rsnv = report.get("recovered_subkey_nibble_value")
        if isinstance(rsnv, str) and re.fullmatch(r"[0-9a-fA-F]", rsnv):
            record("FR3", True)
        else:
            record("FR3", False, "recovered_subkey_nibble_value={!r} is not exactly one hex digit".format(rsnv))

    # ==================================================================
    # FR4: hardening_recommendations >=2 distinct non-empty strings >=10 chars,
    #      analysis_method >=20 chars
    # ==================================================================
    if not fr1_ok:
        record("FR4", False, "required fields missing/malformed (see FR1)")
    else:
        hr = report.get("hardening_recommendations")
        am = report.get("analysis_method")
        problems = []

        valid_entries = []
        if isinstance(hr, list):
            for entry in hr:
                if isinstance(entry, str) and len(entry.strip()) >= 10:
                    valid_entries.append(entry.strip())
        distinct_valid = set(valid_entries)

        if len(distinct_valid) < 2:
            problems.append(
                "hardening_recommendations has fewer than 2 distinct non-empty strings >=10 chars (found {})".format(
                    len(distinct_valid)
                )
            )

        if not isinstance(am, str) or len(am.strip()) < 20:
            problems.append("analysis_method is missing or shorter than 20 characters")

        if problems:
            record("FR4", False, "; ".join(problems))
        else:
            record("FR4", True)

    # ==================================================================
    # SR1: vulnerable_register == 'state_q' (case-sensitive, exact)
    # ==================================================================
    if not fr1_ok or "vulnerable_register" not in report:
        record("SR1", False, "vulnerable_register missing/malformed (see FR1)")
    else:
        vr = report.get("vulnerable_register")
        if isinstance(vr, str) and vr == GT_VULNERABLE_REGISTER:
            record("SR1", True)
        else:
            record("SR1", False, "vulnerable_register={!r} does not match ground truth '{}'".format(
                vr, GT_VULNERABLE_REGISTER))

    # ==================================================================
    # SR2: vulnerable_cycle_offset == 1 AND affected_nibble_index == 0
    # ==================================================================
    if not fr1_ok:
        record("SR2", False, "required fields missing/malformed (see FR1)")
    else:
        vco = report.get("vulnerable_cycle_offset")
        ani2 = report.get("affected_nibble_index")
        vco_ok = isinstance(vco, int) and not isinstance(vco, bool) and vco == GT_VULNERABLE_CYCLE_OFFSET
        ani_ok2 = isinstance(ani2, int) and not isinstance(ani2, bool) and ani2 == GT_AFFECTED_NIBBLE_INDEX
        if vco_ok and ani_ok2:
            record("SR2", True)
        else:
            reasons = []
            if not vco_ok:
                reasons.append("vulnerable_cycle_offset={!r} != {}".format(vco, GT_VULNERABLE_CYCLE_OFFSET))
            if not ani_ok2:
                reasons.append("affected_nibble_index={!r} != {}".format(ani2, GT_AFFECTED_NIBBLE_INDEX))
            record("SR2", False, "; ".join(reasons))

    # ==================================================================
    # SR3: independent DFA cross-check of recovered subkey nibble
    # ==================================================================
    if not fr1_ok:
        record("SR3", False, "required fields missing/malformed (see FR1)")
    elif err_core or err_trace:
        record("SR3", False, "could not load reference artifacts for DFA cross-check: {}".format(
            err_core or err_trace))
    else:
        try:
            sbox = parse_sbox_from_verilog(spn_core_text)
            trace_json = json.loads(trace_text)
            traces = load_traces(trace_json)
            survivors = brute_force_nibble0(traces, sbox)
        except Exception as e:
            record("SR3", False, "independent DFA cross-check failed to run: {}".format(e))
            survivors = None

        if survivors is not None:
            rsni3 = report.get("recovered_subkey_nibble_index")
            rsnv3 = report.get("recovered_subkey_nibble_value")

            index_ok = isinstance(rsni3, int) and not isinstance(rsni3, bool) and rsni3 == GT_RECOVERED_SUBKEY_NIBBLE_INDEX

            value_ok = False
            submitted_val_int = None
            if isinstance(rsnv3, str) and re.fullmatch(r"[0-9a-fA-F]", rsnv3):
                submitted_val_int = int(rsnv3, 16)

            unique_survivor = len(survivors) == 1
            survivor_matches_gt = unique_survivor and survivors[0] == int(GT_RECOVERED_SUBKEY_NIBBLE_VALUE, 16)

            if submitted_val_int is not None and unique_survivor:
                value_ok = submitted_val_int == survivors[0]

            if index_ok and value_ok and survivor_matches_gt:
                record("SR3", True)
            else:
                reasons = []
                if not unique_survivor:
                    reasons.append("independent brute force did not yield a unique survivor: {}".format(survivors))
                elif not survivor_matches_gt:
                    reasons.append("independent brute force survivor {:x} does not match expected ground truth".format(
                        survivors[0]))
                if not index_ok:
                    reasons.append("recovered_subkey_nibble_index={!r} != {}".format(
                        rsni3, GT_RECOVERED_SUBKEY_NIBBLE_INDEX))
                if not value_ok:
                    reasons.append("recovered_subkey_nibble_value={!r} does not match independently-derived survivor {}".format(
                        rsnv3, survivors))
                record("SR3", False, "; ".join(reasons))

    # ==================================================================
    # SR4: >=2 hardening recommendations reference concrete fault-hardening
    #      techniques applicable to a register (not generic crypto advice)
    # ==================================================================
    if not fr1_ok:
        record("SR4", False, "hardening_recommendations missing/malformed (see FR1)")
    else:
        hr4 = report.get("hardening_recommendations")
        if not isinstance(hr4, list):
            record("SR4", False, "hardening_recommendations is not a list")
        else:
            # Keyword/semantic patterns for concrete register-level fault-hardening
            # techniques, per SR4 detection_strategy.
            concrete_patterns = [
                r"\btmr\b",
                r"triple\s+modular\s+redundanc\w*",
                r"redundan\w*",
                r"duplicate[-\s]?and[-\s]?compare",
                r"\bparity\b",
                r"\becc\b",
                r"error[-\s]?(detect|correct)\w*\s*cod\w*",
                r"glitch\s*detect\w*",
                r"sensor[-\s]?based",
                r"random\w*\s*(delay|timing)",
                r"temporal\s+redundanc\w*",
                r"spatial\s+redundanc\w*",
                r"checksum",
                r"hash[-\s]?based\s+integrity",
                r"lock[-\s]?step",
                r"dual[-\s]?rail",
                r"voltage\s+(sensor|monitor)",
                r"clock\s+(glitch\s+)?(sensor|monitor|detect\w*)",
                r"re[-\s]?compute\w*\s+and\s+compare",
                r"masking\s+regist\w*",
            ]
            generic_irrelevant_patterns = [
                r"stronger\s+cipher",
                r"increase\s+key\s+length",
                r"longer\s+key",
                r"use\s+aes",
                r"use\s+a\s+different\s+algorithm",
            ]

            qualifying = []
            for entry in hr4:
                if not isinstance(entry, str) or len(entry.strip()) < 10:
                    continue
                lower = entry.lower()
                is_generic = any(re.search(p, lower) for p in generic_irrelevant_patterns)
                is_concrete = any(re.search(p, lower) for p in concrete_patterns)
                if is_concrete and not is_generic:
                    qualifying.append(entry.strip())

            distinct_qualifying = set(qualifying)
            if len(distinct_qualifying) >= 2:
                record("SR4", True)
            else:
                record("SR4", False,
                       "fewer than 2 distinct hardening_recommendations entries reference concrete "
                       "register-level fault-hardening techniques (found {})".format(len(distinct_qualifying)))

    # ------------------------------------------------------------------
    # Final verdict
    # ------------------------------------------------------------------
    all_passed = all(passed for (_, passed, _) in RESULTS)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()