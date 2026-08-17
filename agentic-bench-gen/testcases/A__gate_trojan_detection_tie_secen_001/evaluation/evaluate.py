#!/usr/bin/env python3
"""
evaluate.py -- Gate-Level Trojan Detection grader.

Grades submission/trojan_report.json against structural facts parsed
from inputs/controller_netlist.v. See evaluation/README.md for details.
"""

import json
import os
import re
import sys

# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NETLIST_PATH = os.path.join(REPO_ROOT, "inputs", "controller_netlist.v")
CELL_LIB_PATH = os.path.join(REPO_ROOT, "inputs", "cell_library.v")
SUBMISSION_PATH = os.path.join(REPO_ROOT, "submission", "trojan_report.json")

# ----------------------------------------------------------------------
# Netlist parsing (self-contained; mirrors evaluation/netlist_utils.py
# helper but is duplicated here defensively so this file is fully
# functional standalone).
# ----------------------------------------------------------------------

# Fixed output-port-name table per cell type, driven by the public
# cell_library.v conventions (AND2/OR2/INV/BUF/DFF/TIEHI/TIELO/MUX2).
OUTPUT_PORT_NAME = {
    "AND2": "o",
    "OR2": "o",
    "INV": "o",
    "BUF": "o",
    "DFF": "q",
    "TIEHI": "o",
    "TIELO": "o",
    "MUX2": "o",
}

KNOWN_CELL_TYPES = set(OUTPUT_PORT_NAME.keys())

results = []  # list of (req_id, passed_bool, message)


def record(req_id, passed, reason=""):
    if passed:
        print("[TEST] PASS: {}".format(req_id))
    else:
        print("[TEST] FAIL: {}: {}".format(req_id, reason))
    results.append((req_id, passed, reason))


def fail_setup(path):
    print("[TEST] FAIL: SETUP: {} not found".format(path))
    sys.exit(1)


def strip_comments(text):
    # Remove // line comments and /* */ block comments.
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def parse_netlist(path):
    """
    Parse a flat structural Verilog netlist and return:
      instances:  dict[instance_name] -> cell_type
      net_driver: dict[net_name] -> instance_name (driving instance)
      net_loads:  dict[net_name] -> list[instance_name] (instances that
                  read this net on a non-output port)
    Handles multi-line instantiations, named (.port(net)) connections,
    and no-connect () ports. Purely structural; no hardcoded instance
    names beyond the fixed cell-type -> output-port-name table above.
    """
    with open(path, "r") as f:
        raw = f.read()
    text = strip_comments(raw)

    instances = {}
    net_driver = {}
    net_loads = {}

    # Match: CELLTYPE INSTNAME ( ... ) ;
    # Cell type must be one of the known types (word boundary), instance
    # name is a Verilog identifier, body is captured non-greedily up to
    # the matching ");" -- since bodies here don't contain nested
    # parens other than the port list itself, a non-greedy match to the
    # first ");" is sufficient and robust across multi-line formatting.
    inst_pattern = re.compile(
        r"\b(" + "|".join(sorted(KNOWN_CELL_TYPES)) + r")\s+"
        r"([A-Za-z_][A-Za-z0-9_$]*)\s*"
        r"\(([^;]*?)\)\s*;",
        re.DOTALL,
    )

    for m in inst_pattern.finditer(text):
        cell_type = m.group(1)
        inst_name = m.group(2)
        port_body = m.group(3)

        instances[inst_name] = cell_type
        out_port = OUTPUT_PORT_NAME.get(cell_type)

        # Named port connections: .portname ( net_expr )
        # net_expr may be empty (no-connect) or contain a bit-select.
        port_conn_pattern = re.compile(
            r"\.\s*([A-Za-z_][A-Za-z0-9_$]*)\s*\(\s*([^()]*?)\s*\)"
        )
        found_named = False
        for pm in port_conn_pattern.finditer(port_body):
            found_named = True
            port_name = pm.group(1)
            net_expr = pm.group(2).strip()
            if net_expr == "":
                continue  # no-connect
            # Extract base net identifier(s) referenced; a net_expr
            # could itself be a simple identifier, a bit-select
            # identifier[N], or a concatenation {a,b,...}. We take all
            # identifiers referenced (ignoring numeric literals) so
            # each contributes to driver/load maps appropriately.
            net_names = re.findall(r"[A-Za-z_][A-Za-z0-9_$]*(?:\[\d+\])?", net_expr)
            for net in net_names:
                base_net = net.split("[")[0]
                full_net = net
                if port_name == out_port:
                    net_driver[full_net] = inst_name
                    net_driver.setdefault(base_net, inst_name)
                else:
                    net_loads.setdefault(full_net, []).append(inst_name)
                    net_loads.setdefault(base_net, []).append(inst_name)

        if not found_named:
            # Positional connections (rare in this generator, but
            # handle defensively): split on top-level commas.
            parts = [p.strip() for p in port_body.split(",") if p.strip() != ""]
            for idx, net_expr in enumerate(parts):
                net_names = re.findall(r"[A-Za-z_][A-Za-z0-9_$]*(?:\[\d+\])?", net_expr)
                for net in net_names:
                    base_net = net.split("[")[0]
                    # Without a port-name mapping we cannot reliably
                    # tell output vs input positionally beyond "first
                    # port is output" convention used by this cell
                    # library; treat idx==0 as output.
                    if idx == 0:
                        net_driver[net] = inst_name
                        net_driver.setdefault(base_net, inst_name)
                    else:
                        net_loads.setdefault(net, []).append(inst_name)
                        net_loads.setdefault(base_net, []).append(inst_name)

    return instances, net_driver, net_loads


