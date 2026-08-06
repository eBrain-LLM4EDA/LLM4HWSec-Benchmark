#!/usr/bin/env python3
"""
evaluate.py -- Gate-level Trojan Detection grader for the tamper-monitoring
audit subsystem (audit_top).

Reads:
    inputs/audit_module_netlist.v   (structural reference; ground-truth netlist)
    inputs/design_brief.md          (not parsed structurally, present for completeness)
    inputs/port_map.txt             (not parsed structurally, present for completeness)
    submission/trojan_report.json   (the graded answer file)

Grades FR1-FR4 (schema/format) and SR1-SR4 (substantive security findings)
against the submitted trojan_report.json, using only structural information
derivable from the netlist text (so it works against any renamed/restructured
but functionally-equivalent netlist).

Exit code 0 iff all 8 requirements PASS; otherwise 1.
"""

import json
import re
import sys
import os
import subprocess
import tempfile
import itertools

NETLIST_PATH = "inputs/audit_module_netlist.v"
DESIGN_BRIEF_PATH = "inputs/design_brief.md"
PORT_MAP_PATH = "inputs/port_map.txt"
SUBMISSION_PATH = "submission/trojan_report.json"
TB_TEMPLATE_PATH = "evaluation/tb_trigger_check.v"

PRIMARY_INPUTS = {"clk", "rst_n", "maintenance_req", "alarm", "tamper_event"}

results = []  # list of (req_id, bool_passed, message)


def record(req_id, passed, msg=""):
    if passed:
        print("[TEST] PASS: %s" % req_id)
    else:
        print("[TEST] FAIL: %s: %s" % (req_id, msg))
    results.append((req_id, passed, msg))


def fail_setup(req_ids, path):
    for rid in req_ids:
        print("[TEST] FAIL: %s: SETUP: %s not found" % (rid, path))
        results.append((rid, False, "SETUP: %s not found" % path))


# ---------------------------------------------------------------------------
# Netlist structural parsing
# ---------------------------------------------------------------------------

INSTANCE_RE = re.compile(
    r'\b([A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z_][A-Za-z0-9_\[\]]*)\s*\(\s*\.'
)

PORT_CONN_RE = re.compile(r'\.\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*([^()]*?)\s*\)')

CELL_TYPES = {"INV", "BUF", "AND2", "OR2", "DFF_ASYNC_CLR"}


def strip_comments(text):
    text = re.sub(r'//.*', '', text)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    return text


