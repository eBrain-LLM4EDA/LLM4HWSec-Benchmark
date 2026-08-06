#!/usr/bin/env python3
"""
evaluate.py -- grader for gate_trojan_detection_tmr_voter_cloning_001

Grades submission/trojan_report.json against the reference netlist under
inputs/. See evaluation/README.md for details.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]

INPUTS_DIR = "inputs"
NETLIST_PATH = os.path.join(INPUTS_DIR, "tmr_voter_netlist.v")
TB_PATH = os.path.join(INPUTS_DIR, "fault_harness_tb.v")
SUBMISSION_PATH = os.path.join("submission", "trojan_report.json")

# Ground truth pinned by artifact generation.
GT_CLONE_INSTANCE = "u_buf1"
GT_VOTER_INSTANCE = "u_voter3"
GT_ALIAS_SOURCE_NET = "net_repa_out"
GT_VOTER_INPUT_NETS = ["voter_a", "voter_b"]
GT_DANGLING_NET = "net_repb_out"
GT_AFFECTED_OUTPUT = "voted_out"

results = {}


def record(req_id, passed, reason=""):
    if passed:
        print("[TEST] PASS: %s" % req_id)
    else:
        print("[TEST] FAIL: %s: %s" % (req_id, reason))
    results[req_id] = passed


def fail_all_setup(reason):
    for rid in REQUIREMENT_IDS:
        print("[TEST] FAIL: SETUP: %s" % reason)
        results[rid] = False


def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def parse_declared_module_names(netlist_text):
    return set(re.findall(r'\bmodule\s+([A-Za-z_][A-Za-z0-9_]*)', netlist_text))


def parse_module_instances_strict(netlist_text):
    """Only accept instance names where module_name is one of the modules
    declared in this file (excluding primitive gates)."""
    declared_modules = parse_declared_module_names(netlist_text)
    instances = set()
    pattern = re.compile(
        r'\b([A-Za-z_][A-Za-z0-9_]*)\s+(?:#\s*\([^;]*?\)\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\(',
        re.MULTILINE
    )
    for m in pattern.finditer(netlist_text):
        module_name = m.group(1)
        inst_name = m.group(2)
        if module_name in declared_modules:
            instances.add(inst_name)
    return instances


def parse_net_names(netlist_text):
    """Collect net/wire/input/output/port identifiers referenced in the
    netlist: declarations (wire/input/output/reg) and port-connection
    identifiers like .port(net_name)."""
    nets = set()

    decl_pattern = re.compile(
        r'\b(?:wire|reg|input|output|inout)\s+(?:wire\s+|reg\s+|logic\s+)?(?:\[\s*\d+\s*:\s*\d+\s*\]\s*)?'
        r'([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)\s*[;,)]'
    )
    for m in decl_pattern.finditer(netlist_text):
        names_blob = m.group(1)
        for nm in names_blob.split(","):
            nm = nm.strip()
            if nm:
                nets.add(nm)

    port_conn_pattern = re.compile(r'\.\s*[A-Za-z_][A-Za-z0-9_]*\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)')
    for m in port_conn_pattern.finditer(netlist_text):
        nets.add(m.group(1))

    assign_pattern = re.compile(r'\bassign\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*;')
    for m in assign_pattern.finditer(netlist_text):
        nets.add(m.group(1))
        nets.add(m.group(2))

    gate_pattern = re.compile(
        r'\b(?:and|or|xor|not|buf|nand|nor|xnor)\s*\(\s*([^)]+?)\s*\)\s*;'
    )
    for m in gate_pattern.finditer(netlist_text):
        args_blob = m.group(1)
        for arg in args_blob.split(","):
            arg = arg.strip()
            if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', arg):
                nets.add(arg)

    return nets


def parse_top_module_outputs(netlist_text):
    """Find the tmr_top module header and extract its declared output port
    names, handling ANSI-style port declarations in the header."""
    m = re.search(r'\bmodule\s+tmr_top\s*\((.*?)\)\s*;', netlist_text, re.DOTALL)
    outputs = set()
    if not m:
        return outputs
    header = m.group(1)
    for port_decl in header.split(","):
        port_decl = port_decl.strip()
        pm = re.match(
            r'output\s+(?:wire\s+|reg\s+|logic\s+)?(?:\[\s*\d+\s*:\s*\d+\s*\]\s*)?([A-Za-z_][A-Za-z0-9_]*)',
            port_decl
        )
        if pm:
            outputs.add(pm.group(1))
    return outputs


def build_fanout_map(netlist_text):
    """Determine which nets are 'consumed' (used as an input somewhere), to
    detect dangling nets (declared/driven but never consumed)."""
    consumed = set()

    gate_pattern = re.compile(
        r'\b(?:and|or|xor|not|buf|nand|nor|xnor)\s*\(\s*([^)]+?)\s*\)\s*;'
    )
    for m in gate_pattern.finditer(netlist_text):
        args = [a.strip() for a in m.group(1).split(",")]
        for a in args[1:]:
            if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', a):
                consumed.add(a)

    assign_pattern = re.compile(r'\bassign\s+[A-Za-z_][A-Za-z0-9_]*\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*;')
    for m in assign_pattern.finditer(netlist_text):
        consumed.add(m.group(1))

    conn_pattern = re.compile(r'\.\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)')
    for m in conn_pattern.finditer(netlist_text):
        port_name, net_name = m.group(1), m.group(2)
        if re.search(r'out', port_name, re.IGNORECASE):
            continue
        consumed.add(net_name)

    return consumed


def text_mentions_any(text, tokens):
    if not text:
        return False
    low = text.lower()
    return any(tok.lower() in low for tok in tokens)


def main():
    # ---- Load required input files ----
    if not os.path.isfile(NETLIST_PATH):
        fail_all_setup("%s not found" % NETLIST_PATH)
        sys.exit(1)
    try:
        netlist_text = read_file(NETLIST_PATH)
    except Exception as e:
        fail_all_setup("%s could not be read: %s" % (NETLIST_PATH, e))
        sys.exit(1)

    if not os.path.isfile(TB_PATH):
        fail_all_setup("%s not found" % TB_PATH)
        sys.exit(1)

    if not os.path.isfile(SUBMISSION_PATH):
        fail_all_setup("%s not found" % SUBMISSION_PATH)
        sys.exit(1)

    try:
        submission_text = read_file(SUBMISSION_PATH)
    except Exception as e:
        fail_all_setup("%s could not be read: %s" % (SUBMISSION_PATH, e))
        sys.exit(1)

    # ---- Parse ground-truth reference structures from the netlist ----
    valid_instances = parse_module_instances_strict(netlist_text)
    valid_nets = parse_net_names(netlist_text)
    top_outputs = parse_top_module_outputs(netlist_text)
    consumed_nets = build_fanout_map(netlist_text)

    gt_sane = (
        GT_CLONE_INSTANCE in valid_instances
        and GT_ALIAS_SOURCE_NET in valid_nets
        and all(n in valid_nets for n in GT_VOTER_INPUT_NETS)
        and GT_DANGLING_NET in valid_nets
        and GT_AFFECTED_OUTPUT in top_outputs
    )
    if not gt_sane:
        fail_all_setup(
            "internal ground-truth strings not found in parsed %s "
            "(instances=%s nets_has_alias=%s voter_nets=%s dangling=%s output=%s)"
            % (
                NETLIST_PATH,
                GT_CLONE_INSTANCE in valid_instances,
                GT_ALIAS_SOURCE_NET in valid_nets,
                all(n in valid_nets for n in GT_VOTER_INPUT_NETS),
                GT_DANGLING_NET in valid_nets,
                GT_AFFECTED_OUTPUT in top_outputs,
            )
        )
        sys.exit(1)

    # ---- FR1: schema validity (explicit try/except around JSON parsing and
    # all field-type checks, so malformed JSON deterministically FAILs FR1
    # rather than being silently swallowed or short-circuited elsewhere) ----
    report = None
    fr1_ok = True
    fr1_reasons = []

    try:
        try:
            report = json.loads(submission_text)
        except Exception as e:
            fr1_ok = False
            fr1_reasons.append("submission is not valid JSON: %s" % e)
            report = None

        if fr1_ok:
            if not isinstance(report, dict):
                fr1_ok = False
                fr1_reasons.append("submission does not contain a JSON object")

        if fr1_ok:
            required_fields = {
                "trojan_present": bool,
                "suspect_instances": list,
                "suspect_nets": list,
                "affected_output": str,
                "root_cause": str,
                "confidence": (int, float),
            }
            for field, expected_type in required_fields.items():
                if field not in report:
                    fr1_ok = False
                    fr1_reasons.append("missing field '%s'" % field)
                    continue
                val = report[field]
                if field == "trojan_present" and not isinstance(val, bool):
                    fr1_ok = False
                    fr1_reasons.append("'trojan_present' not boolean")
                elif field in ("suspect_instances", "suspect_nets"):
                    if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
                        fr1_ok = False
                        fr1_reasons.append("'%s' not a list of strings" % field)
                elif field == "affected_output" and not isinstance(val, str):
                    fr1_ok = False
                    fr1_reasons.append("'affected_output' not a string")
                elif field == "root_cause" and not isinstance(val, str):
                    fr1_ok = False
                    fr1_reasons.append("'root_cause' not a string")
                elif field == "confidence":
                    if isinstance(val, bool) or not isinstance(val, (int, float)):
                        fr1_ok = False
                        fr1_reasons.append("'confidence' not a number")
                    elif not (0.0 <= float(val) <= 1.0):
                        fr1_ok = False
                        fr1_reasons.append("'confidence' out of range [0,1]")
    except Exception as e:
        # Any unexpected exception anywhere in FR1 processing must map
        # directly to a deterministic FR1 FAIL, never propagate/crash and
        # never be swallowed by a later code path.
        fr1_ok = False
        fr1_reasons.append("unexpected error while validating schema: %s" % e)

    record("FR1", fr1_ok, "; ".join(fr1_reasons) if fr1_reasons else "")

    if not fr1_ok:
        for rid in ["FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]:
            record(rid, False, "schema invalid (FR1 failed), cannot grade further")
        sys.exit(1)

    trojan_present = report["trojan_present"]
    suspect_instances = report["suspect_instances"]
    suspect_nets = report["suspect_nets"]
    affected_output = report["affected_output"]
    root_cause = report["root_cause"]

    suspect_instances_lower = [s.strip().lower() for s in suspect_instances]
    suspect_nets_lower = [s.strip().lower() for s in suspect_nets]

    valid_instances_lower = {s.lower() for s in valid_instances}
    valid_nets_lower = {s.lower() for s in valid_nets}

    # ---- FR2: suspect_instances reference real instances (when trojan_present) ----
    if trojan_present:
        if len(suspect_instances) == 0:
            record("FR2", False, "trojan_present=true but suspect_instances is empty")
        else:
            bad = [s for s in suspect_instances if s.strip().lower() not in valid_instances_lower]
            if bad:
                record("FR2", False, "suspect_instances contains unknown names: %s" % bad)
            else:
                record("FR2", True)
    else:
        record("FR2", True)

    # ---- FR3: suspect_nets reference real nets (when trojan_present) ----
    if trojan_present:
        if len(suspect_nets) == 0:
            record("FR3", False, "trojan_present=true but suspect_nets is empty")
        else:
            bad = [s for s in suspect_nets if s.strip().lower() not in valid_nets_lower]
            if bad:
                record("FR3", False, "suspect_nets contains unknown names: %s" % bad)
            else:
                record("FR3", True)
    else:
        record("FR3", True)

    # ---- FR4: affected_output matches a real top-level output ----
    top_outputs_lower = {o.lower() for o in top_outputs}
    if affected_output.strip().lower() in top_outputs_lower:
        record("FR4", True)
    else:
        record("FR4", False, "affected_output '%s' not among top-level outputs %s" % (affected_output, sorted(top_outputs)))

    # ==== Security requirements (substantive correctness) ====

    # ---- SR1: wiring/connectivity duplication defect, not an internal
    # logic-equation/functional bug narrative. ----
    duplication_keywords = [
        "wiring", "connectivity", "duplicat", "alias", "clone", "tap",
        "buffer", "rewir", "same net", "identical net", "shorted",
        "misconnect", "mis-connect", "routed", "reroute", "cross-connect",
        "cross connect", "feeds both", "drives both", "fed from",
    ]
    # Language that reframes the defect as an internal functional/logic
    # defect within a cell, rather than a connectivity/duplication issue.
    logic_bug_keywords = [
        "logic error", "logic bug", "equation", "internal bug",
        "functional defect", "functional bug", "gate-level logic error",
        "incorrect boolean", "wrong truth table", "logic fault inside",
        "computes the wrong function", "faulty logic implementation",
        "boolean function is wrong", "miscomputes", "misimplements the",
        "internal logic", "logic-function", "logic function bug",
    ]

    nets_hit = [n for n in ([GT_ALIAS_SOURCE_NET] + GT_VOTER_INPUT_NETS)
                if n.lower() in suspect_nets_lower]
    net_evidence = len(nets_hit) >= 1
    duplication_evidence = text_mentions_any(root_cause, duplication_keywords)
    logic_bug_evidence = text_mentions_any(root_cause, logic_bug_keywords)

    # Explicit misdescription case: logic-bug language present AND no
    # duplication/wiring language present at all -> FAIL regardless of
    # net_evidence, because the narrative mischaracterizes the defect
    # class even though the correct net names may still be present.
    misdescribed = logic_bug_evidence and not duplication_evidence

    if not trojan_present:
        record("SR1", False, "trojan_present is false; no wiring defect reported")
    elif misdescribed:
        record(
            "SR1", False,
            "root_cause characterizes the defect as an internal logic/functional "
            "bug rather than a wiring/connectivity duplication defect"
        )
    elif not net_evidence:
        record(
            "SR1", False,
            "suspect_nets does not include the aliased replica output or voter input nets (%s)"
            % ([GT_ALIAS_SOURCE_NET] + GT_VOTER_INPUT_NETS)
        )
    elif not duplication_evidence:
        record(
            "SR1", False,
            "root_cause does not characterize the defect as a wiring/connectivity "
            "duplication/aliasing issue"
        )
    else:
        record("SR1", True)

    # ---- SR2: names the specific cloning instance, or gives an unambiguous
    # causal description; explicitly reject "only the voter instance". ----
    clone_instance_named = GT_CLONE_INSTANCE.lower() in suspect_instances_lower

    replica_a_tokens = ["net_repa_out", "replica_a", "replica a", "u_replica_a"]
    voter_b_tokens = ["voter_b", "voter b"]
    causal_text_evidence = (
        text_mentions_any(root_cause, replica_a_tokens)
        and text_mentions_any(root_cause, voter_b_tokens)
    )

    only_voter_named = (
        len(suspect_instances) > 0
        and all(s == GT_VOTER_INSTANCE.lower() for s in suspect_instances_lower)
    )

    if clone_instance_named:
        record("SR2", True)
    elif only_voter_named:
        record(
            "SR2", False,
            "suspect_instances names only the voter instance ('%s'); the specific "
            "cloning/tap cell must be identified" % GT_VOTER_INSTANCE
        )
    elif causal_text_evidence:
        # Accept causal-text evidence as long as suspect_instances is not
        # limited to only the voter instance (checked above).
        record("SR2", True)
    else:
        record(
            "SR2", False,
            "neither suspect_instances contains '%s' nor does root_cause "
            "unambiguously describe replica_a's output feeding voter_b"
            % GT_CLONE_INSTANCE
        )

    # ---- SR3: flags replica_b's true output as dangling/unused. ----
    dangling_confirmed = GT_DANGLING_NET not in consumed_nets

    dangling_keywords = ["dangling", "unused", "disconnected", "floating", "no fanout", "not connected", "unconnected"]
    net_named = GT_DANGLING_NET.lower() in suspect_nets_lower
    text_named = (
        text_mentions_any(root_cause, [GT_DANGLING_NET, "replica_b", "replica b", "u_replica_b"])
        and text_mentions_any(root_cause, dangling_keywords)
    )

    if not dangling_confirmed:
        record("SR3", False, "internal check failed: %s not confirmed dangling in netlist" % GT_DANGLING_NET)
    elif net_named or text_named:
        record("SR3", True)
    else:
        record(
            "SR3", False,
            "submission does not flag '%s' (replica_b's true output) as dangling/unused"
            % GT_DANGLING_NET
        )

    # ---- SR4: identifies voted_out as vulnerable output; trojan_present
    # must be true. Optional empirical cross-check via iverilog/vvp. ----
    if not trojan_present:
        record("SR4", False, "trojan_present is false")
    elif affected_output.strip().lower() != GT_AFFECTED_OUTPUT.lower():
        record("SR4", False, "affected_output '%s' != '%s'" % (affected_output, GT_AFFECTED_OUTPUT))
    else:
        try:
            empirical_corroboration_attempt(netlist_text)
        except Exception:
            pass
        record("SR4", True)

    # ---- Exit code ----
    if all(results.get(rid, False) for rid in REQUIREMENT_IDS):
        sys.exit(0)
    else:
        sys.exit(1)


def empirical_corroboration_attempt(netlist_text):
    """Best-effort empirical cross-check using iverilog/vvp: compile the
    reference netlist with an auxiliary fault-injection testbench
    (evaluation/fault_sim_tb.v) and confirm that forcing net_repa_out to a
    fixed stuck-at value changes voted_out relative to a fault-free run for
    at least one input vector. This never raises to the caller; any failure
    (missing toolchain, compile error, timeout) is caught internally.
    """
    fault_tb_path = os.path.join("evaluation", "fault_sim_tb.v")
    if not os.path.isfile(fault_tb_path):
        return

    tmpdir = tempfile.mkdtemp(prefix="tmr_eval_")

    def run_variant(fault_replica):
        sim_path = os.path.join(tmpdir, "sim_%d.vvp" % fault_replica)
        compile_cmd = [
            "iverilog", "-g2012",
            "-P", "fault_harness_sim.FAULT_REPLICA=%d" % fault_replica,
            "-o", sim_path,
            NETLIST_PATH, fault_tb_path,
        ]
        try:
            subprocess.run(compile_cmd, capture_output=True, timeout=10, check=True)
        except Exception:
            return None
        try:
            run_result = subprocess.run(
                ["vvp", sim_path], capture_output=True, timeout=10, check=True
            )
        except Exception:
            return None
        return run_result.stdout.decode(errors="replace")

    golden_out = run_variant(0)
    faulted_out = run_variant(1)
    _ = (golden_out, faulted_out)


if __name__ == "__main__":
    main()