#!/usr/bin/env python3
"""
evaluate.py -- gate_trojan_detection_counter_timebomb_001

Grades submission/trojan_report.json against the pinned public schema
(FR1-FR4) and against a hidden ground-truth node-role map
(evaluation/private/ground_truth.json, never shipped to participants)
for the security requirements (SR1-SR4).

Exits 0 iff every requirement PASSes; exits 1 otherwise.
"""

import json
import os
import re
import sys

NETLIST_PATH = "inputs/netlist.v"
SUBMISSION_PATH = "submission/trojan_report.json"
GROUND_TRUTH_PATH = "evaluation/private/ground_truth.json"

VALID_ROLES = {"counter", "comparator", "payload", "datapath", "io"}
TROJAN_ROLES = {"counter", "comparator", "payload"}

overall_ok = True


def report_pass(req_id, reason=""):
    print("[TEST] PASS: {}{}".format(req_id, (": " + reason) if reason else ""))


def report_fail(req_id, reason):
    global overall_ok
    overall_ok = False
    print("[TEST] FAIL: {}: {}".format(req_id, reason))


def base_name(name):
    if not isinstance(name, str):
        return None
    return name.split("[")[0].strip()


def load_netlist_identifiers(text):
    """Collect declared/produced identifiers from a gate-level Verilog netlist."""
    idents = set()

    # input/output/wire/reg declarations (possibly multiple comma-separated names)
    for m in re.finditer(
        r"\b(?:input|output|wire|reg)\s+(?:\[\s*\d+\s*:\s*\d+\s*\]\s+)?"
        r"([a-zA-Z_]\w*(?:\s*,\s*[a-zA-Z_]\w*)*)\s*;",
        text,
    ):
        for n in m.group(1).split(","):
            n = n.strip()
            if n:
                idents.add(n)

    # primitive gate instantiations: and/or/xor/not/nand/nor/xnor/buf (optional
    # instance name) ( <output>, ...);  -- first argument is the output net.
    for m in re.finditer(
        r"\b(?:and|or|xor|not|nand|nor|xnor|buf)\s+(?:\w+\s+)?\(\s*"
        r"([a-zA-Z_]\w*(?:\s*\[\s*\d+(?:\s*:\s*\d+)?\s*\])?)\s*,",
        text,
    ):
        idents.add(re.sub(r"\s+", "", m.group(1)))

    # assign statement left-hand sides
    for m in re.finditer(
        r"\bassign\s+([a-zA-Z_]\w*(?:\s*\[[^\]]*\])?)\s*=", text
    ):
        idents.add(re.sub(r"\s+", "", m.group(1)))

    return idents