def parse_netlist(text):
    """
    Parse the netlist text into:
      - instances: dict instance_name -> {"type": cell_type, "ports": {port: net_expr}}
      - nets: set of all net identifiers encountered (declared wires/regs, port names,
              and bit-indexed forms of buses)
      - top_ports: set of audit_top port names
    """
    text = strip_comments(text)

    # Restrict to the audit_top module body (between "module audit_top" and its
    # matching "endmodule"). We locate the module keyword and take everything
    # up to the next 'endmodule' after it, which is sufficient since audit_top
    # is defined last / self-contained per the interface contract.
    m = re.search(r'module\s+audit_top\b(.*?)endmodule', text, flags=re.DOTALL)
    body = m.group(1) if m else text

    # top-level ports: from the port list of audit_top declaration, using a
    # more permissive scan across "input"/"output" declarations within body.
    top_ports = set()
    for pm in re.finditer(
        r'\b(?:input|output)\s+(?:wire\s+|reg\s+)?(?:\[\s*\d+\s*:\s*\d+\s*\]\s*)?'
        r'([A-Za-z_][A-Za-z0-9_]*)', body
    ):
        top_ports.add(pm.group(1))

    # wire/reg declarations (including bus declarations)
    nets = set()
    nets |= top_ports
    for wm in re.finditer(
        r'\b(?:wire|reg)\s+(?:\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*)?'
        r'([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)\s*;',
        body
    ):
        hi, lo, names_blob = wm.group(1), wm.group(2), wm.group(3)
        names = [n.strip() for n in names_blob.split(',')]
        for nm in names:
            nets.add(nm)
            if hi is not None and lo is not None:
                try:
                    hi_i, lo_i = int(hi), int(lo)
                    for idx in range(min(hi_i, lo_i), max(hi_i, lo_i) + 1):
                        nets.add("%s[%d]" % (nm, idx))
                except ValueError:
                    pass

    # instances: scan for "TYPE instname ( .port(net), ... );"
    instances = {}
    # Find each instantiation block by locating "TYPE instname (" then matching
    # up to the closing ");" (balanced enough for this flat netlist style).
    inst_iter = re.finditer(
        r'\b([A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(',
        body
    )
    for im in inst_iter:
        cell_type = im.group(1)
        inst_name = im.group(2)
        if cell_type in ("module", "input", "output", "wire", "reg", "assign",
                          "always", "if", "else", "begin", "end", "function",
                          "endfunction", "posedge", "negedge"):
            continue
        # only accept as instance if cell_type looks like a declared cell type
        # (heuristic: uppercase-containing identifier matching known primitives,
        # OR any identifier followed by a port-connection list containing '.').
        start = im.end() - 1  # position of '('
        # find matching close paren
        depth = 0
        i = start
        end = None
        while i < len(body):
            if body[i] == '(':
                depth += 1
            elif body[i] == ')':
                depth -= 1
                if depth == 0:
                    end = i
                    break
            i += 1
        if end is None:
            continue
        conn_blob = body[start + 1:end]
        if '.' not in conn_blob:
            continue  # positional instantiation not used in this style; skip
        ports = {}
        for pm2 in PORT_CONN_RE.finditer(conn_blob):
            port_name = pm2.group(1)
            net_expr = pm2.group(2).strip()
            ports[port_name] = net_expr
        instances[inst_name] = {"type": cell_type, "ports": ports}
        nets.add(inst_name)  # harmless; instance names tracked separately too

    # also register bit-select nets referenced anywhere as connections, e.g. foo[3]
    for bm in re.finditer(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*\[\s*(\d+)\s*\]', body):
        nets.add("%s[%s]" % (bm.group(1), bm.group(2)))

    return {
        "instances": instances,
        "nets": nets,
        "top_ports": top_ports,
        "body": body,
    }


def instance_names(parsed):
    return set(parsed["instances"].keys())


def net_names(parsed):
    return set(parsed["nets"])


def strip_bus_index(name):
    m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\[\d+\]$', name)
    if m:
        return m.group(1)
    return name


def resolve_identifier(name, parsed, kind):
    """
    kind: 'net' or 'instance'
    Returns True if name resolves against the parsed netlist, allowing
    exact match, case-insensitive match, or (for nets) matching the base
    bus name when an indexed form was requested loosely.
    """
    name = name.strip()
    if kind == "net":
        pool = net_names(parsed)
    else:
        pool = instance_names(parsed)

    if name in pool:
        return True
    # case-insensitive match
    lower_pool = {p.lower(): p for p in pool}
    if name.lower() in lower_pool:
        return True
    if kind == "net":
        base = strip_bus_index(name)
        if base in pool or base.lower() in lower_pool:
            return True
    return False


# ---------------------------------------------------------------------------
# Structural trace: find the net driving the CLR pins of the DFF_ASYNC_CLR bank,
# and identify the gates on the malicious clear path (SR1, SR2).
# ---------------------------------------------------------------------------

def find_dff_clr_net(parsed):
    """Return the (single, common) net name feeding the CLR pin of all
    DFF_ASYNC_CLR instances, or None if inconsistent/not found."""
    clr_nets = set()
    dff_insts = []
    for inst_name, info in parsed["instances"].items():
        if info["type"] == "DFF_ASYNC_CLR":
            dff_insts.append(inst_name)
            clr_expr = info["ports"].get("CLR")
            if clr_expr is not None:
                clr_nets.add(clr_expr.strip())
    if not dff_insts:
        return None, []
    if len(clr_nets) != 1:
        # inconsistent clear net across the bank; cannot uniquely resolve
        return None, dff_insts
    return next(iter(clr_nets)), dff_insts


def find_driver_instance(parsed, net_name):
    """Find the instance whose output port (heuristically named Y, Q, or
    matching typical output-port names) drives net_name. Returns inst_name
    or None."""
    for inst_name, info in parsed["instances"].items():
        for port_name, net_expr in info["ports"].items():
            if net_expr.strip() == net_name and port_name.upper() in ("Y", "Q", "O", "OUT"):
                return inst_name
    return None


def gate_input_nets(parsed, inst_name):
    """Return list of net expressions connected to non-output ports of inst_name."""
    info = parsed["instances"].get(inst_name)
    if not info:
        return []
    ins = []
    for port_name, net_expr in info["ports"].items():
        if port_name.upper() not in ("Y", "Q", "O", "OUT"):
            ins.append(net_expr.strip())
    return ins


def find_reset_sync_net(parsed):
    """Identify the net that is the sole fanout of the rst_n inverter/buffer
    chain (i.e. the synchronized reset net), structurally: trace from rst_n
    through a chain of single-input gates (INV/BUF) to find the terminal net
    that is NOT consumed only by more INV/BUF but is used elsewhere."""
    # Find gates whose input is rst_n (directly), then follow single-input
    # chains (INV/BUF) forward.
    current_nets = set()
    for inst_name, info in parsed["instances"].items():
        if info["type"] in ("INV", "BUF"):
            in_nets = gate_input_nets(parsed, inst_name)
            if any(n == "rst_n" or strip_bus_index(n) == "rst_n" for n in in_nets):
                out = info["ports"].get("Y") or info["ports"].get("Q")
                if out:
                    current_nets.add(out.strip())

    visited = set()
    frontier = set(current_nets)
    terminal = set()
    while frontier:
        net = frontier.pop()
        if net in visited:
            continue
        visited.add(net)
        driver = None
        for inst_name, info in parsed["instances"].items():
            if info["type"] in ("INV", "BUF"):
                in_nets = gate_input_nets(parsed, inst_name)
                if net in in_nets:
                    out = info["ports"].get("Y") or info["ports"].get("Q")
                    if out:
                        frontier.add(out.strip())
                        driver = True
        terminal.add(net)
    return terminal  # set of candidate rst_sync-equivalent net names


def find_malicious_gates(parsed):
    """
    Structurally identify:
      G1 = a 2-input gate (AND2 or equivalent) whose two inputs are exactly
           {maintenance_req, alarm} (order independent).
      G2 = a 2-input gate (OR2 or equivalent) whose inputs are G1's output net
           and a reset-synchronizer-derived net, and whose output is the
           common DFF CLR net (or feeds into it).
    Returns (g1_inst, g2_inst, clr_net) any of which may be None if not found.
    """
    clr_net, dff_insts = find_dff_clr_net(parsed)

    g1_inst = None
    g1_out = None
    for inst_name, info in parsed["instances"].items():
        ins = set(strip_bus_index(n) for n in gate_input_nets(parsed, inst_name))
        if ins == {"maintenance_req", "alarm"}:
            g1_inst = inst_name
            g1_out = (info["ports"].get("Y") or info["ports"].get("Q") or "").strip()
            break

    reset_sync_candidates = find_reset_sync_net(parsed)

    g2_inst = None
    if g1_out:
        for inst_name, info in parsed["instances"].items():
            ins = [n.strip() for n in gate_input_nets(parsed, inst_name)]
            if g1_out in ins:
                other = [n for n in ins if n != g1_out]
                out = (info["ports"].get("Y") or info["ports"].get("Q") or "").strip()
                if any(o in reset_sync_candidates for o in other) or (
                    clr_net is not None and out == clr_net
                ):
                    g2_inst = inst_name
                    break

    return g1_inst, g2_inst, clr_net, reset_sync_candidates


# ---------------------------------------------------------------------------
# FR checks
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {
    "trojan_present": bool,
    "suspect_gates": list,
    "altered_net": str,
    "affected_registers": list,
    "trigger_condition": str,
    "justification": str,
}


def check_fr1(submission):
    if submission is None:
        record("FR1", False, "submission could not be parsed as JSON")
        return False
    if not isinstance(submission, dict):
        record("FR1", False, "top-level JSON value is not an object")
        return False
    missing = [k for k in REQUIRED_FIELDS if k not in submission]
    if missing:
        record("FR1", False, "missing required field(s): %s" % ", ".join(missing))
        return False
    type_errs = []
    for k, expected_type in REQUIRED_FIELDS.items():
        val = submission[k]
        if expected_type is bool:
            if not isinstance(val, bool):
                type_errs.append("%s expected bool, got %s" % (k, type(val).__name__))
        elif expected_type is list:
            if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
                type_errs.append("%s expected list[str]" % k)
        elif expected_type is str:
            if not isinstance(val, str):
                type_errs.append("%s expected str, got %s" % (k, type(val).__name__))
    if type_errs:
        record("FR1", False, "; ".join(type_errs))
        return False
    record("FR1", True)
    return True


def check_fr2(submission, parsed):
    if submission is None:
        record("FR2", False, "no valid submission JSON")
        return False
    bad = []
    for g in submission.get("suspect_gates", []):
        if not isinstance(g, str) or not resolve_identifier(g, parsed, "instance"):
            bad.append("suspect_gates:%r" % g)
    for r in submission.get("affected_registers", []):
        if not isinstance(r, str) or not resolve_identifier(r, parsed, "instance"):
            bad.append("affected_registers:%r" % r)
    altered_net = submission.get("altered_net", "")
    if not isinstance(altered_net, str) or not altered_net.strip() or not resolve_identifier(altered_net, parsed, "net"):
        bad.append("altered_net:%r" % altered_net)
    if bad:
        record("FR2", False, "unresolved identifier(s) not found in netlist: %s" % "; ".join(bad))
        return False
    record("FR2", True)
    return True


def normalize_bool_expr(expr):
    """Normalize common boolean-expression notations (AND/OR/NOT, &&/||/!,
    &/|/~) into a Python-evaluable form using 'and'/'or'/'not'."""
    e = expr
    e = re.sub(r'\bAND\b', 'and', e, flags=re.IGNORECASE)
    e = re.sub(r'\bOR\b', 'or', e, flags=re.IGNORECASE)
    e = re.sub(r'\bNOT\b', 'not', e, flags=re.IGNORECASE)
    e = e.replace('&&', ' and ').replace('||', ' or ')
    e = re.sub(r'(?<![a-zA-Z0-9_])!', ' not ', e)
    # single & / | for bitwise-style boolean use, but avoid breaking 'and'/'or' text
    e = re.sub(r'&(?!&)', ' and ', e)
    e = re.sub(r'\|(?!\|)', ' or ', e)
    e = re.sub(r'~', ' not ', e)
    return e


def extract_identifiers(expr):
    return set(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', expr))


def check_fr3(submission):
    if submission is None:
        record("FR3", False, "no valid submission JSON")
        return False
    trojan_present = submission.get("trojan_present", None)
    if trojan_present is not True:
        # FR3 only applies conditionally when trojan_present == true
        record("FR3", True)
        return True
    trig = submission.get("trigger_condition", "")
    if not isinstance(trig, str) or not trig.strip():
        record("FR3", False, "trigger_condition is empty or not a string")
        return False
    norm = normalize_bool_expr(trig)
    idents = extract_identifiers(norm)
    # filter out python keywords used as normalized operators
    idents -= {"and", "or", "not", "True", "False"}
    bad_idents = [i for i in idents if i not in PRIMARY_INPUTS]
    if bad_idents:
        record("FR3", False, "trigger_condition references non-port identifier(s): %s" % ", ".join(sorted(bad_idents)))
        return False
    # attempt to parse via compile with the whitelisted vars set to booleans
    try:
        env = {name: False for name in PRIMARY_INPUTS}
        compile(norm, "<trigger_condition>", "eval")
        eval(norm, {"__builtins__": {}}, env)
    except Exception as e:
        record("FR3", False, "trigger_condition failed to parse/evaluate: %s" % e)
        return False
    record("FR3", True)
    return True


def check_fr4(submission):
    if submission is None:
        record("FR4", False, "no valid submission JSON")
        return False
    just = submission.get("justification", None)
    if not isinstance(just, str):
        record("FR4", False, "justification is not a string")
        return False
    if len(just.strip()) == 0:
        record("FR4", False, "justification is empty")
        return False
    if len(just) > 2000:
        record("FR4", False, "justification exceeds 2000 characters (len=%d)" % len(just))
        return False
    record("FR4", True)
    return True


# ---------------------------------------------------------------------------
# SR checks
# ---------------------------------------------------------------------------

def check_sr1(submission, parsed):
    if submission is None:
        record("SR1", False, "no valid submission JSON")
        return False
    clr_net, dff_insts = find_dff_clr_net(parsed)
    if clr_net is None:
        record("SR1", False, "internal error: could not structurally resolve DFF CLR net from netlist")
        return False

    altered_net = submission.get("altered_net", "")
    if not isinstance(altered_net, str) or not altered_net.strip():
        record("SR1", False, "altered_net is empty/missing")
        return False

    # Must match clr_net (case-insensitive, allow index-stripped compare)
    def norm(n):
        return strip_bus_index(n.strip()).lower()

    if norm(altered_net) != norm(clr_net) and altered_net.strip() != clr_net:
        record("SR1", False, "altered_net %r does not match structurally-traced clear-driving net %r" % (altered_net, clr_net))
        return False

    # Ensure it's not merely the reset-sync net itself (i.e. it must be driven
    # by a gate with >1 distinct input source, not a pure single-source path).
    driver_inst = find_driver_instance(parsed, clr_net)
    if driver_inst is None:
        record("SR1", False, "could not find driving gate instance for net %r" % clr_net)
        return False
    ins = gate_input_nets(parsed, driver_inst)
    distinct_ins = set(strip_bus_index(n) for n in ins)
    if len(distinct_ins) < 2:
        record("SR1", False, "clear net %r is driven by a single-source path; not a merged/trojan net" % clr_net)
        return False

    reset_sync_candidates = find_reset_sync_net(parsed)
    if norm(altered_net) in {norm(c) for c in reset_sync_candidates} or strip_bus_index(altered_net) == "rst_n":
        record("SR1", False, "altered_net names the legitimate reset signal itself, not the merged clear net")
        return False

    record("SR1", True)
    return True


def check_sr2(submission, parsed):
    if submission is None:
        record("SR2", False, "no valid submission JSON")
        return False
    g1_inst, g2_inst, clr_net, _ = find_malicious_gates(parsed)
    if g1_inst is None or g2_inst is None:
        record("SR2", False, "internal error: could not structurally identify ground-truth malicious gates in netlist")
        return False

    suspect_gates = submission.get("suspect_gates", [])
    if not isinstance(suspect_gates, list):
        record("SR2", False, "suspect_gates is not a list")
        return False

    lower_reported = {g.lower() for g in suspect_gates if isinstance(g, str)}

    missing = []
    if g1_inst.lower() not in lower_reported:
        missing.append("gate implementing (maintenance_req AND alarm) [%s]" % g1_inst)
    if g2_inst.lower() not in lower_reported:
        missing.append("gate merging that condition with reset before the counter clear [%s]" % g2_inst)

    if missing:
        record("SR2", False, "suspect_gates missing required entries: %s" % "; ".join(missing))
        return False

    record("SR2", True)
    return True


def truth_table(expr_norm, varnames):
    table = {}
    for combo in itertools.product([False, True], repeat=len(varnames)):
        env = dict(zip(varnames, combo))
        full_env = {name: False for name in PRIMARY_INPUTS}
        full_env.update(env)
        try:
            val = bool(eval(expr_norm, {"__builtins__": {}}, full_env))
        except Exception:
            return None
        table[combo] = val
    return table


def run_iverilog_crosscheck(netlist_path, tb_template_path):
    """Best-effort simulation cross-check; returns dict mapping
    (maintenance_req, alarm, rst_n) -> cleared(bool), or None if the
    toolchain/simulation is unavailable."""
    try:
        if not os.path.isfile(tb_template_path):
            return None
        with tempfile.TemporaryDirectory() as td:
            sim_path = os.path.join(td, "sim.vvp")
            compile_cmd = ["iverilog", "-g2012", "-o", sim_path, netlist_path, tb_template_path]
            cp = subprocess.run(compile_cmd, capture_output=True, timeout=30, text=True)
            if cp.returncode != 0:
                return None
            run_cmd = ["vvp", sim_path]
            rp = subprocess.run(run_cmd, capture_output=True, timeout=30, text=True)
            if rp.returncode != 0:
                return None
            results_map = {}
            for line in rp.stdout.splitlines():
                m = re.match(r'VEC\s+(\d)\s+(\d)\s+(\d)\s+(\d)', line.strip())
                if m:
                    mr, al, rn, cleared = (int(x) for x in m.groups())
                    results_map[(bool(mr), bool(al), bool(rn))] = bool(cleared)
            return results_map if results_map else None
    except Exception:
        return None


def check_sr3(submission, parsed):
    if submission is None:
        record("SR3", False, "no valid submission JSON")
        return False
    if submission.get("trojan_present", None) is not True:
        record("SR3", False, "trojan_present is not true; cannot evaluate trigger_condition against ground truth")
        return False

    trig = submission.get("trigger_condition", "")
    if not isinstance(trig, str) or not trig.strip():
        record("SR3", False, "trigger_condition is empty/missing")
        return False

    norm = normalize_bool_expr(trig)
    idents = extract_identifiers(norm) - {"and", "or", "not", "True", "False"}
    bad_idents = [i for i in idents if i not in PRIMARY_INPUTS]
    if bad_idents:
        record("SR3", False, "trigger_condition references non-port identifier(s): %s" % ", ".join(sorted(bad_idents)))
        return False

    varnames = ["maintenance_req", "alarm", "rst_n"]
    submitted_table = truth_table(norm, varnames)
    if submitted_table is None:
        record("SR3", False, "trigger_condition failed to evaluate as a boolean expression")
        return False

    reference_table = {}
    for combo in itertools.product([False, True], repeat=3):
        mr, al, rn = combo
        reference_table[combo] = bool(mr and al)  # independent of rst_n

    mismatches = []
    for combo in reference_table:
        if submitted_table.get(combo) != reference_table[combo]:
            mismatches.append((combo, submitted_table.get(combo), reference_table[combo]))

    if mismatches:
        combo, got, expected = mismatches[0]
        record(
            "SR3", False,
            "trigger_condition truth table mismatch at (maintenance_req=%s, alarm=%s, rst_n=%s): "
            "got %s, expected %s (must equal maintenance_req AND alarm, independent of rst_n)"
            % (combo[0], combo[1], combo[2], got, expected)
        )
        return False

    # Optional corroborating simulation cross-check (does not override the
    # primary truth-table verdict above, but is attempted best-effort).
    run_iverilog_crosscheck(NETLIST_PATH, TB_TEMPLATE_PATH)

    record("SR3", True)
    return True


def check_sr4(submission):
    if submission is None:
        record("SR4", False, "no valid submission JSON")
        return False
    tp = submission.get("trojan_present", None)
    if tp is not True:
        record("SR4", False, "trojan_present reported as %r; ground truth requires true" % (tp,))
        return False
    record("SR4", True)
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    all_req_ids = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]

    # Load netlist (required for FR2/SR1/SR2/SR3 structural resolution)
    if not os.path.isfile(NETLIST_PATH):
        fail_setup(all_req_ids, NETLIST_PATH)
        sys.exit(1)
    try:
        with open(NETLIST_PATH, "r") as f:
            netlist_text = f.read()
    except Exception as e:
        fail_setup(all_req_ids, NETLIST_PATH)
        sys.exit(1)

    # design_brief.md / port_map.txt are part of the input contract but are
    # not structurally parsed by this grader; still verify presence per the
    # fixed input_artifacts contract (soft — do not hard fail all reqs if
    # merely absent, since only the netlist is required for structural
    # grading). We simply attempt to open them for completeness.
    for aux_path in (DESIGN_BRIEF_PATH, PORT_MAP_PATH):
        if os.path.isfile(aux_path):
            try:
                with open(aux_path, "r"):
                    pass
            except Exception:
                pass

    parsed = parse_netlist(netlist_text)

    # Load submission
    if not os.path.isfile(SUBMISSION_PATH):
        fail_setup(all_req_ids, SUBMISSION_PATH)
        sys.exit(1)

    submission = None
    try:
        with open(SUBMISSION_PATH, "r") as f:
            raw = f.read()
        submission = json.loads(raw)
    except Exception as e:
        # FR1 will fail explicitly; all other checks proceed with submission=None
        submission = None
        parse_error = str(e)
    else:
        parse_error = None

    fr1_ok = check_fr1(submission) if parse_error is None else False
    if parse_error is not None:
        record("FR1", False, "JSON parse error: %s" % parse_error)

    check_fr2(submission, parsed)
    check_fr3(submission)
    check_fr4(submission)

    check_sr1(submission, parsed)
    check_sr2(submission, parsed)
    check_sr3(submission, parsed)
    check_sr4(submission)

    all_passed = all(passed for (_, passed, _) in results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()