# ----------------------------------------------------------------------
# Load netlist
# ----------------------------------------------------------------------

if not os.path.isfile(NETLIST_PATH):
    fail_setup("inputs/controller_netlist.v")
if not os.path.isfile(CELL_LIB_PATH):
    fail_setup("inputs/cell_library.v")

try:
    instances, net_driver, net_loads = parse_netlist(NETLIST_PATH)
except Exception as e:
    print("[TEST] FAIL: SETUP: failed to parse inputs/controller_netlist.v: {}".format(e))
    sys.exit(1)

# ----------------------------------------------------------------------
# Ground-truth oracle values, pinned by the public interface (the only
# net named secure_enable and the only tie-cell instance in this
# design). We independently re-verify these facts hold in the freshly
# parsed netlist before using them as the oracle, so a mismatched or
# regenerated netlist surfaces as a SETUP failure rather than silently
# mis-grading.
# ----------------------------------------------------------------------

EXPECTED_DRIVER_INSTANCE = "U_TIE_SECEN"
EXPECTED_COMPROMISED_NET = "secure_enable"

oracle_driver_of_secen = net_driver.get(EXPECTED_COMPROMISED_NET)
if oracle_driver_of_secen is None:
    print(
        "[TEST] FAIL: SETUP: could not determine driver of net '{}' in "
        "inputs/controller_netlist.v".format(EXPECTED_COMPROMISED_NET)
    )
    sys.exit(1)

if oracle_driver_of_secen != EXPECTED_DRIVER_INSTANCE:
    print(
        "[TEST] FAIL: SETUP: expected driver of net '{}' to be instance "
        "'{}' per pinned ground truth, but parsed netlist shows driver "
        "'{}'".format(
            EXPECTED_COMPROMISED_NET, EXPECTED_DRIVER_INSTANCE, oracle_driver_of_secen
        )
    )
    sys.exit(1)

oracle_driver_celltype = instances.get(EXPECTED_DRIVER_INSTANCE)
if oracle_driver_celltype not in ("TIEHI", "TIELO"):
    print(
        "[TEST] FAIL: SETUP: expected instance '{}' to be a TIEHI/TIELO "
        "constant-tie cell per pinned ground truth, but parsed cell type "
        "is '{}'".format(EXPECTED_DRIVER_INSTANCE, oracle_driver_celltype)
    )
    sys.exit(1)

# Determine orphan candidates structurally: any instance whose output
# net has zero recorded loads. This is used for SR3 partial credit.
orphan_candidates = set()
for inst_name, cell_type in instances.items():
    out_port = OUTPUT_PORT_NAME.get(cell_type)
    if out_port is None:
        continue
    # Find the net this instance drives (reverse lookup via net_driver).
    driven_nets = [n for n, drv in net_driver.items() if drv == inst_name]
    has_load = False
    for n in driven_nets:
        if net_loads.get(n):
            has_load = True
            break
    if driven_nets and not has_load:
        orphan_candidates.add(inst_name)

# The two ground-truth orphan cone instances must actually be orphaned
# in the parsed netlist (else SETUP mismatch, since this is a pinned
# structural fact about the shipped design).
EXPECTED_ORPHAN_CANDIDATES = {"u_sec_and1", "u_sec_or2"}
missing_orphans = EXPECTED_ORPHAN_CANDIDATES - set(instances.keys())
if missing_orphans:
    print(
        "[TEST] FAIL: SETUP: expected instances {} not found in parsed "
        "netlist".format(sorted(missing_orphans))
    )
    sys.exit(1)