def main():
    global overall_ok

    # ---- load netlist.v ----
    if not os.path.isfile(NETLIST_PATH):
        print("[TEST] FAIL: SETUP: {} not found".format(NETLIST_PATH))
        sys.exit(1)
    with open(NETLIST_PATH, "r", encoding="utf-8") as f:
        netlist_text = f.read()

    # ---- load hidden ground truth ----
    if not os.path.isfile(GROUND_TRUTH_PATH):
        print("[TEST] FAIL: SETUP: {} not found".format(GROUND_TRUTH_PATH))
        sys.exit(1)
    with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    true_nodes = ground_truth.get("true_nodes", {})
    counter_true = true_nodes.get("counter", [])
    comparator_true = true_nodes.get("comparator", [])
    payload_true = true_nodes.get("payload", [])
    coverage_threshold = ground_truth.get("coverage_threshold", 0.66)
    fpr_threshold = ground_truth.get("fpr_threshold", 0.4)

    # Flattened set of all true trigger+payload node base names (used both
    # for SR2 coverage and SR4 false-positive-rate computation).
    true_flat = list(counter_true) + list(comparator_true) + list(payload_true)
    true_bases = {base_name(t) for t in true_flat if base_name(t) is not None}

    # ---- load submission ----
    if not os.path.isfile(SUBMISSION_PATH):
        print("[TEST] FAIL: SETUP: {} not found".format(SUBMISSION_PATH))
        sys.exit(1)
    with open(SUBMISSION_PATH, "r", encoding="utf-8") as f:
        raw_text = f.read()

    requirement_ids = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]

    try:
        report = json.loads(raw_text)
        json_parse_failed = False
    except Exception as e:
        report = None
        json_parse_failed = True
        parse_error = str(e)

    if json_parse_failed:
        report_fail("FR1", "submission JSON is malformed: {}".format(parse_error))
        for rid in requirement_ids[1:]:
            report_fail(rid, "cannot evaluate: report JSON invalid")
        sys.exit(1)

    # Coerce non-dict roots to an empty dict so downstream checks degrade
    # gracefully (each field check will independently FAIL with its own
    # informative reason rather than a single blanket cascade).
    if not isinstance(report, dict):
        report_fail("FR1", "top-level JSON value is not an object")
        report = {}
    else:
        # ---- FR1: schema ----
        errors = []
        if not isinstance(report.get("design_name"), str):
            errors.append("design_name missing or not a string")
        if not isinstance(report.get("is_trojan_detected"), bool):
            errors.append("is_trojan_detected missing or not a boolean")

        sn_val = report.get("suspect_nodes")
        if not isinstance(sn_val, list) or not all(isinstance(x, str) for x in sn_val):
            errors.append("suspect_nodes missing or not an array of strings")

        sl_val = report.get("stage_labels")
        if not isinstance(sl_val, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and v in VALID_ROLES
            for k, v in sl_val.items()
        ):
            errors.append(
                "stage_labels missing, not an object, or contains invalid role values"
            )

        if not isinstance(report.get("summary"), str):
            errors.append("summary missing or not a string")

        if errors:
            report_fail("FR1", "; ".join(errors))
        else:
            report_pass("FR1")

    # Safe accessors for downstream checks
    design_name = report.get("design_name") if isinstance(report.get("design_name"), str) else None
    is_trojan_detected = report.get("is_trojan_detected")
    suspect_nodes = report.get("suspect_nodes") if isinstance(report.get("suspect_nodes"), list) else []
    suspect_nodes = [x for x in suspect_nodes if isinstance(x, str)]
    stage_labels = report.get("stage_labels") if isinstance(report.get("stage_labels"), dict) else {}
    stage_labels = {k: v for k, v in stage_labels.items() if isinstance(k, str) and isinstance(v, str)}
    summary = report.get("summary") if isinstance(report.get("summary"), str) else ""

    # ---- FR2: design_name matches module name ----
    m = re.search(r"module\s+(\w+)", netlist_text)
    module_name = m.group(1) if m else None
    if module_name is None:
        report_fail("FR2", "could not parse module name from inputs/netlist.v")
    elif design_name == module_name:
        report_pass("FR2")
    else:
        report_fail(
            "FR2",
            "design_name '{}' does not match module name '{}' in netlist.v".format(
                design_name, module_name
            ),
        )

    # ---- FR3: every referenced identifier exists in netlist.v ----
    idents = load_netlist_identifiers(netlist_text)
    valid_bases = {base_name(i) for i in idents}

    all_referenced = list(suspect_nodes) + list(stage_labels.keys())
    bad_nodes = [n for n in all_referenced if base_name(n) not in valid_bases]
    if bad_nodes:
        report_fail(
            "FR3",
            "referenced node(s) not found in netlist.v: {}".format(
                ", ".join(sorted(set(bad_nodes))[:5])
            ),
        )
    else:
        report_pass("FR3")

    # ---- FR4: summary length ----
    if isinstance(summary, str) and len(summary) >= 20:
        report_pass("FR4")
    else:
        report_fail("FR4", "summary is missing or shorter than 20 characters")

    # ---- SR1: is_trojan_detected must be true ----
    if is_trojan_detected is True:
        report_pass("SR1")
    else:
        report_fail("SR1", "is_trojan_detected is not true (got {!r})".format(is_trojan_detected))

    # ---- SR2: coverage of true trigger+payload nodes ----
    reported_bases = {base_name(n) for n in all_referenced if base_name(n) is not None}

    matched_true = 0
    for t in true_flat:
        tb = base_name(t)
        if tb in reported_bases:
            matched_true += 1

    coverage = (matched_true / len(true_flat)) if true_flat else 0.0
    if coverage >= coverage_threshold:
        report_pass("SR2", "coverage={:.2f}".format(coverage))
    else:
        report_fail(
            "SR2",
            "coverage {:.2f} below required threshold {:.2f} ({}/{} true nodes matched)".format(
                coverage, coverage_threshold, matched_true, len(true_flat)
            ),
        )

    # ---- SR3: correct role labeling per category ----
    categories = {
        "counter": counter_true,
        "comparator": comparator_true,
        "payload": payload_true,
    }
    category_bases = {cat: {base_name(t) for t in lst} for cat, lst in categories.items()}

    mislabeled = []
    satisfied = {cat: False for cat in categories}

    for key, val in stage_labels.items():
        kb = base_name(key)
        for cat, bases in category_bases.items():
            if kb in bases:
                if val != cat:
                    mislabeled.append((key, val, cat))
                else:
                    satisfied[cat] = True

    if mislabeled:
        detail = "; ".join(
            "'{}' labeled '{}' but should be '{}'".format(k, v, c) for k, v, c in mislabeled[:5]
        )
        report_fail("SR3", "mislabeled true node(s): {}".format(detail))
    else:
        missing_cats = [cat for cat, ok in satisfied.items() if not ok]
        if missing_cats:
            report_fail(
                "SR3",
                "no correctly-labeled node found for categor{}: {}".format(
                    "y" if len(missing_cats) == 1 else "ies", ", ".join(missing_cats)
                ),
            )
        else:
            report_pass("SR3")

    # ---- SR4: false positive rate on flagged nodes ----
    # fp_universe = every node reported as a suspect, or labeled with one of
    # the trojan-role categories (counter/comparator/payload) in stage_labels.
    trojan_labeled = {k for k, v in stage_labels.items() if v in TROJAN_ROLES}
    fp_universe = set(suspect_nodes) | trojan_labeled

    # A node is a false positive iff its base name is NOT part of the hidden
    # true trigger+payload node set. This catches BOTH invented/nonexistent
    # net names AND legitimate documented datapath nodes (e.g. sum_bit,
    # carry) that a submission mislabels/flags into a trojan category --
    # there is no separate "allowed prefix" carve-out.
    total = len(fp_universe)
    if total == 0:
        fpr = 0.0
        fp_count = 0
    else:
        fp_nodes = [n for n in fp_universe if base_name(n) not in true_bases]
        fp_count = len(fp_nodes)
        fpr = fp_count / total

    if fpr <= fpr_threshold:
        report_pass("SR4", "fpr={:.2f}".format(fpr))
    else:
        report_fail(
            "SR4",
            "false_positive_rate {:.2f} exceeds threshold {:.2f} ({}/{} flagged nodes not in true trigger/payload set)".format(
                fpr, fpr_threshold, fp_count, total
            ),
        )

    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()