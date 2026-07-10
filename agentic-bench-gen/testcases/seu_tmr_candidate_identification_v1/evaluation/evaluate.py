#!/usr/bin/env python3
"""
evaluate.py - Grader for seu_tmr_candidate_identification_v1

Reads reference input artifacts under inputs/ and grades the participant's
submission/vulnerability_report.json against FR1-FR4 (structural/format) and
SR1-SR3 (substantive correctness against hidden ground truth).
"""

import json
import os
import sys

INPUTS_DIR = "inputs"
SUBMISSION_PATH = os.path.join("submission", "vulnerability_report.json")
REGISTER_MAP_PATH = os.path.join(INPUTS_DIR, "register_map.json")
CONTROLLER_RTL_PATH = os.path.join(INPUTS_DIR, "controller_datapath.v")
FAULT_MODEL_PATH = os.path.join(INPUTS_DIR, "fault_model.md")
GROUND_TRUTH_PATH = os.path.join(os.path.dirname(__file__), "private", "ground_truth.json")

results = []  # list of (req_id, bool_passed, reason_or_None)


def record(req_id, passed, reason=None):
    results.append((req_id, passed, reason))
    if passed:
        print("[TEST] PASS: {}".format(req_id))
    else:
        print("[TEST] FAIL: {}: {}".format(req_id, reason))


def fail_setup(path):
    print("[TEST] FAIL: SETUP: {} not found".format(path))
    sys.exit(1)