# It's fine if the actual orphan analysis differs slightly (e.g. due to
# parsing edge cases) -- but at least one of the two must show as
# orphaned per structural analysis, matching the ground-truth design
# intent. We don't hard-fail SETUP on this since it's a partial-credit
# requirement's oracle, not a security oracle; downstream SR3 check
# uses whichever of EXPECTED_ORPHAN_CANDIDATES intersect orphan_candidates,
# falling back to the full expected set if structural detection found
# neither (defensive, avoids a parser edge case blocking grading).
effective_orphan_set = orphan_candidates & EXPECTED_ORPHAN_CANDIDATES
if not effective_orphan_set:
    effective_orphan_set = set(EXPECTED_ORPHAN_CANDIDATES)

# ----------------------------------------------------------------------
# Load submission
# ----------------------------------------------------------------------

if not os.path.isfile(SUBMISSION_PATH):
    fail_setup("submission/trojan_report.json")

with open(SUBMISSION_PATH, "r") as f:
    raw_submission = f.read()

report = None
json_parse_error = None
try:
    report = json.loads(raw_submission)
except Exception as e:
    json_parse_error = str(e)

# ----------------------------------------------------------------------
# FR1: valid JSON with required top-level fields, correctly typed.
# ----------------------------------------------------------------------

fr1_pass = True
fr1_reason = ""

if json_parse_error is not None:
    fr1_pass = False
    fr1_reason = "trojan_report.json is not valid JSON: {}".format(json_parse_error)
elif not isinstance(report, dict):
    fr1_pass = False
    fr1_reason = "trojan_report.json top-level value is not a JSON object"
else:
    verdict = report.get("verdict")
    suspect_instances = report.get("suspect_instances")
    rationale = report.get("rationale")

    if not isinstance(verdict, str) or verdict.strip().lower() not in (
        "trojan_detected",
        "clean",
    ):
        fr1_pass = False
        fr1_reason = (
            "field 'verdict' missing or not one of 'trojan_detected'/'clean' "
            "(got: {!r})".format(verdict)
        )
    elif not isinstance(suspect_instances, list) or not all(
        isinstance(x, str) for x in suspect_instances
    ):
        fr1_pass = False
        fr1_reason = "field 'suspect_instances' missing or not an array of strings"
    elif not isinstance(rationale, str) or rationale.strip() == "":
        fr1_pass = False
        fr1_reason = "field 'rationale' missing, empty, or not a string"

record("FR1", fr1_pass, fr1_reason)

# If JSON didn't even parse or isn't a dict, all subsequent checks must
# still emit a definitive FAIL (never SKIP).
if not isinstance(report, dict):
    reason = "trojan_report.json did not parse as a JSON object: {}".format(
        json_parse_error or "not a dict"
    )
    record("FR2", False, reason)
    record("FR3", False, reason)
    record("FR4", False, reason)
    record("SR1", False, reason)
    record("SR2", False, reason)
    record("SR3", False, reason)
    record("SR4", False, reason)

    any_fail = any(not p for _, p, _ in results)
    sys.exit(1 if any_fail else 0)

# ----------------------------------------------------------------------
# FR2: every suspect_instances entry exists in controller_netlist.v
# ----------------------------------------------------------------------

suspect_instances = report.get("suspect_instances")
if not isinstance(suspect_instances, list):
    record("FR2", False, "field 'suspect_instances' missing or not a list")
else:
    bad = None
    for name in suspect_instances:
        if not isinstance(name, str) or name not in instances:
            bad = name
            break
    if bad is not None:
        record(
            "FR2",
            False,
            "suspect_instances entry {!r} does not match any instance name "
            "in controller_netlist.v".format(bad),
        )
    else:
        record("FR2", True)

# ----------------------------------------------------------------------
# FR3: if verdict == trojan_detected, compromised_net + driver_instance
# must be present, non-empty strings.
# ----------------------------------------------------------------------

verdict_raw = report.get("verdict")
verdict_norm = verdict_raw.strip().lower() if isinstance(verdict_raw, str) else ""

compromised_net = report.get("compromised_net")
driver_instance = report.get("driver_instance")

