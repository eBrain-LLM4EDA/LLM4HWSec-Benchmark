#!/usr/bin/env python3
"""
evaluate.py -- Gate-level trojan detection report grader.

Grades submission/trojan_report.json against the reference netlist at
inputs/access_ctrl_netlist.v per FR1-FR4 (structural) and SR1-SR5
(substantive) requirements.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

INPUTS_DIR = "inputs"
SUBMISSION_DIR = "submission"
EVAL_DIR = "evaluation"

NETLIST_PATH = os.path.join(INPUTS_DIR, "access_ctrl_netlist.v")
CELL_LIB_PATH = os.path.join(INPUTS_DIR, "cell_library.v")
SUBMISSION_PATH = os.path.join(SUBMISSION_DIR, "trojan_report.json")
TB_CROSS_CHECK_PATH = os.path.join(EVAL_DIR, "tb_cross_check.v")

results = []  # list of (req_id, passed_bool, message)


def record(req_id, passed, reason=""):
    if passed:
        print("[TEST] PASS: {}".format(req_id))
    else:
        print("[TEST] FAIL: {}: {}".format(req_id, reason))
    results.append((req_id, passed, reason))


def normalize_instance_name(name):
    if not isinstance(name, str):
        return ""
    n = name.strip().lower()
    # strip common hierarchy separators
    n = n.replace(".", "").replace("/", "").replace("\\", "")
    return n


def main():
    # ---------------------------------------------------------------
    # SETUP: verify required input files exist
    # ---------------------------------------------------------------
    if not os.path.isfile(NETLIST_PATH):
        print("[TEST] FAIL: SETUP: {} not found".format(NETLIST_PATH))
        sys.exit(1)

    netlist_text = ""
    try:
        with open(NETLIST_PATH, "r") as f:
            netlist_text = f.read()
    except Exception as e:
        print("[TEST] FAIL: SETUP: could not read {}: {}".format(NETLIST_PATH, e))
        sys.exit(1)

    if not os.path.isfile(SUBMISSION_PATH):
        print("[TEST] FAIL: SETUP: {} not found".format(SUBMISSION_PATH))
        sys.exit(1)

    # ---------------------------------------------------------------
    # Extract identifier tokens from the netlist text for FR2 cross-ref
    # ---------------------------------------------------------------
    # Verilog identifiers: letters, digits, underscore, $, not starting with digit
    identifier_pattern = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")
    netlist_identifiers = set(identifier_pattern.findall(netlist_text))
    # also allow bracketed/indexed forms like grant_pre or key_in[3] to match on base name
    # (identifier_pattern already captures the base names; indices are separate tokens)

    # ---------------------------------------------------------------
    # Parse submission JSON
    # ---------------------------------------------------------------
    parse_error = None
    report = None
    try:
        with open(SUBMISSION_PATH, "r") as f:
            raw = f.read()
        report = json.loads(raw)
    except Exception as e:
        parse_error = str(e)

    fr_ids = ["FR1", "FR2", "FR3", "FR4"]
    sr_ids = ["SR1", "SR2", "SR3", "SR4", "SR5"]

    if parse_error is not None or not isinstance(report, dict):
        reason = "submission JSON could not be parsed: {}".format(
            parse_error if parse_error else "top-level value is not a JSON object"
        )
        for rid in fr_ids + sr_ids:
            record(rid, False, reason)
        sys.exit(1)

    # ---------------------------------------------------------------
    # FR1: top-level fields present with correct types
    # ---------------------------------------------------------------
    trojan_detected = report.get("trojan_detected", None)
    suspect_instances = report.get("suspect_instances", None)
    summary = report.get("summary", None)

    fr1_reasons = []
    if "trojan_detected" not in report or not isinstance(trojan_detected, bool):
        fr1_reasons.append("trojan_detected missing or not boolean")
    if "suspect_instances" not in report or not isinstance(suspect_instances, list):
        fr1_reasons.append("suspect_instances missing or not array")
    if "summary" not in report or not isinstance(summary, str):
        fr1_reasons.append("summary missing or not string")

    fr1_pass = len(fr1_reasons) == 0
    record("FR1", fr1_pass, "; ".join(fr1_reasons))

    # Normalize for downstream checks even if FR1 failed, to allow best-effort
    # grading of remaining requirements (each of which independently reports
    # its own PASS/FAIL).
    if not isinstance(suspect_instances, list):
        suspect_instances = []
    if not isinstance(summary, str):
        summary = ""
    if not isinstance(trojan_detected, bool):
        trojan_detected = None  # unknown / invalid

    # ---------------------------------------------------------------
    # FR2: each suspect_instances entry has non-empty strings that
    # reference identifiers verbatim found in the netlist text.
    # ---------------------------------------------------------------
    fr2_pass = True
    fr2_reason = ""
    required_fields = ["instance_name", "cell_type", "sampled_signal"]

    if not isinstance(report.get("suspect_instances", None), list):
        fr2_pass = False
        fr2_reason = "suspect_instances is not a list"
    else:
        for idx, entry in enumerate(report.get("suspect_instances", [])):
            if not isinstance(entry, dict):
                fr2_pass = False
                fr2_reason = "entry {} is not an object".format(idx)
                break
            bad = False
            for field in required_fields:
                val = entry.get(field, None)
                if not isinstance(val, str) or len(val.strip()) == 0:
                    fr2_pass = False
                    fr2_reason = "entry {} field '{}' is missing/empty".format(idx, field)
                    bad = True
                    break
                # verbatim substring check against raw netlist text (handles
                # tokens as well as compound expressions containing them)
                token = val.strip()
                if token in netlist_text:
                    continue
                # fall back to identifier-set membership (covers cases where
                # participant wrote just the base identifier)
                if token in netlist_identifiers:
                    continue
                fr2_pass = False
                fr2_reason = "entry {} field '{}' value '{}' not found in netlist".format(
                    idx, field, token
                )
                bad = True
                break
            if bad:
                break

    record("FR2", fr2_pass, fr2_reason)

    # ---------------------------------------------------------------
    # FR3: trojan_detected / suspect_instances consistency
    # ---------------------------------------------------------------
    fr3_pass = True
    fr3_reason = ""
    td_raw = report.get("trojan_detected", None)
    si_raw = report.get("suspect_instances", None)
    if not isinstance(td_raw, bool) or not isinstance(si_raw, list):
        fr3_pass = False
        fr3_reason = "cannot evaluate consistency: malformed trojan_detected/suspect_instances"
    else:
        if td_raw is True and len(si_raw) == 0:
            fr3_pass = False
            fr3_reason = "trojan_detected=true but suspect_instances is empty"
        elif td_raw is False and len(si_raw) != 0:
            fr3_pass = False
            fr3_reason = "trojan_detected=false but suspect_instances is non-empty"

    record("FR3", fr3_pass, fr3_reason)

    # ---------------------------------------------------------------
    # FR4: summary is a non-empty string of at least 20 characters
    # ---------------------------------------------------------------
    summary_raw = report.get("summary", None)
    if not isinstance(summary_raw, str):
        record("FR4", False, "summary is missing or not a string")
    else:
        stripped = summary_raw.strip()
        if len(stripped) < 20:
            record("FR4", False, "summary length {} < 20 characters".format(len(stripped)))
        else:
            record("FR4", True)

    # ---------------------------------------------------------------
    # SR1: correctly identify u_grant_ff as the anomalous instance
    # ---------------------------------------------------------------
    matched_entry = None
    target_norm = normalize_instance_name("u_grant_ff")

    valid_entries = []
    for entry in (suspect_instances if isinstance(suspect_instances, list) else []):
        if isinstance(entry, dict):
            valid_entries.append(entry)

    for entry in valid_entries:
        name = entry.get("instance_name", "")
        if normalize_instance_name(name) == target_norm:
            matched_entry = entry
            break

    sr1_pass = matched_entry is not None
    record(
        "SR1",
        sr1_pass,
        "" if sr1_pass else "no suspect_instances entry names u_grant_ff (case/hierarchy-insensitive)",
    )

    # ---------------------------------------------------------------
    # SR2: correctly identify cell_type as DFF_NEGEDGE / negedge language
    #
    # This check is fully independent: it is computed strictly from the
    # matched u_grant_ff entry's own cell_type/justification fields (plus
    # the report's summary as supplementary free-text evidence), and does
    # NOT consult any aggregate of other SR results. It runs whenever a
    # matching entry exists (regardless of whether SR1 "passed" via some
    # other bookkeeping), and independently FAILs if the cell_type is
    # wrong (e.g. DFF_POSEDGE) and no negedge/falling-edge language is
    # present.
    # ---------------------------------------------------------------
    if matched_entry is None:
        record("SR2", False, "cannot verify cell_type: no matching u_grant_ff entry (see SR1)")
    else:
        cell_type = matched_entry.get("cell_type", "")
        justification = matched_entry.get("justification", "")
        combined_text = " ".join(
            [
                justification if isinstance(justification, str) else "",
                summary if isinstance(summary, str) else "",
            ]
        ).lower()

        cell_type_str = cell_type.strip().upper() if isinstance(cell_type, str) else ""

        negedge_language_present = any(
            phrase in combined_text
            for phrase in [
                "negedge",
                "negative-edge",
                "negative edge",
                "falling edge",
                "falling-edge",
            ]
        )

        if cell_type_str == "DFF_NEGEDGE":
            sr2_pass = True
            sr2_reason = ""
        elif cell_type_str == "DFF_POSEDGE":
            # Explicitly wrong polarity claimed; free-text language cannot
            # rescue a directly contradictory cell_type field.
            sr2_pass = False
            sr2_reason = "cell_type reported as DFF_POSEDGE, contradicting the actual DFF_NEGEDGE instantiation"
        elif negedge_language_present:
            sr2_pass = True
            sr2_reason = ""
        else:
            sr2_pass = False
            sr2_reason = (
                "cell_type is not DFF_NEGEDGE (got: {!r}) and no negedge/falling-edge "
                "language found in justification/summary".format(cell_type)
            )

        record("SR2", sr2_pass, sr2_reason)

    # ---------------------------------------------------------------
    # SR3: correctly identify sampled_signal as grant_pre
    # ---------------------------------------------------------------
    if matched_entry is None:
        record("SR3", False, "cannot verify sampled_signal: no matching u_grant_ff entry (see SR1)")
    else:
        sampled_signal = matched_entry.get("sampled_signal", "")
        sr3_pass = (
            isinstance(sampled_signal, str) and sampled_signal.strip().lower() == "grant_pre"
        )
        record(
            "SR3",
            sr3_pass,
            "" if sr3_pass else "sampled_signal is not 'grant_pre' (got: {!r})".format(sampled_signal),
        )

    # ---------------------------------------------------------------
    # SR4: trojan_detected must be true
    # ---------------------------------------------------------------
    sr4_pass = trojan_detected is True
    record("SR4", sr4_pass, "" if sr4_pass else "trojan_detected is not true")

    # ---------------------------------------------------------------
    # SR5: simulation cross-check of the timing discrepancy narrative.
    #
    # This check ALWAYS runs the iverilog/vvp simulation (it is not a
    # lenient bypass gated on SR1-SR4 passing). It establishes golden
    # evidence of a half-cycle-early sample: the negedge-triggered
    # instance's registered output (grant_q) differs from grant_pre's
    # settled value at the following posedge, within the same clock
    # period. It then checks whether the submission's own narrative
    # (justification of the matched entry, plus summary) is consistent
    # with that evidence: it must not claim a different signal name is
    # responsible, must not describe the anomaly as multi-cycle drift
    # (as opposed to a half-cycle/sub-cycle timing issue), and must not
    # simply assert no discrepancy while trojan_detected is true.
    # ---------------------------------------------------------------
    sim_confirmed = False
    sim_error = None
    sim_mismatch_seen = False

    if not os.path.isfile(CELL_LIB_PATH):
        sim_error = "cell library file not found, skipping simulation"
    elif not os.path.isfile(TB_CROSS_CHECK_PATH):
        sim_error = "cross-check testbench not found, skipping simulation"
    else:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                sim_bin = os.path.join(tmpdir, "sim.vvp")
                compile_cmd = [
                    "iverilog",
                    "-g2012",
                    "-o",
                    sim_bin,
                    NETLIST_PATH,
                    CELL_LIB_PATH,
                    TB_CROSS_CHECK_PATH,
                ]
                compile_proc = subprocess.run(
                    compile_cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if compile_proc.returncode != 0:
                    sim_error = "iverilog compile failed: {}".format(
                        compile_proc.stderr.strip()[:300]
                    )
                else:
                    run_proc = subprocess.run(
                        ["vvp", sim_bin],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    if run_proc.returncode != 0:
                        sim_error = "vvp run failed: {}".format(run_proc.stderr.strip()[:300])
                    else:
                        stdout = run_proc.stdout
                        line_pattern = re.compile(
                            r"TB t=(\d+)\s+grant_pre=([01xXzZ])\s+grant_q=([01xXzZ])"
                        )
                        samples = []
                        for m in line_pattern.finditer(stdout):
                            t = int(m.group(1))
                            gp = m.group(2)
                            gq = m.group(3)
                            samples.append((t, gp, gq))

                        if len(samples) == 0:
                            sim_error = "no parseable TB lines produced by simulation"
                        else:
                            # Golden evidence: a half-cycle-early sample means
                            # that at some sample point, grant_q (captured on
                            # the negedge from a stale/transitional grant_pre)
                            # differs from grant_pre's own currently observed
                            # value, and this discrepancy resolves/changes by
                            # the *next* sample within the same or following
                            # half-period (i.e. it is a short-lived, sub-cycle
                            # mismatch rather than a persistent multi-cycle
                            # drift). We detect: any adjacent pair of samples
                            # where grant_pre != grant_q at one timestep, and
                            # then grant_pre == grant_q (or grant_q catches
                            # up to the prior grant_pre) shortly after --
                            # confirming a transient, half-cycle-scale event.
                            for i in range(len(samples)):
                                t, gp, gq = samples[i]
                                if gp in ("0", "1") and gq in ("0", "1") and gp != gq:
                                    sim_mismatch_seen = True
                                    # Check it resolves within a short window
                                    # (<= 2 samples, i.e. within about one
                                    # clock period) rather than persisting
                                    # indefinitely (which would indicate a
                                    # different kind of bug, not our target).
                                    resolved_soon = False
                                    for j in range(i + 1, min(i + 3, len(samples))):
                                        _tj, gpj, gqj = samples[j]
                                        if gpj in ("0", "1") and gqj in ("0", "1") and gpj == gqj:
                                            resolved_soon = True
                                            break
                                    if resolved_soon:
                                        sim_confirmed = True
                                        break

                            if not sim_confirmed and not sim_mismatch_seen:
                                sim_error = "simulation did not exhibit any grant_pre/grant_q mismatch"
                            elif not sim_confirmed and sim_mismatch_seen:
                                sim_error = (
                                    "simulation showed a persistent (non-half-cycle-scale) "
                                    "grant_pre/grant_q mismatch, not the expected transient "
                                    "half-cycle-early sample"
                                )
        except subprocess.TimeoutExpired:
            sim_error = "simulation timed out"
        except FileNotFoundError as e:
            sim_error = "toolchain not available: {}".format(e)
        except Exception as e:
            sim_error = "unexpected error running simulation: {}".format(e)

    # Gather the narrative text to check for consistency with simulated
    # evidence. Prefer the matched u_grant_ff entry's own fields; fall back
    # to scanning all entries plus the overall summary.
    narrative_parts = []
    if matched_entry is not None:
        j = matched_entry.get("justification", "")
        if isinstance(j, str):
            narrative_parts.append(j)
    for entry in valid_entries:
        j = entry.get("justification", "")
        if isinstance(j, str):
            narrative_parts.append(j)
    if isinstance(summary, str):
        narrative_parts.append(summary)
    narrative_text = " ".join(narrative_parts).lower()

    # Multi-cycle / wrong-granularity drift language that would misdescribe
    # a half-cycle-early sample as something else.
    multi_cycle_drift_phrases = [
        "multi-cycle drift",
        "multiple clock cycles",
        "several clock cycles",
        "drifts over multiple cycles",
        "accumulates over cycles",
        "long-term drift",
    ]
    half_cycle_phrases = [
        "half cycle",
        "half-cycle",
        "half a cycle",
        "sub-cycle",
        "sub cycle",
        "before the comparator",
        "before it settles",
        "settle",
        "negedge",
        "negative-edge",
        "negative edge",
        "falling edge",
        "falling-edge",
        "stale",
        "premature",
        "early",
    ]

    claims_multi_cycle_drift = any(p in narrative_text for p in multi_cycle_drift_phrases)
    claims_half_cycle_or_stale = any(p in narrative_text for p in half_cycle_phrases)

    # Determine whether the report names a signal other than grant_pre as
    # the locus of the discrepancy (wrong-signal narrative), when it does
    # discuss sampled/discrepant signals at all.
    wrong_signal_claim = False
    if matched_entry is not None:
        sampled_signal_val = matched_entry.get("sampled_signal", "")
        if isinstance(sampled_signal_val, str) and sampled_signal_val.strip():
            if sampled_signal_val.strip().lower() != "grant_pre":
                # Only relevant if that field is present but wrong; SR3
                # already penalizes this on its own, but for SR5 we
                # specifically check the *narrative* is not internally
                # inconsistent with the simulated evidence about grant_pre.
                wrong_signal_claim = True

    sr5_pass = True
    sr5_reason = ""

    if sim_error is not None and not sim_confirmed:
        # Could not establish golden evidence at all (toolchain problem or
        # inconclusive simulation). We cannot penalize the submission's
        # narrative against evidence we do not have, but we also cannot
        # confirm it. Treat as a FAIL only if the report actively contains
        # narrative claims that would be inconsistent with ANY sane timing
        # explanation (multi-cycle drift) or explicitly denies a
        # discrepancy while claiming detection; otherwise we cannot
        # adjudicate, and default to FAIL to avoid vacuously passing an
        # ungrounded claim, consistent with SR5 needing to independently
        # discriminate.
        sr5_pass = False
        sr5_reason = "simulation cross-check could not confirm golden half-cycle-mismatch evidence: {}".format(
            sim_error
        )
    else:
        # sim_confirmed is True: we have golden evidence of a transient,
        # half-cycle-scale grant_pre/grant_q mismatch. Now check narrative
        # consistency.
        if trojan_detected is not True:
            sr5_pass = False
            sr5_reason = "simulation confirms a timing discrepancy but trojan_detected is not true"
        elif claims_multi_cycle_drift and not claims_half_cycle_or_stale:
            sr5_pass = False
            sr5_reason = (
                "submission narrative describes a multi-cycle drift, inconsistent with the "
                "simulated evidence of a transient half-cycle-early sample"
            )
        elif wrong_signal_claim:
            sr5_pass = False
            sr5_reason = (
                "submission's sampled_signal for the matched instance does not match grant_pre, "
                "inconsistent with the simulated evidence localized to grant_pre"
            )
        elif not claims_half_cycle_or_stale:
            sr5_pass = False
            sr5_reason = (
                "submission narrative does not describe a half-cycle-early/stale-sample timing "
                "discrepancy consistent with the simulated evidence"
            )
        else:
            sr5_pass = True
            sr5_reason = ""

    record("SR5", sr5_pass, sr5_reason)

    # ---------------------------------------------------------------
    # Final verdict
    # ---------------------------------------------------------------
    all_pass = all(passed for (_rid, passed, _reason) in results)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()