def main():
    # --- Existence checks for input artifacts (SETUP-level, not a graded requirement) ---
    for p in (REGISTER_MAP_PATH, CONTROLLER_RTL_PATH, FAULT_MODEL_PATH):
        if not os.path.isfile(p):
            fail_setup(p)

    # --- Load register_map.json (canonical register name inventory) ---
    try:
        with open(REGISTER_MAP_PATH, "r", encoding="utf-8") as f:
            register_map_data = json.load(f)
    except Exception as e:
        fail_setup(REGISTER_MAP_PATH + " (unparseable: {})".format(e))
        return

    try:
        reg_map_entries = register_map_data["registers"]
        canonical_names = set()
        for entry in reg_map_entries:
            canonical_names.add(entry["signal_name"])
    except Exception as e:
        fail_setup(REGISTER_MAP_PATH + " (malformed: {})".format(e))
        return

    # --- Load private ground truth ---
    if not os.path.isfile(GROUND_TRUTH_PATH):
        fail_setup(GROUND_TRUTH_PATH)
        return
    try:
        with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
            ground_truth = json.load(f)
        control_state_regs = list(ground_truth["control_state_registers"])
        data_pipeline_regs = list(ground_truth["data_pipeline_registers"])
        sr3_keywords = [kw.lower() for kw in ground_truth["sr3_keywords"]]
    except Exception as e:
        fail_setup(GROUND_TRUTH_PATH + " (malformed: {})".format(e))
        return

    # --- Open submission file ---
    if not os.path.isfile(SUBMISSION_PATH):
        print("[TEST] FAIL: SETUP: {} not found".format(SUBMISSION_PATH))
        sys.exit(1)

    parse_error = None
    report = None
    try:
        with open(SUBMISSION_PATH, "r", encoding="utf-8") as f:
            raw_text = f.read()
        report = json.loads(raw_text)
    except Exception as e:
        parse_error = str(e)

    # ================= FR4: valid JSON, exact top-level keys, schema_version =================
    fr4_ok = True
    fr4_reason = None
    if parse_error is not None:
        fr4_ok = False
        fr4_reason = "submission is not valid JSON: {}".format(parse_error)
    elif not isinstance(report, dict):
        fr4_ok = False
        fr4_reason = "top-level JSON value is not an object"
    else:
        expected_keys = {"schema_version", "summary", "registers"}
        actual_keys = set(report.keys())
        if actual_keys != expected_keys:
            fr4_ok = False
            fr4_reason = "top-level keys {} do not exactly match expected {}".format(
                sorted(actual_keys), sorted(expected_keys)
            )
        elif report.get("schema_version") != "1.0":
            fr4_ok = False
            fr4_reason = "schema_version is {!r}, expected '1.0'".format(report.get("schema_version"))

    record("FR4", fr4_ok, fr4_reason)

    # If we cannot even parse/structure the report, everything downstream fails deterministically.
    report_usable = fr4_ok
    registers_list = None
    summary_obj = None
    if report_usable:
        registers_list = report.get("registers")
        summary_obj = report.get("summary")
        if not isinstance(registers_list, list):
            report_usable = False
        if not isinstance(summary_obj, dict):
            report_usable = False

    # Build a normalized view of register entries: signal_name -> entry (first occurrence)
    entries_by_name = {}
    entry_list_valid_shape = True  # whether every entry is at least a dict with signal_name str
    if report_usable:
        for entry in registers_list:
            if not isinstance(entry, dict) or not isinstance(entry.get("signal_name"), str):
                entry_list_valid_shape = False
                continue
            name = entry["signal_name"]
            if name not in entries_by_name:
                entries_by_name[name] = entry

    # ================= FR1: register inventory matches register_map.json exactly =================
    if not report_usable:
        record("FR1", False, "submission report is malformed JSON/structure; cannot check register inventory")
    else:
        submitted_names = set(entries_by_name.keys())
        missing = canonical_names - submitted_names
        fabricated = submitted_names - canonical_names
        if missing or fabricated:
            parts = []
            if missing:
                parts.append("missing: {}".format(sorted(missing)))
            if fabricated:
                parts.append("fabricated: {}".format(sorted(fabricated)))
            record("FR1", False, "; ".join(parts))
        else:
            record("FR1", True)

    # ================= FR2: each entry has correctly-typed required fields =================
    # NOTE: bit_width is checked only for presence/type (positive int), NOT cross-referenced
    # against register_map.json's numeric value -- an independently-derived correct submission
    # may legitimately report different (but internally consistent) bit widths than the
    # reference table, and FR2 is a field-presence/format requirement, not a value-equality
    # requirement against an external table.
    if not report_usable:
        record("FR2", False, "submission report is malformed JSON/structure; cannot check register fields")
    elif not entry_list_valid_shape:
        record("FR2", False, "one or more entries in 'registers' are not objects with a string signal_name")
    else:
        fr2_problems = []
        allowed_categories = {"control_state", "data_pipeline"}
        for entry in registers_list:
            if not isinstance(entry, dict):
                fr2_problems.append("entry is not an object")
                continue
            name = entry.get("signal_name")
            if not isinstance(name, str) or name == "":
                fr2_problems.append("entry has invalid/missing signal_name")
                continue

            bit_width = entry.get("bit_width")
            if not isinstance(bit_width, int) or isinstance(bit_width, bool):
                fr2_problems.append("{}: bit_width is not an int".format(name))
            elif bit_width <= 0:
                fr2_problems.append("{}: bit_width {} is not a positive integer".format(name, bit_width))

            category = entry.get("category")
            if category not in allowed_categories:
                fr2_problems.append(
                    "{}: category {!r} not one of {}".format(name, category, sorted(allowed_categories))
                )

            tmr = entry.get("tmr_recommended")
            if not isinstance(tmr, bool):
                fr2_problems.append("{}: tmr_recommended is not a boolean".format(name))

            justification = entry.get("justification")
            if not isinstance(justification, str) or justification.strip() == "":
                fr2_problems.append("{}: justification is missing or empty".format(name))

        if fr2_problems:
            record("FR2", False, "; ".join(fr2_problems[:6]) + (" (+more)" if len(fr2_problems) > 6 else ""))
        else:
            record("FR2", True)

    # ================= FR3: summary counts internally consistent =================
    if not report_usable:
        record("FR3", False, "submission report is malformed JSON/structure; cannot check summary consistency")
    else:
        required_summary_fields = ["total_registers", "control_state_count", "data_pipeline_count", "tmr_recommended_count"]
        summary_type_problems = []
        for field in required_summary_fields:
            val = summary_obj.get(field)
            if not isinstance(val, int) or isinstance(val, bool):
                summary_type_problems.append("summary.{} missing or not an int".format(field))

        if summary_type_problems:
            record("FR3", False, "; ".join(summary_type_problems))
        else:
            computed_total = len(entries_by_name)
            computed_control = sum(1 for e in entries_by_name.values() if e.get("category") == "control_state")
            computed_data = sum(1 for e in entries_by_name.values() if e.get("category") == "data_pipeline")
            computed_tmr = sum(1 for e in entries_by_name.values() if e.get("tmr_recommended") is True)

            mismatches = []
            if summary_obj.get("total_registers") != computed_total:
                mismatches.append(
                    "total_registers {} != computed {}".format(summary_obj.get("total_registers"), computed_total)
                )
            if summary_obj.get("control_state_count") != computed_control:
                mismatches.append(
                    "control_state_count {} != computed {}".format(
                        summary_obj.get("control_state_count"), computed_control
                    )
                )
            if summary_obj.get("data_pipeline_count") != computed_data:
                mismatches.append(
                    "data_pipeline_count {} != computed {}".format(
                        summary_obj.get("data_pipeline_count"), computed_data
                    )
                )
            if summary_obj.get("tmr_recommended_count") != computed_tmr:
                mismatches.append(
                    "tmr_recommended_count {} != computed {}".format(
                        summary_obj.get("tmr_recommended_count"), computed_tmr
                    )
                )

            if mismatches:
                record("FR3", False, "; ".join(mismatches))
            else:
                record("FR3", True)

    # ================= SR1: all 5 control_state registers correctly flagged =================
    if not report_usable:
        record("SR1", False, "submission report is malformed JSON/structure; cannot check control-state classification")
    else:
        sr1_problems = []
        for name in control_state_regs:
            entry = entries_by_name.get(name)
            if entry is None:
                sr1_problems.append("{}: missing from submission".format(name))
                continue
            if entry.get("category") != "control_state":
                sr1_problems.append(
                    "{}: category is {!r}, expected 'control_state'".format(name, entry.get("category"))
                )
            if entry.get("tmr_recommended") is not True:
                sr1_problems.append(
                    "{}: tmr_recommended is {!r}, expected true".format(name, entry.get("tmr_recommended"))
                )
        if sr1_problems:
            record("SR1", False, "; ".join(sr1_problems))
        else:
            record("SR1", True)

    # ================= SR2: at most 1 of 3 data-pipeline registers TMR-recommended =================
    if not report_usable:
        record("SR2", False, "submission report is malformed JSON/structure; cannot check data-pipeline over-hardening")
    else:
        tmr_true_data = []
        for name in data_pipeline_regs:
            entry = entries_by_name.get(name)
            if entry is not None and entry.get("tmr_recommended") is True:
                tmr_true_data.append(name)
        if len(tmr_true_data) > 1:
            record(
                "SR2",
                False,
                "{} of 3 data-pipeline registers marked tmr_recommended=true (>1): {}".format(
                    len(tmr_true_data), tmr_true_data
                ),
            )
        else:
            record("SR2", True)

    # ================= SR3: >=3 of 5 control-state justifications reference silent-corruption rationale =================
    if not report_usable:
        record("SR3", False, "submission report is malformed JSON/structure; cannot check justification quality")
    else:
        matched_count = 0
        unmatched = []
        for name in control_state_regs:
            entry = entries_by_name.get(name)
            justification = ""
            if entry is not None and isinstance(entry.get("justification"), str):
                justification = entry["justification"].lower()
            if any(kw in justification for kw in sr3_keywords):
                matched_count += 1
            else:
                unmatched.append(name)
        if matched_count >= 3:
            record("SR3", True)
        else:
            record(
                "SR3",
                False,
                "only {} of 5 control-state justifications reference silent-corruption rationale "
                "(need >=3); lacking: {}".format(matched_count, unmatched),
            )

    # ================= Final verdict =================
    any_failed = any(not passed for (_rid, passed, _reason) in results)
    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()