if verdict_norm == "trojan_detected":
    fr3_pass = True
    fr3_reason = ""
    if not isinstance(compromised_net, str) or compromised_net.strip() == "":
        fr3_pass = False
        fr3_reason = "verdict is trojan_detected but 'compromised_net' missing/empty"
    elif not isinstance(driver_instance, str) or driver_instance.strip() == "":
        fr3_pass = False
        fr3_reason = "verdict is trojan_detected but 'driver_instance' missing/empty"
    record("FR3", fr3_pass, fr3_reason)
else:
    # Conditional requirement: vacuously satisfied when verdict is not
    # trojan_detected.
    record("FR3", True)

# ----------------------------------------------------------------------
# FR4: orphaned_logic, if present, must be a list of strings each
# matching a real instance name.
# ----------------------------------------------------------------------

orphaned_logic = report.get("orphaned_logic")
if orphaned_logic is None:
    record("FR4", True)
elif not isinstance(orphaned_logic, list) or not all(
    isinstance(x, str) for x in orphaned_logic
):
    record("FR4", False, "field 'orphaned_logic' present but not an array of strings")
else:
    bad = None
    for name in orphaned_logic:
        if name not in instances:
            bad = name
            break
    if bad is not None:
        record(
            "FR4",
            False,
            "orphaned_logic entry {!r} does not match any instance name in "
            "controller_netlist.v".format(bad),
        )
    else:
        record("FR4", True)

# ----------------------------------------------------------------------
# SR1: correctly identify secure_enable is driven by a constant-tie
# cell (TIEHI/TIELO) rather than combinational logic; cross-checked
# against driver_instance/compromised_net fields for exact match.
# ----------------------------------------------------------------------

sr1_pass = (
    isinstance(compromised_net, str)
    and compromised_net.strip() == EXPECTED_COMPROMISED_NET
    and isinstance(driver_instance, str)
    and driver_instance.strip() == EXPECTED_DRIVER_INSTANCE
    and verdict_norm == "trojan_detected"
)
if sr1_pass:
    record("SR1", True)
else:
    reasons = []
    if verdict_norm != "trojan_detected":
        reasons.append("verdict is not 'trojan_detected'")
    if not (isinstance(compromised_net, str) and compromised_net.strip() == EXPECTED_COMPROMISED_NET):
        reasons.append(
            "compromised_net {!r} != expected {!r}".format(
                compromised_net, EXPECTED_COMPROMISED_NET
            )
        )
    if not (isinstance(driver_instance, str) and driver_instance.strip() == EXPECTED_DRIVER_INSTANCE):
        reasons.append(
            "driver_instance {!r} != expected {!r}".format(
                driver_instance, EXPECTED_DRIVER_INSTANCE
            )
        )
    record("SR1", False, "; ".join(reasons))

# ----------------------------------------------------------------------
# SR2: driver_instance must exactly name U_TIE_SECEN, not merely flag
# the net.
# ----------------------------------------------------------------------

sr2_pass = isinstance(driver_instance, str) and driver_instance.strip() == EXPECTED_DRIVER_INSTANCE
record(
    "SR2",
    sr2_pass,
    "" if sr2_pass else "driver_instance field missing or does not exactly equal '{}' (got: {!r})".format(
        EXPECTED_DRIVER_INSTANCE, driver_instance
    ),
)

# ----------------------------------------------------------------------
# SR3: orphaned_logic should include at least one of the orphaned
# intended-driver cone instances (partial credit; single PASS/FAIL
# marker, never SKIP).
# ----------------------------------------------------------------------

if isinstance(orphaned_logic, list):
    overlap = set(x for x in orphaned_logic if isinstance(x, str)) & effective_orphan_set
    sr3_pass = len(overlap) > 0
else:
    sr3_pass = False

record(
    "SR3",
    sr3_pass,
    "" if sr3_pass else (
        "orphaned_logic missing/empty or does not include any of the "
        "orphaned intended-driver cone instances {}".format(sorted(effective_orphan_set))
    ),
)

# ----------------------------------------------------------------------
# SR4: verdict must be exactly 'trojan_detected' (case-insensitive),
# not 'clean' or hedged.
# ----------------------------------------------------------------------

sr4_pass = verdict_norm == "trojan_detected"
record(
    "SR4",
    sr4_pass,
    "" if sr4_pass else "verdict is {!r}, expected 'trojan_detected'".format(verdict_raw),
)

# ----------------------------------------------------------------------
# Final exit code
# ----------------------------------------------------------------------

any_fail = any(not passed for _, passed, _ in results)
sys.exit(1 if any_fail else 0)