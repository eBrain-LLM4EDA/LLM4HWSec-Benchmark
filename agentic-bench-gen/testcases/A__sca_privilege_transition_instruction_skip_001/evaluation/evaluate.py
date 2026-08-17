#!/usr/bin/env python3
"""
evaluate.py - Grading entry point for sca_privilege_transition_instruction_skip_001

Grades submission/vulnerability_report.json against the reference design
artifacts in inputs/ (mode_sequencer.v, fault_model.md, design_brief.md).
"""

import json
import os
import re
import subprocess
import sys
import tempfile

REQUIRED_INPUTS = ["mode_sequencer.v", "fault_model.md", "design_brief.md"]
INPUTS_DIR = "inputs"
SUBMISSION_PATH = os.path.join("submission", "vulnerability_report.json")

DEMOTION_SEQUENCE = ["IDLE", "CHECK", "DEMOTE", "SETTLE", "DONE"]
NON_VULNERABLE_STATES = {"IDLE", "CHECK", "SETTLE", "DONE"}
VULNERABLE_STATE = "DEMOTE"
FAULT_FREE_PRIV = "00"
EXPECTED_RESULTING_PRIVILEGE = "supervisor"

# State encodings from design_brief.md
STATE_CODES = {
    "IDLE": 0,
    "CHECK": 1,
    "DEMOTE": 2,
    "SETTLE": 3,
    "DONE": 4,
    "PCHECK": 5,
    "PROMOTE": 6,
    "PSETTLE": 7,
    "PDONE": 8,
}

results = []  # list of (req_id, passed(bool), message)


def record(req_id, passed, msg=""):
    if passed:
        print("[TEST] PASS: {}".format(req_id))
    else:
        print("[TEST] FAIL: {}: {}".format(req_id, msg))
    results.append((req_id, passed, msg))


def fail_setup(msg):
    print("[TEST] FAIL: SETUP: {}".format(msg))
    sys.exit(1)


def is_2bit_binary(s):
    return isinstance(s, str) and re.fullmatch(r"[01]{2}", s) is not None


