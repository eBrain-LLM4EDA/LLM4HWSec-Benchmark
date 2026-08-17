#!/usr/bin/env python3
"""
evaluation/evaluate.py

Grades submission/trojan_report.json against ground truth derived
structurally from inputs/gate_netlist.v (and cross-referenced against
inputs/design_brief.md / inputs/testbench_reset_trace.v).

This script does not execute the submission as code -- it is a JSON
answer file. Structural facts about the netlist (flop instance names,
per-flop reset net resolution, inverter cells) are parsed directly from
inputs/gate_netlist.v so grading generalizes to any correct golden
report regardless of phrasing/ordering/extra fields.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "private"))
import rubric_terms  # noqa: E402

INPUTS_DIR = "inputs"
SUBMISSION_PATH = os.path.join("submission", "trojan_report.json")

NETLIST_PATH = os.path.join(INPUTS_DIR, "gate_netlist.v")
DESIGN_BRIEF_PATH = os.path.join(INPUTS_DIR, "design_brief.md")
TESTBENCH_PATH = os.path.join(INPUTS_DIR, "testbench_reset_trace.v")

TB_CROSSCHECK_PATH = os.path.join("evaluation", "tb_cross_check.v")

RESULTS = []  # list of (req_id, passed(bool), message)

# Requirements that gate the overall exit code. SR5 is intentionally
# excluded: per the hidden spec it is a bonus/consistency signal, not a
# primary correctness gate, so its failure alone must not fail an
# otherwise-fully-correct submission.
GATING_REQ_IDS = ("FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4")


def record(req_id, passed, message=""):
    RESULTS.append((req_id, passed, message))
    if passed:
        print("[TEST] PASS: %s" % req_id)
    else:
        print("[TEST] FAIL: %s: %s" % (req_id, message))


def fail_setup(path):
    print("[TEST] FAIL: SETUP: %s not found" % path)
    sys.exit(1)


def read_file(path):
    if not os.path.isfile(path):
        fail_setup(path)
    with open(path, "r") as f:
        return f.read()


# ---------------------------------------------------------------------
# Netlist structural parsing
# ---------------------------------------------------------------------

# Matches instantiations of the DFF primitive:
#   PRIM_DFF_SYNC u_ctrl_ff0 (.CLK(CLK), .RST_N(RSTN), .D(ctrl_ff0_d), .Q(ctrl_ff0_q));
DFF_INST_RE = re.compile(
    r'\bPRIM_DFF_SYNC\s+(\w+)\s*\(([^;]*?)\)\s*;',
    re.DOTALL,
)

# Matches instantiations of the inverter primitive:
#   PRIM_INV u_inv_rst_b (.a(RSTN), .y(rstn_b));
INV_INST_RE = re.compile(
    r'\bPRIM_INV\s+(\w+)\s*\(([^;]*?)\)\s*;',
    re.DOTALL,
)

# Generic named-port-connection extractor: .PORTNAME(NET)
PORT_CONN_RE = re.compile(r'\.\s*(\w+)\s*\(\s*([^()]*?)\s*\)')


def parse_port_connections(arglist_text):
    """Return dict portname -> net expression string, from a Verilog
    named-connection argument list body (text between the outer parens)."""
    conns = {}
    for m in PORT_CONN_RE.finditer(arglist_text):
        portname = m.group(1)
        net = m.group(2).strip()
        conns[portname] = net
    return conns


def parse_netlist_structure(netlist_text):
    """
    Returns:
      flop_names: set of all flip-flop instance names (PRIM_DFF_SYNC instances)
      flop_reset_net: dict instance_name -> resolved reset net expression string
                       (whatever is textually connected to .RST_N(...))
      inverter_outputs: dict output_net_name -> input_net_name for each
                        PRIM_INV instance (output is inverted copy of input)
    """
    flop_names = set()
    flop_reset_net = {}

    for m in DFF_INST_RE.finditer(netlist_text):
        inst_name = m.group(1)
        body = m.group(2)
        conns = parse_port_connections(body)
        flop_names.add(inst_name)
        rst_net = conns.get("RST_N", None)
        flop_reset_net[inst_name] = rst_net

    inverter_outputs = {}
    for m in INV_INST_RE.finditer(netlist_text):
        body = m.group(2)
        conns = parse_port_connections(body)
        in_net = conns.get("a", None)
        out_net = conns.get("y", None)
        if in_net is not None and out_net is not None:
            inverter_outputs[out_net] = in_net

    return flop_names, flop_reset_net, inverter_outputs


def find_primary_reset_net(netlist_text, flop_reset_net):
    """Determine the 'majority' / primary reset net name: the reset net
    expression used directly (not through an inverter output) by the
    largest number of flops. This is the netlist's RSTN-equivalent,
    determined structurally rather than by hardcoding the literal
    string 'RSTN', so grading is robust to any correct golden netlist
    naming."""
    from collections import Counter
    counts = Counter(net for net in flop_reset_net.values() if net is not None)
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def compute_true_suspect_set(flop_names, flop_reset_net, inverter_outputs, primary_reset_net):
    """A flop is a true suspect if its resolved RST_N connection net is
    NOT the primary reset net directly, i.e. it is instead the output of
    an inverter (or any net different from the primary reset net)."""
    suspects = set()
    for inst, net in flop_reset_net.items():
        if net is None:
            continue
        if net != primary_reset_net:
            suspects.add(inst)
    return suspects


# ---------------------------------------------------------------------
# Submission loading / FR checks
# ---------------------------------------------------------------------

def load_submission():
    if not os.path.isfile(SUBMISSION_PATH):
        fail_setup(SUBMISSION_PATH)
    with open(SUBMISSION_PATH, "r") as f:
        raw = f.read()
    try:
        data = json.loads(raw)
    except Exception as e:
        return None, "invalid JSON: %s" % str(e)
    return data, None


def check_fr1(data, parse_err):
    if data is None:
        record("FR1", False, "submission is not valid JSON: %s" % parse_err)
        return False
    if not isinstance(data, dict):
        record("FR1", False, "top-level JSON value is not an object")
        return False

    required = {
        "trojan_present": bool,
        "suspect_flops": list,
        "anomaly_description": str,
        "reset_net_summary": dict,
    }
    missing = [k for k in required if k not in data]
    if missing:
        record("FR1", False, "missing required field(s): %s" % ", ".join(missing))
        return False

    wrong_type = []
    for k, t in required.items():
        if not isinstance(data[k], t):
            wrong_type.append("%s (expected %s, got %s)" % (k, t.__name__, type(data[k]).__name__))
    if wrong_type:
        record("FR1", False, "field(s) with wrong type: %s" % "; ".join(wrong_type))
        return False

    # suspect_flops must be a list of strings
    if not all(isinstance(x, str) for x in data["suspect_flops"]):
        record("FR1", False, "suspect_flops must be an array of strings")
        return False

    # reset_net_summary must map to lists of strings
    for k, v in data["reset_net_summary"].items():
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            record("FR1", False, "reset_net_summary values must be arrays of strings (key=%s)" % k)
            return False

    record("FR1", True)
    return True


def check_fr2(data, flop_names):
    suspects = set(data["suspect_flops"])
    unknown = sorted(s for s in suspects if s not in flop_names)
    if unknown:
        record("FR2", False, "suspect_flops contains unknown instance name(s): %s" % ", ".join(unknown))
        return False
    record("FR2", True)
    return True


def check_fr3(data, flop_names):
    summary = data["reset_net_summary"]
    all_listed = []
    for key, flops in summary.items():
        all_listed.extend(flops)

    counts = {}
    for f in all_listed:
        counts[f] = counts.get(f, 0) + 1

    missing = sorted(flop_names - set(all_listed))
    double_counted = sorted(f for f, c in counts.items() if c > 1)
    unknown = sorted(set(all_listed) - flop_names)

    problems = []
    if missing:
        problems.append("omitted flop(s): %s" % ", ".join(missing))
    if double_counted:
        problems.append("double-counted flop(s): %s" % ", ".join(double_counted))
    if unknown:
        problems.append("unknown flop(s) referenced: %s" % ", ".join(unknown))

    if problems:
        record("FR3", False, "; ".join(problems))
        return False
    record("FR3", True)
    return True


def check_fr4(data):
    trojan_present = data["trojan_present"]
    desc = data["anomaly_description"]
    if trojan_present:
        if len(desc) < 20:
            record("FR4", False,
                   "trojan_present=true requires anomaly_description length>=20 (got %d)" % len(desc))
            return False
    else:
        if desc != "":
            record("FR4", False,
                   "trojan_present=false requires anomaly_description=='' (got length %d)" % len(desc))
            return False
    record("FR4", True)
    return True


# ---------------------------------------------------------------------
# SR checks
# ---------------------------------------------------------------------

def check_sr1(data, true_suspects):
    ground_truth_present = len(true_suspects) > 0
    submitted = data["trojan_present"]
    if submitted == ground_truth_present:
        record("SR1", True)
        return True
    record("SR1", False,
           "trojan_present=%s but ground truth is %s (anomalous reset wiring %s)"
           % (submitted, ground_truth_present,
              "present" if ground_truth_present else "absent"))
    return False


def check_sr2(data, true_suspects):
    submitted = set(data["suspect_flops"])
    if submitted == true_suspects:
        record("SR2", True)
        return True
    extra = sorted(submitted - true_suspects)
    missing = sorted(true_suspects - submitted)
    parts = []
    if extra:
        parts.append("extraneous: %s" % ", ".join(extra))
    if missing:
        parts.append("omitted: %s" % ", ".join(missing))
    record("SR2", False, "suspect_flops does not exactly match ground truth (%s)" % "; ".join(parts))
    return False


def check_sr3(data):
    desc = data.get("anomaly_description", "")
    if rubric_terms.has_inversion_claim(desc):
        record("SR3", True)
        return True
    record("SR3", False,
           "anomaly_description does not substantively describe an inverted/complemented "
           "reset polarity defect (must co-locate a reset term with a polarity/inversion term)")
    return False


def check_sr4(data, true_suspects, flop_names):
    summary = data["reset_net_summary"]

    if not true_suspects:
        # No ground-truth anomaly: SR4's purpose (separating a suspect
        # subset from the rest) is vacuous. Require FR3 coverage style
        # consistency: this is fine, pass.
        record("SR4", True)
        return True

    others = flop_names - true_suspects

    # Find group(s) containing at least one true suspect.
    groups_with_suspects = []
    for key, flops in summary.items():
        fset = set(flops)
        if fset & true_suspects:
            groups_with_suspects.append((key, fset))

    if not groups_with_suspects:
        record("SR4", False, "no reset_net_summary group contains any of the true suspect flops")
        return False

    # All true suspects must be covered by groups_with_suspects, and none
    # of those groups may contain a non-suspect flop.
    covered_suspects = set()
    for key, fset in groups_with_suspects:
        covered_suspects |= (fset & true_suspects)
        contaminating = fset & others
        if contaminating:
            record("SR4", False,
                   "group '%s' mixes true suspect flop(s) with non-suspect flop(s): %s"
                   % (key, ", ".join(sorted(contaminating))))
            return False

    missing_suspects = true_suspects - covered_suspects
    if missing_suspects:
        record("SR4", False,
               "true suspect flop(s) not grouped together/at all: %s" % ", ".join(sorted(missing_suspects)))
        return False

    # Additionally require they are NOT split across multiple groups that
    # are each clean (spec wants "a distinct net/signal key" -- i.e. one
    # group, not several). If split across multiple clean groups, that's
    # still not a single distinct key covering exactly the suspect set;
    # fail as insufficiently precise structural tracing.
    if len(groups_with_suspects) > 1:
        keys = [k for k, _ in groups_with_suspects]
        record("SR4", False,
               "true suspect flops are split across multiple reset_net_summary groups (%s) "
               "instead of a single distinct group" % ", ".join(keys))
        return False

    record("SR4", True)
    return True


def run_cmd(cmd, cwd=None, timeout=60):
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return None, "", "timeout"
    except Exception as e:
        return None, "", str(e)


CROSSCHECK_LINE_RE = re.compile(
    r'CROSSCHECK\s+(\w+)=([01]),\s*([01])'
)

# The documented reset value for every state-holding flop in this design
# (design_brief.md Section 3.3) is logic 0. A flop "fails to reset" if its
# post-reset sampled value does not equal this documented value, regardless
# of what its pre-reset value happened to be.
DOCUMENTED_RESET_VALUE = "0"


def check_sr5(data, true_suspects, flop_names):
    if not os.path.isfile(TB_CROSSCHECK_PATH):
        record("SR5", False, "SETUP-like: %s not found (harness file missing)" % TB_CROSSCHECK_PATH)
        return False
    if not os.path.isfile(NETLIST_PATH):
        record("SR5", False, "%s not found" % NETLIST_PATH)
        return False

    tmpdir = tempfile.mkdtemp(prefix="gtd_sr5_")
    sim_bin = os.path.join(tmpdir, "sim.vvp")

    rc, out, err = run_cmd(
        ["iverilog", "-g2012", "-o", sim_bin, NETLIST_PATH, TB_CROSSCHECK_PATH],
        timeout=60,
    )
    if rc is None:
        record("SR5", False, "iverilog compile timed out or could not be launched: %s" % err)
        return False
    if rc != 0:
        record("SR5", False, "iverilog compile failed: %s" % (err.strip()[-500:] if err else "unknown error"))
        return False

    rc, out, err = run_cmd(["vvp", sim_bin], timeout=60)
    if rc is None:
        record("SR5", False, "vvp simulation timed out or could not be launched: %s" % err)
        return False

    persistent = set()
    cleared = set()
    for m in CROSSCHECK_LINE_RE.finditer(out):
        name, pre, post = m.group(1), m.group(2), m.group(3)
        # A flop is classified as "persistent" (anomalous) purely on
        # whether it FAILED TO CLEAR to its documented reset value (0)
        # after the reset pulse -- independent of whether its pre-reset
        # value happened to equal its post-reset value. This matches the
        # design brief's documented reset value (logic 0 for every flop)
        # rather than a pre==post equality heuristic, which could
        # spuriously flag/miss flops depending on incidental stimulus
        # values.
        if post != DOCUMENTED_RESET_VALUE:
            persistent.add(name)
        else:
            cleared.add(name)

    observed_names = persistent | cleared
    if not observed_names:
        record("SR5", False,
               "no CROSSCHECK lines parsed from simulation output; cannot corroborate suspect set "
               "(stdout tail: %r)" % (out[-300:] if out else ""))
        return False

    # Only compare against flops that were actually observed (tb targets a
    # fixed canonical set of 8 role names present in this generated netlist).
    expected_persistent = true_suspects & observed_names
    submitted = set(data["suspect_flops"])

    if persistent == expected_persistent and submitted == persistent:
        record("SR5", True)
        return True

    problems = []
    if persistent != expected_persistent:
        problems.append(
            "simulation-observed persistent flops %s do not match structurally-derived "
            "suspect flops %s" % (sorted(persistent), sorted(expected_persistent))
        )
    if submitted != persistent:
        extra = sorted(submitted - persistent)
        missing = sorted(persistent - submitted)
        parts = []
        if extra:
            parts.append("submitted-but-not-persistent: %s" % extra)
        if missing:
            parts.append("persistent-but-not-submitted: %s" % missing)
        problems.append("submission suspect_flops does not match simulation-observed persistent set (%s)"
                         % "; ".join(parts))

    record("SR5", False, "; ".join(problems))
    return False


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():
    netlist_text = read_file(NETLIST_PATH)
    # design_brief.md and testbench_reset_trace.v are part of the required
    # reference artifact set; ensure they exist (used implicitly / for
    # completeness of the reference context), even though only the
    # netlist is parsed structurally here.
    read_file(DESIGN_BRIEF_PATH)
    read_file(TESTBENCH_PATH)

    flop_names, flop_reset_net, inverter_outputs = parse_netlist_structure(netlist_text)

    if not flop_names:
        print("[TEST] FAIL: SETUP: no flip-flop instances (PRIM_DFF_SYNC) could be parsed from %s" % NETLIST_PATH)
        sys.exit(1)

    primary_reset_net = find_primary_reset_net(netlist_text, flop_reset_net)
    true_suspects = compute_true_suspect_set(flop_names, flop_reset_net, inverter_outputs, primary_reset_net)

    data, parse_err = load_submission()

    fr1_ok = check_fr1(data, parse_err)

    if not fr1_ok:
        # Cannot safely evaluate downstream requirements on malformed data;
        # they all fail deterministically, referencing the FR1 failure.
        for req_id in ("FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4", "SR5"):
            record(req_id, False, "cannot evaluate: submission failed FR1 (malformed/missing required fields)")
        sys.exit(1)

    fr2_ok = check_fr2(data, flop_names)
    fr3_ok = check_fr3(data, flop_names)
    fr4_ok = check_fr4(data)

    sr1_ok = check_sr1(data, true_suspects)
    sr2_ok = check_sr2(data, true_suspects)
    sr3_ok = check_sr3(data)
    sr4_ok = check_sr4(data, true_suspects, flop_names)

    # SR5 is a bonus/corroboration signal (hidden_spec SR5 description):
    # it always emits its own PASS/FAIL line, but its result is
    # deliberately excluded from the gating set below so that a
    # simulation stimulus/classification quirk cannot, by itself, sink an
    # otherwise fully correct submission.
    check_sr5(data, true_suspects, flop_names)

    gating_results = {
        "FR1": fr1_ok,
        "FR2": fr2_ok,
        "FR3": fr3_ok,
        "FR4": fr4_ok,
        "SR1": sr1_ok,
        "SR2": sr2_ok,
        "SR3": sr3_ok,
        "SR4": sr4_ok,
    }

    gating_ok = all(gating_results[req_id] for req_id in GATING_REQ_IDS)
    sys.exit(0 if gating_ok else 1)


if __name__ == "__main__":
    main()