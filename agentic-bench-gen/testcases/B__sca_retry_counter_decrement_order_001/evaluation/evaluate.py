#!/usr/bin/env python3
"""
evaluate.py -- grades submission/vulnerability_report.json against the
hidden ground truth for the pin_check_fsm decrement-after-check flaw.

This script grades an ANSWER FILE, not code. It reads inputs/ artifacts
only for reference/corroboration (optional simulation); the PASS/FAIL
verdicts are computed from the content of submission/vulnerability_report.json.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

RESULTS = []


def record(req_id, passed, reason=""):
    if passed:
        print(f"[TEST] PASS: {req_id}")
    else:
        print(f"[TEST] FAIL: {req_id}: {reason}")
    RESULTS.append(passed)


def read_file(path):
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def main():
    inputs_dir = "inputs"
    submission_path = os.path.join("submission", "vulnerability_report.json")

    # --- Load required input artifacts (SETUP checks) ---
    required_inputs = [
        "pin_check_fsm.v",
        "fault_model.md",
        "testbench_reference.v",
        "design_brief.md",
    ]
    input_texts = {}
    for fname in required_inputs:
        fpath = os.path.join(inputs_dir, fname)
        text = read_file(fpath)
        if text is None:
            # Every requirement fails with SETUP since we cannot proceed
            # meaningfully without the RTL reference.
            for rid in ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]:
                record(rid, False, f"SETUP: {fpath} not found")
            sys.exit(1)
        input_texts[fname] = text

    rtl_text = input_texts["pin_check_fsm.v"]

    # --- Load submission ---
    if not os.path.isfile(submission_path):
        for rid in ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]:
            record(rid, False, f"SETUP: {submission_path} not found")
        sys.exit(1)

    raw = read_file(submission_path)
    try:
        report = json.loads(raw)
    except Exception as e:
        for rid in ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]:
            record(rid, False, f"submission is not valid JSON: {e}")
        sys.exit(1)

    if not isinstance(report, dict):
        for rid in ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]:
            record(rid, False, "submission JSON top-level is not an object")
        sys.exit(1)

    # --- Extract state names from RTL (grounding for FR3) ---
    # Matches lines like: localparam [1:0] COMPARE = 2'd1;
    state_names = set(
        re.findall(r"localparam\s*(?:\[[^\]]*\]\s*)?(\w+)\s*=", rtl_text)
    )
    # Filter out non-state localparams like SECRET_PIN by intersecting with
    # the expected canonical set as a sanity net, but keep union so any
    # legitimately-added state name in a variant RTL would still work.
    expected_states = {"IDLE", "COMPARE", "CHECK_DONE", "LOCKOUT"}
    valid_state_names = state_names if state_names else expected_states

    # =========================================================
    # FR1: required string/array fields
    # =========================================================
    def fr1_check():
        missing = []
        for field in ["vulnerable_transition", "glitch_window", "remediation"]:
            if field not in report or not isinstance(report[field], str) or not report[field].strip():
                missing.append(field)
        if "affected_signals" not in report or not isinstance(report["affected_signals"], list) \
           or not all(isinstance(x, str) for x in report["affected_signals"]):
            missing.append("affected_signals")
        if missing:
            return False, f"missing or malformed field(s): {', '.join(missing)}"

        signals = [s.lower() for s in report["affected_signals"]]
        has_counter = any(
            ("attempt" in s) or ("retry" in s) or ("counter" in s) for s in signals
        )
        has_auth_or_lock = any(
            ("auth_ok" in s) or ("locked_out" in s) or ("lockout" in s) for s in signals
        )
        if not has_counter:
            return False, "affected_signals does not name a retry-counter-like signal (e.g. attempts_left)"
        if not has_auth_or_lock:
            return False, "affected_signals does not name auth_ok/locked_out"
        return True, ""

    ok, reason = fr1_check()
    record("FR1", ok, reason)

    # =========================================================
    # FR2: fault_free_behavior_preserved (bool) + justification (str)
    # =========================================================
    def fr2_check():
        if "fault_free_behavior_preserved" not in report or not isinstance(
            report["fault_free_behavior_preserved"], bool
        ):
            return False, "fault_free_behavior_preserved missing or not boolean"
        just = report.get("fault_free_justification")
        if not isinstance(just, str) or len(just.strip()) < 10:
            return False, "fault_free_justification missing or too short/not a string"
        return True, ""

    ok, reason = fr2_check()
    record("FR2", ok, reason)

    # =========================================================
    # FR3: state_names_referenced subset of RTL localparams
    # =========================================================
    def fr3_check():
        names = report.get("state_names_referenced")
        if not isinstance(names, list) or not all(isinstance(x, str) for x in names) or len(names) == 0:
            return False, "state_names_referenced missing, not a non-empty array of strings"
        for n in names:
            if n not in valid_state_names:
                return False, f"state name '{n}' does not literally appear as a localparam in pin_check_fsm.v"
        return True, ""

    ok, reason = fr3_check()
    record("FR3", ok, reason)

    # =========================================================
    # FR4: confidence in [0,1], method in allowed set
    # =========================================================
    def fr4_check():
        conf = report.get("confidence")
        if not isinstance(conf, (int, float)) or isinstance(conf, bool):
            return False, "confidence missing or not a number"
        if not (0 <= conf <= 1):
            return False, "confidence out of range [0,1]"
        method = report.get("method")
        if not isinstance(method, str) or method not in ("static_analysis", "simulation", "both"):
            return False, "method missing or not one of static_analysis/simulation/both"
        return True, ""

    ok, reason = fr4_check()
    record("FR4", ok, reason)

    # =========================================================
    # SR1: vulnerable_transition names COMPARE and CHECK_DONE, correct direction
    # =========================================================
    def sr1_check():
        vt = report.get("vulnerable_transition")
        if not isinstance(vt, str) or not vt.strip():
            return False, "vulnerable_transition missing"
        vt_norm = vt.upper()
        has_compare = "COMPARE" in vt_norm
        has_check_done = "CHECK_DONE" in vt_norm or "CHECKDONE" in vt_norm
        if not (has_compare and has_check_done):
            return False, "vulnerable_transition does not name both COMPARE and CHECK_DONE"

        # Reject wrong-direction or wrong-transition claims.
        # Wrong transitions: CHECK_DONE->LOCKOUT, IDLE->COMPARE (without CHECK_DONE),
        # or explicit reversed direction CHECK_DONE->COMPARE without any "into"/"entering" phrasing.
        if "LOCKOUT" in vt_norm and "CHECK_DONE" in vt_norm:
            # e.g. "CHECK_DONE->LOCKOUT" phrased explicitly as the vulnerable edge
            # Only reject if COMPARE is not clearly the source alongside CHECK_DONE as dest.
            # Look for an explicit arrow/direction pattern.
            m = re.search(r"CHECK_DONE\s*(?:->|-->|to)\s*LOCKOUT", vt_norm)
            if m and not re.search(r"COMPARE\s*(?:->|-->|to)\s*CHECK_DONE", vt_norm):
                return False, "vulnerable_transition incorrectly names CHECK_DONE->LOCKOUT instead of COMPARE->CHECK_DONE"

        # Detect explicit reversed direction: CHECK_DONE -> COMPARE (without also mentioning
        # correct direction phrase like "into CHECK_DONE from COMPARE" or "entering CHECK_DONE").
        reversed_match = re.search(r"CHECK_DONE\s*(?:->|-->|to)\s*COMPARE", vt_norm)
        forward_match = re.search(r"COMPARE\s*(?:->|-->|to)\s*CHECK_DONE", vt_norm)
        entering_phrase = ("INTO CHECK_DONE" in vt_norm) or ("ENTERING CHECK_DONE" in vt_norm) or \
                           ("ENTRY TO CHECK_DONE" in vt_norm) or ("TRANSITION TO CHECK_DONE" in vt_norm) or \
                           ("TRANSITION INTO CHECK_DONE" in vt_norm)

        if reversed_match and not forward_match and not entering_phrase:
            return False, "vulnerable_transition appears reversed (CHECK_DONE->COMPARE) without correct directionality"

        # Must have some positive indication of correct direction: either explicit forward arrow,
        # or an "into/entering CHECK_DONE ... from COMPARE" style phrase, or just both names present
        # without an explicit reversed arrow (loosely accept generic co-mention).
        if forward_match or entering_phrase:
            return True, ""
        if not reversed_match:
            # Both names mentioned, no explicit arrow contradicting the correct direction.
            return True, ""
        return False, "vulnerable_transition direction unclear or incorrect"

    ok, reason = sr1_check()
    record("SR1", ok, reason)

    # =========================================================
    # SR2: glitch_window correctly scoped to COMPARE->CHECK_DONE edge
    # =========================================================
    def sr2_check():
        gw = report.get("glitch_window")
        if not isinstance(gw, str) or not gw.strip():
            return False, "glitch_window missing"
        gw_norm = gw.upper()

        has_compare = "COMPARE" in gw_norm
        has_check_done = "CHECK_DONE" in gw_norm or "CHECKDONE" in gw_norm
        if not (has_compare and has_check_done):
            return False, "glitch_window does not reference the COMPARE/CHECK_DONE edge"

        timing_keywords = [
            "AFTER COMPARISON", "AFTER THE COMPARISON", "BEFORE DECREMENT", "BEFORE THE DECREMENT",
            "ENTERING CHECK_DONE", "ENTRY TO CHECK_DONE", "EDGE", "TRANSITION", "CYCLE AFTER",
            "CYCLE FOLLOWING", "POST-COMPARISON", "POST COMPARISON",
        ]
        if not any(k in gw_norm for k in timing_keywords):
            return False, "glitch_window lacks timing language tying it to the comparison-to-decrement edge"

        # Reject overly broad / wrong-location claims.
        vague_patterns = ["ANY TIME", "ANY CYCLE", "AT ANY POINT", "WHENEVER"]
        if any(v in gw_norm for v in vague_patterns):
            return False, "glitch_window is vague/overly broad ('any time'-style claim)"

        # Reject if it names IDLE or LOCKOUT as the primary landing point instead of the
        # COMPARE/CHECK_DONE edge (allow incidental mention, but not as the sole location).
        if ("IDLE" in gw_norm or "LOCKOUT" in gw_norm) and not has_compare:
            return False, "glitch_window names IDLE/LOCKOUT instead of the COMPARE->CHECK_DONE edge"

        return True, ""

    ok, reason = sr2_check()
    record("SR2", ok, reason)

    # =========================================================
    # SR3: remediation must affirmatively describe BOTH
    #      (a) early/speculative decrement-on-entry-to-COMPARE (or atomic
    #          merge of decrement+compare), AND
    #      (b) an explicit restore/increment-on-success mechanism tied to a
    #          successful match outcome.
    #      Explicit negation of restoration must FAIL even if (a) is present.
    # =========================================================
    def sr3_check():
        rem = report.get("remediation")
        if not isinstance(rem, str) or not rem.strip():
            return False, "remediation missing"
        rem_norm = rem.upper()

        entry_decrement_phrases = [
            "DECREMENT ON ENTRY TO COMPARE", "DECREMENT ON ENTRY", "DECREMENT AT COMPARE ENTRY",
            "DECREMENT WHEN ENTERING COMPARE", "DECREMENT AS SOON AS", "SPECULATIVELY DECREMENT",
            "DECREMENT UPON ENTERING COMPARE", "DECREMENT IN COMPARE", "MOVE THE DECREMENT TO COMPARE",
            "MOVE DECREMENT TO COMPARE",
        ]
        restore_phrases = [
            "RESTORE", "INCREMENT BACK", "INCREMENT ON MATCH", "INCREMENT ON SUCCESS",
            "RESTORE ON SUCCESS", "RESTORE ON MATCH", "UNDO THE DECREMENT", "ROLL BACK",
            "INCREMENT IT BACK", "INCREMENT THE COUNTER BACK", "CANCEL THE DECREMENT",
            "COMPENSATING INCREMENT", "OFFSETTING INCREMENT", "REVERT THE DECREMENT",
        ]
        atomic_phrases = [
            "ATOMIC", "SAME STATE", "SINGLE STATE", "COMBINE", "MERGE COMPARE AND CHECK_DONE",
            "MERGE THE COMPARE AND CHECK_DONE", "ONE STATE", "SINGLE CYCLE", "SINGLE CLOCK EDGE",
        ]
        # Explicit negation phrases: the text itself states no restoration happens.
        negation_phrases = [
            "NO RESTORATION", "NO RESTORE", "WITHOUT RESTORING", "WITHOUT RESTORATION",
            "DOES NOT RESTORE", "DOESN'T RESTORE", "DOES NOT INCREMENT BACK", "DOESN'T INCREMENT BACK",
            "NO CANCELLATION", "WITHOUT CANCELLING", "WITHOUT CANCELING", "NOT RESTORED",
            "IS NOT RESTORED", "NO COMPENSATING", "NO OFFSETTING", "NEVER RESTORED",
            "PERMANENTLY LOSES", "PERMANENTLY LOST", "NO INCREMENT BACK",
        ]

        has_entry_decrement = any(p in rem_norm for p in entry_decrement_phrases)
        has_restore = any(p in rem_norm for p in restore_phrases)
        has_atomic = any(p in rem_norm for p in atomic_phrases)
        has_negation = any(p in rem_norm for p in negation_phrases)

        if has_negation:
            return False, "remediation explicitly negates/omits restoration-on-success semantics"

        # Accept: (decrement-at-entry AND restore-on-success), OR a clearly stated
        # atomic/merged decrement+compare fix that also does not need a separate
        # restore (a genuinely single, atomic net-decrement-per-outcome mechanism)
        # but still must not explicitly negate restoration if it separately claims
        # a speculative/early decrement style.
        if has_entry_decrement and has_restore:
            return True, ""

        if has_atomic and ("DECREMENT" in rem_norm) and ("COMPARE" in rem_norm):
            # An atomic merge (single state doing compare+decrement) inherently
            # produces exactly one net decrement per outcome without requiring
            # separate restore language, provided it isn't itself describing an
            # early-decrement-without-restore scheme (already rejected via
            # has_negation above, and via the entry_decrement-without-restore
            # rejection below).
            if has_entry_decrement and not has_restore:
                return False, "remediation describes early/speculative decrement without restore-on-success"
            return True, ""

        # Also accept phrasing like "decrement attempts_left in the COMPARE state before/while
        # comparing, and increment it back if the PIN matches"
        if ("COMPARE" in rem_norm) and ("DECREMENT" in rem_norm) and has_restore:
            return True, ""

        # If it describes the early-decrement mechanism but never mentions restore at all,
        # that is the SR3 mutant case explicitly called out in repair notes: FAIL.
        if has_entry_decrement and not has_restore:
            return False, "remediation describes decrement-on-entry-to-COMPARE but omits restore-on-success semantics, leaving successful authentications permanently penalized"

        # Reject vague/incorrect fixes.
        vague_fixes = ["WATCHDOG", "ADD PARITY", "REDUNDANT LOGIC", "ADD REDUNDANCY", "TRIPLE MODULAR"]
        if any(v in rem_norm for v in vague_fixes) and not (has_entry_decrement or has_atomic):
            return False, "remediation proposes vague/generic fix without addressing decrement ordering"

        return False, "remediation does not describe decrement-on-entry-to-COMPARE with restore-on-success or an equivalent atomic fix"

    ok, reason = sr3_check()
    record("SR3", ok, reason)

    # =========================================================
    # SR4: the remediation's OWN described decrement/restore arithmetic and
    #      the justification's claimed attempt count must be strictly
    #      consistent with the documented 3-consecutive-fault-free-failure
    #      lockout. This is judged against the remediation text's own
    #      described mechanism and the justification's numeric claims, not
    #      just surface keyword presence.
    # =========================================================
    def sr4_check():
        preserved = report.get("fault_free_behavior_preserved")
        just = report.get("fault_free_justification")
        rem = report.get("remediation")

        if not isinstance(preserved, bool):
            return False, "fault_free_behavior_preserved missing or not boolean"
        if not isinstance(just, str) or not just.strip():
            return False, "fault_free_justification missing"
        if not isinstance(rem, str) or not rem.strip():
            return False, "remediation missing (needed to check arithmetic consistency)"

        just_norm = just.upper()
        rem_norm = rem.upper()
        combined_norm = just_norm + " " + rem_norm

        if preserved is not True:
            return False, "fault_free_behavior_preserved must be true for a correct remediation"

        # --- (1) Reject restore-on-FAILURE / increment-on-failure schemes. ---
        # These are inverted relative to the correct restore-on-success semantics:
        # if the counter is restored when a comparison FAILS (rather than when it
        # succeeds), then either the decrement is fully cancelled on every failure
        # (net 0 decrements per failed attempt -> lockout never triggers), or the
        # scheme is otherwise inverted from the documented policy.
        restore_on_failure_patterns = [
            r"RESTORE\s+ON\s+FAIL", r"RESTORE\s+ON\s+A\s+FAIL", r"RESTORE\s+ON\s+MISMATCH",
            r"RESTORE\s+ON\s+A\s+MISMATCH", r"RESTORE\s+ON\s+FAILED", r"RESTORE\s+IF\s+(?:THE\s+)?(?:MATCH\s+)?FAIL",
            r"RESTORE\s+IF\s+(?:THE\s+)?(?:COMPARISON\s+)?(?:FAILS|MISMATCHES)",
            r"INCREMENT\s+(?:IT\s+)?(?:BACK\s+)?ON\s+FAIL", r"INCREMENT\s+ON\s+A\s+FAILED",
            r"INCREMENT\s+ON\s+MISMATCH", r"INCREMENT\s+ON\s+FAILURE",
            r"RESTORE(?:D)?\s+WHEN\s+(?:THE\s+)?(?:MATCH\s+)?FAILS",
            r"RESTORE(?:D)?\s+WHEN\s+(?:THE\s+)?PIN\s+(?:IS\s+)?(?:WRONG|INCORRECT)",
            r"RESTORE\s+ON\s+A\s+FAILED\s+MATCH", r"RESTORE\s+ON\s+INCORRECT",
        ]
        for pat in restore_on_failure_patterns:
            if re.search(pat, combined_norm):
                return False, ("remediation/justification describes restoring or incrementing the "
                                "counter on a FAILED/mismatched attempt rather than on a successful "
                                "match; this inverts the intended semantics and does not preserve "
                                "the documented 3-attempt fault-free lockout")

        # --- (2) Numeric attempt-count consistency: any digit/word other than 3/three
        # appearing near lockout/attempt language in the justification is rejected. ---
        number_words = {
            "0": "ZERO", "1": "ONE", "2": "TWO", "4": "FOUR", "5": "FIVE",
            "6": "SIX", "7": "SEVEN", "8": "EIGHT", "9": "NINE", "10": "TEN",
        }
        lockout_context_pattern = re.compile(
            r"(?:LOCK(?:S|ED)?\s*OUT|ATTEMPTS?|TRIES|TRY|GUESSES?|FAILURES?|FAILED\s+ATTEMPTS?)"
        )
        # Scan sentences/segments for lockout-context mentions with a nearby non-3 number.
        off_count_found = None
        # digit-based: e.g. "locks out after 2 attempts", "4 attempts", "after 5 failures"
        digit_near_pattern = re.compile(
            r"\b([0-9]{1,2})\b\s*(?:CONSECUTIVE\s+)?(?:FAILED\s+)?(?:ATTEMPTS?|TRIES|TRY|GUESSES?|FAILURES?)"
        )
        for m in digit_near_pattern.finditer(just_norm):
            num = m.group(1)
            if num != "3":
                off_count_found = num
                break
        if off_count_found is None:
            digit_near_pattern2 = re.compile(
                r"(?:LOCK(?:S|ED)?\s*OUT\s*AFTER)\s*([0-9]{1,2})\b"
            )
            for m in digit_near_pattern2.finditer(just_norm):
                num = m.group(1)
                if num != "3":
                    off_count_found = num
                    break
        if off_count_found is None:
            # word-based: TWO ATTEMPTS, FOUR ATTEMPTS, FIVE FAILURES, etc.
            word_near_pattern = re.compile(
                r"\b(ZERO|ONE|TWO|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)\b\s*(?:CONSECUTIVE\s+)?(?:FAILED\s+)?"
                r"(?:ATTEMPTS?|TRIES|TRY|GUESSES?|FAILURES?)"
            )
            m = word_near_pattern.search(just_norm)
            if m:
                off_count_found = m.group(1)

        if off_count_found is not None:
            return False, (f"fault_free_justification implies an altered attempt count "
                            f"('{off_count_found}') instead of the documented 3-consecutive-failure lockout")

        has_three = bool(re.search(r"\b3\b|\bTHREE\b", just_norm))
        if not has_three:
            return False, "fault_free_justification does not mention preservation of the 3-attempt sequence"

        consistency_terms = [
            "RESTORE", "INCREMENT", "ATOMIC", "SAME AS BEFORE", "UNCHANGED", "STILL DECREMENTS ONCE",
            "NET EFFECT", "EACH FAILED ATTEMPT STILL", "EXHAUST", "STILL REACHES 0", "STILL REACHES ZERO",
        ]
        if not any(t in just_norm for t in consistency_terms):
            return False, "fault_free_justification not clearly consistent with the decrement-on-entry+restore remediation preserving the 3-attempt count"

        # --- (3)/(4) Cross-check the ARITHMETIC implied by the remediation's own
        # description, independent of the justification's surface keywords. ---
        entry_decrement_phrases = [
            "DECREMENT ON ENTRY TO COMPARE", "DECREMENT ON ENTRY", "DECREMENT AT COMPARE ENTRY",
            "DECREMENT WHEN ENTERING COMPARE", "DECREMENT AS SOON AS", "SPECULATIVELY DECREMENT",
            "DECREMENT UPON ENTERING COMPARE", "DECREMENT IN COMPARE", "MOVE THE DECREMENT TO COMPARE",
            "MOVE DECREMENT TO COMPARE",
        ]
        restore_phrases = [
            "RESTORE", "INCREMENT BACK", "INCREMENT ON MATCH", "INCREMENT ON SUCCESS",
            "RESTORE ON SUCCESS", "RESTORE ON MATCH", "UNDO THE DECREMENT", "ROLL BACK",
            "INCREMENT IT BACK", "INCREMENT THE COUNTER BACK", "CANCEL THE DECREMENT",
            "COMPENSATING INCREMENT", "OFFSETTING INCREMENT", "REVERT THE DECREMENT",
        ]
        atomic_phrases = [
            "ATOMIC", "SAME STATE", "SINGLE STATE", "COMBINE", "MERGE COMPARE AND CHECK_DONE",
            "MERGE THE COMPARE AND CHECK_DONE", "ONE STATE", "SINGLE CYCLE", "SINGLE CLOCK EDGE",
        ]
        # A second decrement point described explicitly in CHECK_DONE (or "on failure"/"on
        # mismatch") in addition to the entry decrement, with no cancelling restore, implies
        # a double-decrement per failed attempt.
        second_decrement_phrases = [
            "DECREMENT AGAIN", "ALSO DECREMENT", "DECREMENT A SECOND TIME", "ANOTHER DECREMENT",
            "DECREMENT ONCE MORE", "SECOND DECREMENT", "DECREMENT IN CHECK_DONE",
            "DECREMENT ON FAILURE IN CHECK_DONE", "DECREMENT AGAIN IN CHECK_DONE",
            "DECREMENT ON MISMATCH IN CHECK_DONE", "STILL DECREMENT IN CHECK_DONE",
            "ALSO DECREMENT IN CHECK_DONE", "DECREMENT BOTH", "DECREMENT AT COMPARE ENTRY AND",
            "DECREMENT AT BOTH", "TWICE PER FAILED ATTEMPT", "TWO DECREMENTS PER",
            "DECREMENTS TWICE",
        ]

        has_entry_decrement = any(p in rem_norm for p in entry_decrement_phrases)
        has_restore = any(p in rem_norm for p in restore_phrases)
        has_atomic = any(p in rem_norm for p in atomic_phrases)
        has_second_decrement = any(p in rem_norm for p in second_decrement_phrases)

        # Explicit statement that no cancellation/restore occurs on a decrement-on-entry
        # scheme is a net-2-decrements-on-failure (never cancelled) or, more importantly
        # for SR4, indicates a double bookkeeping path that doesn't collapse to 1 net
        # decrement per failed attempt.
        no_cancel_phrases = [
            "NO CANCELLATION", "WITHOUT CANCELLING", "WITHOUT CANCELING", "NO OFFSETTING",
            "WITH NO CANCELLATION", "NOT CANCELLED", "NOT CANCELED",
        ]
        has_no_cancel = any(p in rem_norm for p in no_cancel_phrases)

        # Determine implied net decrements per failed attempt from the remediation's own
        # described mechanism:
        #   - Entry decrement + explicit second decrement in CHECK_DONE on failure, with
        #     no restore/cancellation mentioned -> net 2 per failed attempt -> INCONSISTENT.
        #   - Entry decrement + second decrement + has_no_cancel explicitly -> net 2 -> INCONSISTENT.
        #   - Entry decrement + restore-on-success only (no second decrement described) ->
        #     net 1 per failed attempt (restore only fires on success, so failed attempts are
        #     unaffected by restore) -> CONSISTENT.
        #   - Atomic merge (single state does both) -> net 1 per outcome -> CONSISTENT.
        if has_entry_decrement and has_second_decrement:
            return False, ("remediation's own description implies decrementing attempts_left both "
                            "at COMPARE entry and again on failure in CHECK_DONE with no offsetting "
                            "restore, yielding a net of 2 decrements per failed attempt instead of 1 "
                            "-- this would exhaust the 3-attempt budget after fewer than 3 fault-free "
                            "failures, contradicting the claimed fault_free_behavior_preserved=true")

        if has_no_cancel and has_entry_decrement:
            return False, ("remediation explicitly describes decrement bookkeeping without a "
                            "cancellation/restore mechanism, implying more than one net decrement "
                            "per failed attempt")

        # has_entry_decrement without restore/atomic is already rejected by SR3; for SR4's
        # narrower arithmetic scope (failed-attempt net-decrement consistency) it does not
        # itself imply a double-decrement-per-failure, so it is not re-flagged here.

        return True, ""

    ok, reason = sr4_check()
    record("SR4", ok, reason)

    # =========================================================
    # Optional corroboration: cross-simulate state-skip stimulus.
    # This is purely informational/corroborative and does NOT gate
    # PASS/FAIL on any requirement -- the report text itself is graded
    # above. Failures here are silently ignored (best-effort).
    # =========================================================
    try:
        tb_path = os.path.join("evaluation", "tb_stateskip.v")
        rtl_path = os.path.join(inputs_dir, "pin_check_fsm.v")
        if os.path.isfile(tb_path) and os.path.isfile(rtl_path):
            with tempfile.TemporaryDirectory() as tmpdir:
                sim_bin = os.path.join(tmpdir, "sim.vvp")
                compile_cmd = ["iverilog", "-g2012", "-o", sim_bin, rtl_path, tb_path]
                cp = subprocess.run(
                    compile_cmd, capture_output=True, text=True, timeout=30
                )
                if cp.returncode == 0:
                    rp = subprocess.run(
                        ["vvp", sim_bin], capture_output=True, text=True, timeout=30
                    )
                    # Purely corroborative; parse but do not affect verdicts.
                    _ = re.findall(
                        r"STATESKIP attempts_before=(\d+) attempts_after=(\d+)", rp.stdout
                    )
    except Exception:
        pass

    if all(RESULTS):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()