def main():
    # --- Check required input artifacts exist ---
    for fname in REQUIRED_INPUTS:
        fpath = os.path.join(INPUTS_DIR, fname)
        if not os.path.isfile(fpath):
            fail_setup("{} not found".format(fpath))

    mode_sequencer_path = os.path.join(INPUTS_DIR, "mode_sequencer.v")
    tb_path = os.path.join("evaluation", "tb_skip.v")

    # --- Load submission ---
    if not os.path.isfile(SUBMISSION_PATH):
        fail_setup("{} not found".format(SUBMISSION_PATH))

    try:
        with open(SUBMISSION_PATH, "r") as f:
            report = json.load(f)
    except Exception as e:
        fail_setup("{} could not be parsed as JSON: {}".format(SUBMISSION_PATH, e))

    if not isinstance(report, dict):
        fail_setup("{} does not contain a JSON object".format(SUBMISSION_PATH))

    # =========================================================
    # FR1: transition_sequence present, array of strings, matches
    #      exact ordered demotion sequence from design_brief.md
    # =========================================================
    transition_sequence = report.get("transition_sequence", None)
    fr1_ok = True
    fr1_msg = ""
    if not isinstance(transition_sequence, list) or not all(
        isinstance(x, str) for x in transition_sequence
    ):
        fr1_ok = False
        fr1_msg = "'transition_sequence' missing or not an array of strings"
    elif transition_sequence != DEMOTION_SEQUENCE:
        fr1_ok = False
        fr1_msg = (
            "'transition_sequence' {} does not equal expected ordered sequence {}".format(
                transition_sequence, DEMOTION_SEQUENCE
            )
        )
    record("FR1", fr1_ok, fr1_msg)

    # =========================================================
    # FR2: fault_free_final_priv present, 2-bit binary string == '00'
    # =========================================================
    fault_free_final_priv = report.get("fault_free_final_priv", None)
    fr2_ok = True
    fr2_msg = ""
    if not is_2bit_binary(fault_free_final_priv):
        fr2_ok = False
        fr2_msg = "'fault_free_final_priv' missing or not a 2-bit binary string"
    elif fault_free_final_priv != FAULT_FREE_PRIV:
        fr2_ok = False
        fr2_msg = "'fault_free_final_priv' == '{}' but expected '{}'".format(
            fault_free_final_priv, FAULT_FREE_PRIV
        )
    record("FR2", fr2_ok, fr2_msg)

    # =========================================================
    # FR3: per_state_skip_impact INDEPENDENTLY validated:
    #      - must be a list
    #      - must contain an entry (well-formed 'state' + valid
    #        'priv_reg_after_skip') for every state in
    #        transition_sequence; fewer entries than
    #        transition_sequence's length (or missing coverage of
    #        any specific state) fails this check directly.
    #      - every present entry must have a syntactically valid
    #        2-bit binary priv_reg_after_skip value (^[01]{2}$),
    #        flagging malformed entries (e.g. '2', 'xx', '', non-str)
    #        independently of FR4.
    # =========================================================
    per_state_skip_impact = report.get("per_state_skip_impact", None)
    fr3_ok = True
    fr3_msg = ""
    entry_map = {}  # state -> priv_reg_after_skip (first occurrence, well-formed only)

    # Reference list of states we expect coverage for (fall back to the
    # canonical demotion sequence if transition_sequence itself is
    # malformed, so FR3 can still meaningfully evaluate coverage).
    if isinstance(transition_sequence, list) and all(
        isinstance(x, str) for x in transition_sequence
    ):
        expected_states = transition_sequence
    else:
        expected_states = DEMOTION_SEQUENCE

    if not isinstance(per_state_skip_impact, list):
        fr3_ok = False
        fr3_msg = "'per_state_skip_impact' missing or not an array"
    else:
        malformed_entries = []
        seen_states = set()
        for idx, entry in enumerate(per_state_skip_impact):
            if not isinstance(entry, dict):
                malformed_entries.append("index {}: not an object".format(idx))
                continue
            st = entry.get("state", None)
            val = entry.get("priv_reg_after_skip", None)
            if not isinstance(st, str) or not st:
                malformed_entries.append(
                    "index {}: missing/invalid 'state' string".format(idx)
                )
                continue
            if not is_2bit_binary(val):
                malformed_entries.append(
                    "index {} ('state'={}): 'priv_reg_after_skip'={!r} does not match "
                    "^[01]{{2}}$".format(idx, st, val)
                )
                continue
            seen_states.add(st)
            if st not in entry_map:
                entry_map[st] = val

        # Independent length/coverage check: every state in
        # expected_states must have a well-formed entry.
        missing_states = [s for s in expected_states if s not in seen_states]

        if len(per_state_skip_impact) < len(expected_states):
            fr3_ok = False
            fr3_msg = (
                "'per_state_skip_impact' has {} entries but transition_sequence "
                "has {} states (fewer entries than states)".format(
                    len(per_state_skip_impact), len(expected_states)
                )
            )
        elif malformed_entries:
            fr3_ok = False
            fr3_msg = "malformed entries in 'per_state_skip_impact': {}".format(
                "; ".join(malformed_entries[:5])
            )
        elif missing_states:
            fr3_ok = False
            fr3_msg = (
                "'per_state_skip_impact' does not cover all states in "
                "transition_sequence; missing well-formed entries for: {}".format(
                    missing_states
                )
            )

    record("FR3", fr3_ok, fr3_msg)

    # =========================================================
    # FR4: all required top-level fields present with correct types,
    #      and per_state_skip_impact contains one entry per state in
    #      transition_sequence.
    # =========================================================
    fr4_ok = True
    fr4_msgs = []

    required_fields = {
        "transition_sequence": list,
        "fault_free_final_priv": str,
        "per_state_skip_impact": list,
        "vulnerable_state": str,
        "resulting_privilege": str,
        "mitigation": str,
    }
    for field, ftype in required_fields.items():
        if field not in report:
            fr4_ok = False
            fr4_msgs.append("missing field '{}'".format(field))
        elif not isinstance(report[field], ftype):
            fr4_ok = False
            fr4_msgs.append(
                "field '{}' has wrong type (expected {})".format(field, ftype.__name__)
            )

    # Only check per-state coverage if the basic structures are sane
    if (
        isinstance(transition_sequence, list)
        and all(isinstance(x, str) for x in transition_sequence)
        and isinstance(per_state_skip_impact, list)
        and fr3_ok
    ):
        covered_states = set(entry_map.keys())
        missing_states = [s for s in transition_sequence if s not in covered_states]
        if missing_states:
            fr4_ok = False
            fr4_msgs.append(
                "'per_state_skip_impact' missing entries for states: {}".format(
                    missing_states
                )
            )
    else:
        # If FR1/FR3 already broken in a way that prevents coverage checking,
        # note it but don't double count if already flagged above.
        if not (isinstance(per_state_skip_impact, list) and fr3_ok):
            fr4_ok = False
            fr4_msgs.append(
                "'per_state_skip_impact' malformed; cannot verify per-state coverage"
            )

    record("FR4", fr4_ok, "; ".join(fr4_msgs))

    # =========================================================
    # SR1: vulnerable_state == 'DEMOTE' and resulting_privilege == 'supervisor'
    # =========================================================
    vulnerable_state = report.get("vulnerable_state", None)
    resulting_privilege = report.get("resulting_privilege", None)
    sr1_ok = True
    sr1_msg = ""
    if not isinstance(vulnerable_state, str) or vulnerable_state != VULNERABLE_STATE:
        sr1_ok = False
        sr1_msg = "'vulnerable_state' == {!r} but expected {!r}".format(
            vulnerable_state, VULNERABLE_STATE
        )
    elif (
        not isinstance(resulting_privilege, str)
        or resulting_privilege.strip().lower() != EXPECTED_RESULTING_PRIVILEGE
    ):
        sr1_ok = False
        sr1_msg = "'resulting_privilege' == {!r} but expected {!r}".format(
            resulting_privilege, EXPECTED_RESULTING_PRIVILEGE
        )
    record("SR1", sr1_ok, sr1_msg)

    # =========================================================
    # SR2: non-vulnerable states' priv_reg_after_skip must equal
    #      fault_free_final_priv (no false-positive fault claims)
    # =========================================================
    sr2_ok = True
    sr2_msgs = []
    if isinstance(per_state_skip_impact, list) and fr3_ok:
        baseline_priv = (
            fault_free_final_priv if is_2bit_binary(fault_free_final_priv) else FAULT_FREE_PRIV
        )
        for st, val in entry_map.items():
            if st in NON_VULNERABLE_STATES:
                if val != baseline_priv:
                    sr2_ok = False
                    sr2_msgs.append(
                        "non-vulnerable state '{}' reports priv_reg_after_skip='{}' "
                        "(expected '{}')".format(st, val, baseline_priv)
                    )
    else:
        sr2_ok = False
        sr2_msgs.append("'per_state_skip_impact' malformed; cannot verify false-positive rate")
    record("SR2", sr2_ok, "; ".join(sr2_msgs))

    # =========================================================
    # SR3: mitigation text must describe a genuine redundancy-based
    #      hardware countermeasure tied to the vulnerable write/state,
    #      not a vague/generic suggestion.
    # =========================================================
    mitigation = report.get("mitigation", None)
    sr3_ok = True
    sr3_msg = ""
    if not isinstance(mitigation, str) or not mitigation.strip():
        sr3_ok = False
        sr3_msg = "'mitigation' missing or empty"
    else:
        mtext = mitigation.lower()

        redundancy_keywords = [
            "duplicate",
            "duplicat",
            "triplicat",
            "tmr",
            "re-check",
            "recheck",
            "re-assert",
            "reassert",
            "comparator",
            "compare",
            "vote",
            "voting",
            "redundant write",
            "redundancy",
            "re-write",
            "rewrite",
            "double write",
            "second write",
            "check-and-correct",
            "check and correct",
        ]

        target_keywords = [
            "demote",
            "priv_reg",
            "privilege register",
            "priv reg",
            "settle",
            "demotion write",
            "the write",
        ]

        # Vague/generic phrases that should NOT count as sufficient mitigation
        vague_only_patterns = [
            r"\badd more testing\b",
            r"\buse encryption\b",
            r"\bcode review\b",
            r"\bimprove documentation\b",
            r"\bmore testing\b",
            r"\bbetter testing\b",
            r"\bsecurity audit\b",
        ]

        has_redundancy = any(kw in mtext for kw in redundancy_keywords)
        has_target = any(kw in mtext for kw in target_keywords)

        # If the text is dominated by vague patterns and lacks redundancy
        # keywords entirely, definitely reject.
        looks_vague_only = (
            any(re.search(pat, mtext) for pat in vague_only_patterns) and not has_redundancy
        )

        if not has_redundancy:
            sr3_ok = False
            sr3_msg = (
                "'mitigation' lacks a genuine redundancy mechanism keyword "
                "(duplicate/triplicate/re-check/comparator/re-assert/vote/redundant write)"
            )
        elif not has_target:
            sr3_ok = False
            sr3_msg = (
                "'mitigation' has redundancy language but does not reference the "
                "vulnerable write/state (DEMOTE / priv_reg / the demotion write)"
            )
        elif looks_vague_only:
            sr3_ok = False
            sr3_msg = "'mitigation' reads as a generic/vague suggestion, not a concrete redundancy mechanism"

    record("SR3", sr3_ok, sr3_msg)

    # =========================================================
    # SR4: cross-simulate via iverilog/vvp: force-skip the write at
    #      the reported vulnerable_state, compare simulated final
    #      priv_reg against reported resulting_privilege.
    # =========================================================
    sr4_ok = True
    sr4_msg = ""

    if not isinstance(vulnerable_state, str) or vulnerable_state not in STATE_CODES:
        sr4_ok = False
        sr4_msg = (
            "'vulnerable_state' ({!r}) is not a recognized state name; "
            "cannot cross-simulate".format(vulnerable_state)
        )
    elif not isinstance(resulting_privilege, str):
        sr4_ok = False
        sr4_msg = "'resulting_privilege' missing or not a string; cannot cross-simulate"
    elif not os.path.isfile(tb_path):
        fail_setup("{} not found".format(tb_path))
    else:
        skip_code = STATE_CODES[vulnerable_state]
        priv_map = {"10": "supervisor", "00": "user"}

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                sim_bin = os.path.join(tmpdir, "sim.vvp")

                compile_cmd = [
                    "iverilog",
                    "-g2012",
                    "-o",
                    sim_bin,
                    mode_sequencer_path,
                    tb_path,
                ]
                compile_proc = subprocess.run(
                    compile_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=60,
                )
                if compile_proc.returncode != 0:
                    sr4_ok = False
                    sr4_msg = "iverilog compile failed: {}".format(
                        compile_proc.stderr.decode(errors="replace")[:500]
                    )
                else:
                    run_cmd = ["vvp", sim_bin, "+SKIP={}".format(skip_code)]
                    run_proc = subprocess.run(
                        run_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=60,
                    )
                    out = run_proc.stdout.decode(errors="replace")

                    m = re.search(r"FINAL_PRIV=([01]{2})", out)
                    done_seen = "DONE_SEEN=1" in out

                    if run_proc.returncode != 0:
                        sr4_ok = False
                        sr4_msg = "simulation run crashed/timed out (returncode={})".format(
                            run_proc.returncode
                        )
                    elif not m or not done_seen:
                        sr4_ok = False
                        sr4_msg = (
                            "simulation output did not contain expected "
                            "FINAL_PRIV=<xx> / DONE_SEEN=1 markers; got: {}".format(out[-500:])
                        )
                    else:
                        simulated_priv_bits = m.group(1)
                        simulated_privilege = priv_map.get(
                            simulated_priv_bits, "unknown({})".format(simulated_priv_bits)
                        )
                        reported = resulting_privilege.strip().lower()
                        if simulated_privilege != reported:
                            sr4_ok = False
                            sr4_msg = (
                                "reported resulting_privilege={!r} does not match "
                                "simulated final priv_reg={} (-> {}) when skipping "
                                "state {!r}".format(
                                    resulting_privilege,
                                    simulated_priv_bits,
                                    simulated_privilege,
                                    vulnerable_state,
                                )
                            )
        except subprocess.TimeoutExpired:
            sr4_ok = False
            sr4_msg = "simulation run crashed/timed out"
        except FileNotFoundError as e:
            sr4_ok = False
            sr4_msg = "toolchain invocation failed (iverilog/vvp not available): {}".format(e)

    record("SR4", sr4_ok, sr4_msg)

    # =========================================================
    # Final verdict
    # =========================================================
    all_passed = all(passed for (_, passed, _) in results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()