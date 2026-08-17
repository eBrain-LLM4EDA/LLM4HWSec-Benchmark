#!/usr/bin/env python3
"""
evaluate.py -- Grades submission/vulnerability_report.json against the
hidden ground truth for the precharge_bus_wrapper Hamming-weight bus
leakage task.

This script reads reference artifacts under inputs/ for context and
ground truth, but the PASS/FAIL verdicts are computed against the
submitted answer file at submission/vulnerability_report.json.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

INPUTS_DIR = "inputs"
SUBMISSION_PATH = os.path.join("submission", "vulnerability_report.json")

RTL_FILENAME = os.path.join(INPUTS_DIR, "precharge_bus_wrapper.v")
FAULT_MODEL_FILENAME = os.path.join(INPUTS_DIR, "fault_model.json")
DESIGN_BRIEF_FILENAME = os.path.join(INPUTS_DIR, "design_brief.md")
ACTIVITY_TEMPLATE_FILENAME = os.path.join(INPUTS_DIR, "activity_trace_template.txt")

TB_CHECK_PATH = os.path.join("evaluation", "tb_check.v")

results = []  # list of (id, passed_bool, message)


def record(req_id, passed, reason=""):
    if passed:
        print("[TEST] PASS: %s" % req_id)
    else:
        print("[TEST] FAIL: %s: %s" % (req_id, reason))
    results.append((req_id, passed, reason))


def fail_setup_and_exit(path):
    print("[TEST] FAIL: SETUP: %s not found" % path)
    sys.exit(1)


def load_text_file(path):
    if not os.path.isfile(path):
        fail_setup_and_exit(path)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    # --- Load required input artifacts (context / ground truth sources) ---
    rtl_text = load_text_file(RTL_FILENAME)
    load_text_file(FAULT_MODEL_FILENAME)  # existence check only; read for context
    design_brief_text = load_text_file(DESIGN_BRIEF_FILENAME)
    load_text_file(ACTIVITY_TEMPLATE_FILENAME)  # existence check only

    # --- Load submission (the graded artifact) ---
    if not os.path.isfile(SUBMISSION_PATH):
        fail_setup_and_exit(SUBMISSION_PATH)

    with open(SUBMISSION_PATH, "r", encoding="utf-8") as f:
        raw_submission = f.read()

    try:
        report = json.loads(raw_submission)
    except Exception as e:
        # If the JSON itself is unparseable, every requirement that depends
        # on parsed structure must fail. We still emit one line per
        # requirement rather than SETUP, since the submission file exists
        # but its content is invalid per the schema.
        parse_err = str(e)
        for req_id in ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4", "SR5"]:
            record(req_id, False, "submission is not valid JSON: %s" % parse_err)
        sys.exit(1)

    if not isinstance(report, dict):
        for req_id in ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4", "SR5"]:
            record(req_id, False, "submission JSON is not an object")
        sys.exit(1)

    # =====================================================================
    # FR1: required top-level keys/types
    # =====================================================================
    fr1_ok = True
    fr1_reasons = []

    def check_key(key, expected_types, type_desc):
        nonlocal fr1_ok
        if key not in report:
            fr1_ok = False
            fr1_reasons.append("missing key '%s'" % key)
            return None
        val = report[key]
        if not isinstance(val, expected_types):
            fr1_ok = False
            fr1_reasons.append("key '%s' must be %s, got %s" % (key, type_desc, type(val).__name__))
            return None
        return val

    leaking_phase_val = check_key("leaking_phase", (str,), "a string")
    affected_nets_val = check_key("affected_nets", (list,), "an array")
    if isinstance(affected_nets_val, list):
        if not all(isinstance(x, str) for x in affected_nets_val):
            fr1_ok = False
            fr1_reasons.append("'affected_nets' must be an array of strings")
    leakage_metric_val = check_key("leakage_metric", (str,), "a string")
    mitigation_val = check_key("mitigation", (str,), "a string")

    func_equiv_val = report.get("functional_equivalence_claim", None)
    if "functional_equivalence_claim" not in report:
        fr1_ok = False
        fr1_reasons.append("missing key 'functional_equivalence_claim'")
    elif not isinstance(func_equiv_val, (bool, str)):
        fr1_ok = False
        fr1_reasons.append(
            "'functional_equivalence_claim' must be a boolean or string, got %s"
            % type(func_equiv_val).__name__
        )

    transfer_timing_val = check_key("transfer_timing", (dict,), "an object")

    record("FR1", fr1_ok, "; ".join(fr1_reasons) if fr1_reasons else "")

    # =====================================================================
    # Build valid dbus net-name set from the actual RTL declaration.
    # =====================================================================
    # Look for the dbus port declaration, e.g.:
    #   output reg  [7:0] dbus,
    port_decl_pattern = re.compile(
        r'output\s+reg\s*\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*dbus\b'
    )
    m = port_decl_pattern.search(rtl_text)
    if m:
        hi = int(m.group(1))
        lo = int(m.group(2))
    else:
        # Fallback: still expect an 8-bit dbus bus per the pinned interface,
        # in case declaration style differs slightly (e.g. spacing).
        hi, lo = 7, 0

    bit_indices = list(range(min(hi, lo), max(hi, lo) + 1))
    whole_bus_tokens = set()
    whole_bus_tokens.add("dbus")
    whole_bus_tokens.add("dbus[%d:%d]" % (hi, lo))
    whole_bus_tokens.add("dbus[%d:%d]" % (max(hi, lo), min(hi, lo)))
    whole_bus_tokens.add("dbus[7:0]")

    bit_tokens = set()
    for i in bit_indices:
        bit_tokens.add("dbus[%d]" % i)

    valid_dbus_tokens = whole_bus_tokens | bit_tokens

    def normalize_net_token(s):
        # Remove whitespace, lower-case for comparison purposes on the
        # "dbus" literal itself, but keep bracket digits intact.
        return re.sub(r'\s+', '', s.strip())

    def is_valid_dbus_reference(token):
        norm = normalize_net_token(token)
        # Accept exact matches against known valid tokens (case-insensitive
        # on the leading "dbus" literal).
        norm_cmp = norm
        for valid in valid_dbus_tokens:
            if norm_cmp.lower() == valid.lower():
                return True
        # Also accept case-insensitive whole-bus phrase mentions like
        # "dbus[7:0]" embedded with extra text is not expected since these
        # are supposed to be net name entries, so we do exact-token
        # comparisons only above. But also allow bare "dbus" bit access
        # patterns not caught above, e.g. differing bracket spacing already
        # normalized.
        return False

    # =====================================================================
    # FR2: affected_nets entries reference dbus / its bit indices
    # =====================================================================
    fr2_ok = True
    fr2_reasons = []
    if not isinstance(affected_nets_val, list) or len(affected_nets_val) == 0:
        fr2_ok = False
        fr2_reasons.append("'affected_nets' missing or empty")
    else:
        invalid_entries = []
        for entry in affected_nets_val:
            if not isinstance(entry, str):
                invalid_entries.append(str(entry))
                continue
            if not is_valid_dbus_reference(entry):
                invalid_entries.append(entry)
        if invalid_entries:
            fr2_ok = False
            fr2_reasons.append(
                "entries not derivable from declared dbus port: %s" % invalid_entries
            )

    record("FR2", fr2_ok, "; ".join(fr2_reasons) if fr2_reasons else "")

    # =====================================================================
    # FR3: mitigation names a concrete bus-leakage countermeasure technique
    # =====================================================================
    countermeasure_keyword_pattern = re.compile(
        r'(dual[-\s]?rail|complementary|complement|constant[-\s]?weight|'
        r'constant[-\s]?hamming|masking|random\s*mask|balanced)',
        re.IGNORECASE,
    )

    fr3_ok = True
    fr3_reasons = []
    if not isinstance(mitigation_val, str) or not mitigation_val.strip():
        fr3_ok = False
        fr3_reasons.append("'mitigation' is empty or not a string")
    elif not countermeasure_keyword_pattern.search(mitigation_val):
        fr3_ok = False
        fr3_reasons.append(
            "'mitigation' does not name a recognized bus-leakage countermeasure "
            "technique (dual-rail, complementary/complement encoding, "
            "constant-weight/constant-Hamming encoding, or masking); got: %r"
            % mitigation_val
        )

    record("FR3", fr3_ok, "; ".join(fr3_reasons) if fr3_reasons else "")

    # =====================================================================
    # FR4: transfer_timing has integer precharge_cycle_offset and
    # evaluate_cycle_offset fields
    # =====================================================================
    fr4_ok = True
    fr4_reasons = []
    precharge_offset = None
    evaluate_offset = None
    if not isinstance(transfer_timing_val, dict):
        fr4_ok = False
        fr4_reasons.append("'transfer_timing' missing or not an object")
    else:
        precharge_offset = transfer_timing_val.get("precharge_cycle_offset", None)
        evaluate_offset = transfer_timing_val.get("evaluate_cycle_offset", None)
        if not isinstance(precharge_offset, int) or isinstance(precharge_offset, bool):
            fr4_ok = False
            fr4_reasons.append(
                "'transfer_timing.precharge_cycle_offset' missing or not an integer"
            )
        if not isinstance(evaluate_offset, int) or isinstance(evaluate_offset, bool):
            fr4_ok = False
            fr4_reasons.append(
                "'transfer_timing.evaluate_cycle_offset' missing or not an integer"
            )

    record("FR4", fr4_ok, "; ".join(fr4_reasons) if fr4_reasons else "")

    # =====================================================================
    # SR1: leaking_phase == 'evaluate' (case-insensitive, trimmed)
    # =====================================================================
    if isinstance(leaking_phase_val, str) and leaking_phase_val.strip().lower() == "evaluate":
        record("SR1", True)
    else:
        record(
            "SR1",
            False,
            "leaking_phase must be 'evaluate' (the precharge->evaluate "
            "transition where the Hamming-weight-dependent transition "
            "occurs), got: %r" % leaking_phase_val,
        )

    # =====================================================================
    # SR2: affected_nets covers the full dbus[7:0] bus
    # =====================================================================
    sr2_ok = False
    sr2_reason = ""
    if isinstance(affected_nets_val, list):
        normalized_entries = set()
        for entry in affected_nets_val:
            if isinstance(entry, str):
                normalized_entries.add(normalize_net_token(entry).lower())

        has_whole_bus_token = any(
            tok.lower() in normalized_entries for tok in whole_bus_tokens
        )
        has_all_bits = all(
            ("dbus[%d]" % i).lower() in normalized_entries for i in bit_indices
        )

        if has_whole_bus_token or has_all_bits:
            sr2_ok = True
        else:
            sr2_reason = (
                "affected_nets does not cover the full dbus[%d:%d] bus "
                "(neither a whole-bus token nor all individual bit indices "
                "are present); got: %s" % (max(hi, lo), min(hi, lo), affected_nets_val)
            )
    else:
        sr2_reason = "'affected_nets' missing or not a list"

    record("SR2", sr2_ok, sr2_reason)

    # =====================================================================
    # SR3: leakage_metric describes Hamming-weight/transition-count metric
    # =====================================================================
    transition_terms_pattern = re.compile(
        r'(hamming|transition|switching|toggle)', re.IGNORECASE
    )
    weight_count_terms_pattern = re.compile(
        r'(weight|count)', re.IGNORECASE
    )
    unrelated_terms_pattern = re.compile(
        r'(timing\s*delay|propagation\s*delay|fault\s*count|clock\s*skew)',
        re.IGNORECASE,
    )

    sr3_ok = False
    sr3_reason = ""
    if not isinstance(leakage_metric_val, str) or not leakage_metric_val.strip():
        sr3_reason = "'leakage_metric' is empty or not a string"
    else:
        has_transition_term = bool(transition_terms_pattern.search(leakage_metric_val))
        has_weight_count_term = bool(weight_count_terms_pattern.search(leakage_metric_val))
        has_unrelated_only = bool(unrelated_terms_pattern.search(leakage_metric_val))

        if has_transition_term and has_weight_count_term:
            sr3_ok = True
        elif has_unrelated_only and not (has_transition_term and has_weight_count_term):
            sr3_reason = (
                "'leakage_metric' describes an unrelated metric (timing "
                "delay / fault count) rather than a Hamming-weight or "
                "transition-count based metric; got: %r" % leakage_metric_val
            )
        else:
            sr3_reason = (
                "'leakage_metric' does not describe a Hamming-weight or "
                "transition-count-based metric (needs a transition-like "
                "term such as hamming/transition/switching/toggle combined "
                "with a weight/count term); got: %r" % leakage_metric_val
            )

    record("SR3", sr3_ok, sr3_reason)

    # =====================================================================
    # SR4: mitigation achieves constant transition count AND
    # functional_equivalence_claim is affirmative
    # =====================================================================
    constant_weight_pattern = re.compile(
        r'(dual[-\s]?rail|complementary|complement|constant[-\s]?weight|'
        r'constant[-\s]?hamming|balanced)',
        re.IGNORECASE,
    )

    def is_affirmative_claim(val):
        if isinstance(val, bool):
            return val is True
        if isinstance(val, str):
            v = val.strip().lower()
            if v in ("true", "yes"):
                return True
            affirmative_terms = re.compile(
                r'(yes|true|preserve[sd]?|correct|equivalent|maintained|unchanged)',
                re.IGNORECASE,
            )
            negative_terms = re.compile(
                r'(no\b|false|not\s+preserv|not\s+equivalent|broken|incorrect)',
                re.IGNORECASE,
            )
            if negative_terms.search(v):
                return False
            return bool(affirmative_terms.search(v))
        return False

    sr4_ok = True
    sr4_reasons = []

    if not isinstance(mitigation_val, str) or not constant_weight_pattern.search(mitigation_val):
        sr4_ok = False
        sr4_reasons.append(
            "'mitigation' does not describe a constant-transition-count "
            "technique (complementary-bit companion word, dual-rail, or "
            "constant-Hamming-weight encoding; plain masking alone is "
            "insufficient); got: %r" % mitigation_val
        )

    if not is_affirmative_claim(func_equiv_val):
        sr4_ok = False
        sr4_reasons.append(
            "'functional_equivalence_claim' is not affirmative; got: %r" % func_equiv_val
        )

    record("SR4", sr4_ok, "; ".join(sr4_reasons) if sr4_reasons else "")

    # =====================================================================
    # SR5: transfer_timing offsets match ground truth from design_brief.md
    # (precharge at load+1, evaluate at load+2), with an optional,
    # non-authoritative iverilog/vvp cross-check.
    # =====================================================================
    precharge_gt_pattern = re.compile(
        r'\|\s*Precharge\s*\|\s*\+?\s*(-?\d+)\s*\|', re.IGNORECASE
    )
    evaluate_gt_pattern = re.compile(
        r'\|\s*Evaluate\s*\|\s*\+?\s*(-?\d+)\s*\|', re.IGNORECASE
    )

    pm = precharge_gt_pattern.search(design_brief_text)
    em = evaluate_gt_pattern.search(design_brief_text)

    if pm and em:
        gt_precharge_offset = int(pm.group(1))
        gt_evaluate_offset = int(em.group(1))
    else:
        # Fallback to the documented two-cycle latency contract if the
        # table text could not be parsed for some reason.
        gt_precharge_offset = 1
        gt_evaluate_offset = 2

    # Optional secondary cross-check via iverilog/vvp simulation. This is
    # purely supplementary; failures or unavailability of the toolchain do
    # not affect the SR5 verdict, which is always decided from the
    # documented ground truth above.
    sim_note = ""
    try:
        if os.path.isfile(TB_CHECK_PATH):
            with tempfile.TemporaryDirectory() as tmpdir:
                sim_bin = os.path.join(tmpdir, "sim.vvp")
                compile_proc = subprocess.run(
                    ["iverilog", "-g2012", "-o", sim_bin, RTL_FILENAME, TB_CHECK_PATH],
                    capture_output=True,
                    timeout=30,
                    text=True,
                )
                if compile_proc.returncode == 0:
                    run_proc = subprocess.run(
                        ["vvp", sim_bin],
                        capture_output=True,
                        timeout=30,
                        text=True,
                    )
                    sim_note = " (sim cross-check ran: %s)" % (
                        "ok" if run_proc.returncode == 0 else "vvp nonzero exit"
                    )
                else:
                    sim_note = " (sim cross-check skipped: compile failed)"
        else:
            sim_note = " (sim cross-check skipped: tb_check.v not present)"
    except Exception:
        sim_note = " (sim cross-check skipped: toolchain unavailable or errored)"

    sr5_ok = True
    sr5_reasons = []

    if precharge_offset != gt_precharge_offset:
        sr5_ok = False
        sr5_reasons.append(
            "transfer_timing.precharge_cycle_offset should be %d (per "
            "design_brief.md's documented two-cycle latency), got %r"
            % (gt_precharge_offset, precharge_offset)
        )

    if evaluate_offset != gt_evaluate_offset:
        sr5_ok = False
        sr5_reasons.append(
            "transfer_timing.evaluate_cycle_offset should be %d (per "
            "design_brief.md's documented two-cycle latency), got %r"
            % (gt_evaluate_offset, evaluate_offset)
        )

    record("SR5", sr5_ok, ("; ".join(sr5_reasons) + sim_note) if sr5_reasons else "")

    # =====================================================================
    # Final verdict
    # =====================================================================
    all_passed = all(passed for (_id, passed, _reason) in results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()