#!/usr/bin/env python3
"""
evaluate.py -- Gate-level Trojan Detection grader for the address-decoder
aliasing case (gate_trojan_detection_addr_decoder_alias_001).

Reads inputs/decoder_netlist.v, inputs/testbench_harness.v,
inputs/gate_library.v as reference material, and grades
submission/trojan_report.json against the hidden ground truth by:
  - structurally parsing decoder_netlist.v (regex-based) to build the
    universe of valid net/instance names and to trace the alias-gate
    structure feeding bank2_we,
  - exhaustively simulating decoder_netlist.v via evaluation/tb_exhaustive.v
    (iverilog + vvp) to build the ground-truth activation table.

Ground truth for this case: at addr=011, write_en=1, both bank0_we and
bank2_we assert simultaneously (bank0_we's legitimate decode tree spans
minterm0 OR minterm3; a hidden alias tap re-derives the minterm3&write_en
condition and ORs it into the bank2_we enable tree). bank3_we is unused
(tied low) in this corrected wiring. All other legal addresses assert at
most one bank write-enable.

Prints one '[TEST] PASS: <id>' or '[TEST] FAIL: <id>: <reason>' line per
requirement id (FR1-FR4, SR1-SR5) and exits 0 iff all pass.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

INPUTS_DIR = "inputs"
SUBMISSION_PATH = os.path.join("submission", "trojan_report.json")

DECODER_FILE = os.path.join(INPUTS_DIR, "decoder_netlist.v")
TESTBENCH_FILE = os.path.join(INPUTS_DIR, "testbench_harness.v")
GATE_LIB_FILE = os.path.join(INPUTS_DIR, "gate_library.v")

EVAL_TB_EXHAUSTIVE = os.path.join("evaluation", "tb_exhaustive.v")

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4", "SR5"]

results = {}  # id -> (bool, reason)


def record(rid, ok, reason=""):
    if rid in results:
        return
    results[rid] = (ok, reason)
    if ok:
        print("[TEST] PASS: %s" % rid)
    else:
        print("[TEST] FAIL: %s: %s" % (rid, reason))


def fail_setup_all(missing_path):
    for rid in REQUIREMENT_IDS:
        if rid not in results:
            print("[TEST] FAIL: SETUP: %s not found" % missing_path)
    sys.exit(1)


def read_file(path):
    with open(path, "r") as f:
        return f.read()


# ---------------------------------------------------------------------
# Structural parsing of decoder_netlist.v
# ---------------------------------------------------------------------

def strip_comments(text):
    text = re.sub(r'//.*', '', text)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    return text


def parse_ports(text):
    """Return dict: port_name -> direction ('input'/'output')"""
    ports = {}
    for m in re.finditer(
        r'\b(input|output)\s+(?:wire\s+|reg\s+|logic\s+)?(?:\[\s*\d+\s*:\s*\d+\s*\]\s*)?'
        r'([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)\s*[;,)]',
        text
    ):
        direction = m.group(1)
        names = [n.strip() for n in m.group(2).split(",")]
        for n in names:
            if n:
                ports[n] = direction
    return ports


def parse_wires(text):
    """Return set of declared wire names."""
    wires = set()
    for m in re.finditer(
        r'\bwire\s+(?:\[\s*\d+\s*:\s*\d+\s*\]\s*)?'
        r'([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)\s*;',
        text
    ):
        names = [n.strip() for n in m.group(1).split(",")]
        for n in names:
            if n:
                wires.add(n)
    return wires


def parse_instances(text):
    """
    Parse gate/module instances of the form:
        TYPE #(...)? INSTNAME ( .port(net), .port(net), ... );
    Returns list of dicts: {type, name, conns: {port: net}}
    Skips 'module' declarations themselves.
    """
    instances = []
    pattern = re.compile(
        r'\b([A-Za-z_][A-Za-z0-9_]*)\s+'          # type
        r'(?:#\s*\([^)]*\)\s*)?'                   # optional params
        r'([A-Za-z_][A-Za-z0-9_]*)\s*'             # instance name
        r'\(([^;]*?)\)\s*;',
        re.DOTALL
    )
    keywords = {"module", "endmodule", "input", "output", "wire", "reg",
                "assign", "always", "initial", "begin", "end", "if", "else",
                "posedge", "negedge", "function", "endfunction", "parameter",
                "localparam", "case", "endcase", "for", "and", "or", "not",
                "nand", "nor", "xor", "xnor", "buf"}
    for m in pattern.finditer(text):
        itype = m.group(1)
        iname = m.group(2)
        body = m.group(3)
        if itype in keywords or iname in keywords:
            continue
        conns = {}
        for cm in re.finditer(r'\.\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*([^()]*?)\s*\)', body):
            port = cm.group(1)
            net = cm.group(2).strip()
            conns[port] = net
        instances.append({"type": itype, "name": iname, "conns": conns})
    return instances


def parse_assigns(text):
    """Return list of (lhs, rhs) for assign statements."""
    assigns = []
    for m in re.finditer(r'\bassign\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^;]+);', text):
        lhs = m.group(1).strip()
        rhs = m.group(2).strip()
        assigns.append((lhs, rhs))
    return assigns


def build_net_universe(text, ports, wires, instances):
    """All valid net names: ports + declared wires + any net literal used as
    an instance connection (covers implicit nets)."""
    universe = set(ports.keys()) | set(wires)
    for inst in instances:
        for net in inst["conns"].values():
            cleaned = re.sub(r'\[[^\]]*\]', '', net).strip()
            if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', cleaned):
                universe.add(cleaned)
    return universe


def trace_bank2_structural_suspects(ports, instances, assigns):
    """
    Identify the set of (net_name / gate_instance) candidates that
    structurally constitute the "alias" gate feeding bank2_we with a tap
    of the minterm-3 (addr==011) decode, regardless of naming.

    Approach (name-agnostic, structural):
      1. Build a driver map: net_name -> instance dict, using known
         output-port-name conventions from gate_library.v ('y', 'q', 'out',
         'o'). gate_library.v is a fixed input artifact so these
         conventions are safe to rely on structurally.
      2. Identify "minterm3" signals: outputs of AND-like instances whose
         inputs resolve (directly, or through one level of NOT gates) to
         addr[2]==0, addr[1]==1, addr[0]==1.
      3. Extend to "minterm3-derived" signals: outputs of instances whose
         inputs include a minterm3 signal AND write_en (an extra AND gate
         re-deriving the minterm3&write_en condition).
      4. Trace what drives bank2_we's DFF D input (walking through assigns).
      5. Any instance whose output feeds (directly or via assigns) that
         D-input tree AND whose inputs intersect the minterm3/minterm3-
         derived signal set is the alias/bridge gate.

    Returns dict with candidate net/instance names usable for fuzzy
    matching against a submitted report.
    """
    net_driver = {}  # net_name -> instance dict
    net_drivers_ports = ("y", "q", "out", "o")

    for inst in instances:
        conns = inst["conns"]
        out_net = None
        for pname in net_drivers_ports:
            if pname in conns:
                out_net = conns[pname]
                break
        if out_net is None:
            continue
        net_driver[out_net] = inst

    net_assign_rhs = {}
    for lhs, rhs in assigns:
        net_assign_rhs[lhs] = rhs

    def inst_inputs(inst):
        conns = inst["conns"]
        return {p: n for p, n in conns.items() if p not in net_drivers_ports}

    def resolve_addr_polarity(net):
        """
        Return (bit_index, polarity) if `net` is directly addr[bitidx]
        (polarity True) or the output of a NOT gate whose input is
        addr[bitidx] (polarity False), else None.
        """
        m = re.match(r'^addr\s*\[\s*(\d)\s*\]$', net)
        if m:
            return (int(m.group(1)), True)
        if net in net_driver:
            inst = net_driver[net]
            inputs = inst_inputs(inst)
            if len(inputs) == 1:
                (only_port, only_net) = list(inputs.items())[0]
                m2 = re.match(r'^addr\s*\[\s*(\d)\s*\]$', only_net)
                if m2:
                    return (int(m2.group(1)), False)
        return None

    minterm3_signal_nets = set()
    minterm3_instances = set()

    for inst in instances:
        inputs = inst_inputs(inst)
        if len(inputs) < 2:
            continue
        polarities = {}
        ok = True
        for port, net in inputs.items():
            res = resolve_addr_polarity(net)
            if res is None:
                if net == "write_en":
                    continue
                ok = False
                break
            bit_idx, pol = res
            polarities[bit_idx] = pol
        if not ok:
            continue
        # addr == 3'b011 means addr[2]=0 (pol False), addr[1]=1 (pol True),
        # addr[0]=1 (pol True)
        if polarities.get(2) is False and polarities.get(1) is True and polarities.get(0) is True:
            out_net = None
            for pname in net_drivers_ports:
                if pname in inst["conns"]:
                    out_net = inst["conns"][pname]
                    break
            if out_net:
                minterm3_signal_nets.add(out_net)
                minterm3_instances.add(inst["name"])

    minterm3_or_derived = set(minterm3_signal_nets)
    for inst in instances:
        inputs = inst_inputs(inst)
        input_nets = set(inputs.values())
        if input_nets & minterm3_signal_nets and "write_en" in input_nets:
            out_net = None
            for pname in net_drivers_ports:
                if pname in inst["conns"]:
                    out_net = inst["conns"][pname]
                    break
            if out_net:
                minterm3_or_derived.add(out_net)

    # Determine what drives bank2_we's D input.
    bank2_dff = None
    for inst in instances:
        conns = inst["conns"]
        if conns.get("q") == "bank2_we":
            bank2_dff = inst
            break

    bank2_alias_instances = set()
    bank2_alias_nets = set()

    if bank2_dff is not None:
        d_net = bank2_dff["conns"].get("d")
        visited_nets = set()
        frontier = [d_net] if d_net else []
        resolved_final_nets = set()
        while frontier:
            n = frontier.pop()
            if n in visited_nets or n is None:
                continue
            visited_nets.add(n)
            if n in net_assign_rhs:
                rhs = net_assign_rhs[n]
                rhs_ids = re.findall(r'[A-Za-z_][A-Za-z0-9_]*', rhs)
                for rid in rhs_ids:
                    frontier.append(rid)
            else:
                resolved_final_nets.add(n)

        for inst in instances:
            out_net = None
            for pname in net_drivers_ports:
                if pname in inst["conns"]:
                    out_net = inst["conns"][pname]
                    break
            if out_net is None:
                continue
            inputs = inst_inputs(inst)
            input_nets = set(inputs.values())
            feeds_bank2 = out_net in resolved_final_nets
            has_minterm3_tap = bool(input_nets & minterm3_or_derived)
            if feeds_bank2 and has_minterm3_tap:
                bank2_alias_instances.add(inst["name"])
                bank2_alias_nets.add(out_net)

    candidate_names = set()
    candidate_names |= minterm3_instances
    candidate_names |= minterm3_signal_nets
    candidate_names |= minterm3_or_derived
    candidate_names |= bank2_alias_instances
    candidate_names |= bank2_alias_nets
    for inst in instances:
        if inst["name"] in bank2_alias_instances:
            candidate_names |= set(inst["conns"].values())

    return {
        "minterm3_signal_nets": minterm3_signal_nets,
        "bank2_alias_instances": bank2_alias_instances,
        "bank2_alias_nets": bank2_alias_nets,
        "candidate_names": candidate_names,
    }


# ---------------------------------------------------------------------
# Exhaustive simulation via iverilog + vvp
# ---------------------------------------------------------------------

def run_exhaustive_simulation():
    """
    Compile and run evaluation/tb_exhaustive.v against inputs/decoder_netlist.v
    and inputs/gate_library.v. Returns (table, err) where table is keyed by
    (addr_str, we_str) -> dict(bank0_we=str,...,bank3_we=str), or (None, reason)
    on failure.
    """
    if not os.path.isfile(EVAL_TB_EXHAUSTIVE):
        return None, "evaluation/tb_exhaustive.v not found"

    with tempfile.TemporaryDirectory() as tmpdir:
        sim_path = os.path.join(tmpdir, "sim.vvp")
        compile_cmd = [
            "iverilog", "-g2012", "-o", sim_path,
            EVAL_TB_EXHAUSTIVE, DECODER_FILE, GATE_LIB_FILE
        ]
        try:
            cp = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return None, "iverilog compile timed out"
        except FileNotFoundError:
            return None, "iverilog not available"
        if cp.returncode != 0:
            return None, "iverilog compile failed: %s" % (cp.stderr.strip()[:400])

        try:
            rp = subprocess.run(["vvp", sim_path], capture_output=True, text=True, timeout=10)
        except subprocess.TimeoutExpired:
            return None, "vvp simulation timed out"
        except FileNotFoundError:
            return None, "vvp not available"
        if rp.returncode != 0 and "VEC " not in (rp.stdout or ""):
            return None, "vvp run failed: %s" % (rp.stderr.strip()[:400])

        output = rp.stdout or ""

    table = {}
    for m in re.finditer(
        r'VEC\s+addr=([01]{3})\s+we=([01])\s+b0=([01])\s+b1=([01])\s+b2=([01])\s+b3=([01])',
        output
    ):
        addr, we, b0, b1, b2, b3 = m.groups()
        table[(addr, we)] = {
            "bank0_we": b0, "bank1_we": b1, "bank2_we": b2, "bank3_we": b3
        }
    if len(table) < 16:
        return None, "exhaustive simulation produced incomplete data (%d/16 vectors parsed)" % len(table)
    return table, None


def ground_truth_anomalous_addresses(sim_table):
    """
    Return dict address -> set of asserted bank outputs, restricted to
    write_en='1' vectors, only for entries where more than one bank
    asserts (i.e. anomalies relative to one-hot).
    """
    anomalies = {}
    for (addr, we), vals in sim_table.items():
        if we != "1":
            continue
        asserted = {k for k, v in vals.items() if v == "1"}
        if len(asserted) > 1:
            anomalies[addr] = asserted
    return anomalies


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():
    # ---- SETUP: verify input artifacts exist ----
    for path in (DECODER_FILE, TESTBENCH_FILE, GATE_LIB_FILE):
        if not os.path.isfile(path):
            fail_setup_all(path)

    if not os.path.isfile(SUBMISSION_PATH):
        fail_setup_all(SUBMISSION_PATH)

    decoder_text_raw = read_file(DECODER_FILE)
    decoder_text = strip_comments(decoder_text_raw)

    ports = parse_ports(decoder_text)
    wires = parse_wires(decoder_text)
    instances = parse_instances(decoder_text)
    assigns = parse_assigns(decoder_text)
    net_universe = build_net_universe(decoder_text, ports, wires, instances)
    instance_names = {inst["name"] for inst in instances}

    output_ports = {name for name, d in ports.items() if d == "output"}
    input_ports = {name for name, d in ports.items() if d == "input"}

    # ---- Load submission JSON ----
    try:
        with open(SUBMISSION_PATH, "r") as f:
            report_text = f.read()
        report = json.loads(report_text)
    except Exception as e:
        reason = "invalid JSON: %s" % str(e)
        for rid in REQUIREMENT_IDS:
            record(rid, False, reason)
        sys.exit(1)

    if not isinstance(report, dict):
        reason = "submission JSON root is not an object"
        for rid in REQUIREMENT_IDS:
            record(rid, False, reason)
        sys.exit(1)

    # =========================================================
    # FR1: schema structural validity
    # =========================================================
    required_top = ["design_under_test", "trojan_present", "suspect_nets",
                     "trigger_condition", "affected_outputs", "evidence"]
    fr1_ok = True
    fr1_reason = ""

    missing = [k for k in required_top if k not in report]
    if missing:
        fr1_ok = False
        fr1_reason = "missing top-level fields: %s" % ", ".join(missing)

    if fr1_ok:
        if not isinstance(report["design_under_test"], str):
            fr1_ok = False
            fr1_reason = "design_under_test must be a string"
        elif not isinstance(report["trojan_present"], bool):
            fr1_ok = False
            fr1_reason = "trojan_present must be a boolean"
        elif not isinstance(report["suspect_nets"], list):
            fr1_ok = False
            fr1_reason = "suspect_nets must be an array"
        elif not isinstance(report["trigger_condition"], dict):
            fr1_ok = False
            fr1_reason = "trigger_condition must be an object"
        elif not isinstance(report["affected_outputs"], list):
            fr1_ok = False
            fr1_reason = "affected_outputs must be an array"
        elif not isinstance(report["evidence"], str):
            fr1_ok = False
            fr1_reason = "evidence must be a string"

    if fr1_ok:
        for i, entry in enumerate(report["suspect_nets"]):
            if not isinstance(entry, dict):
                fr1_ok = False
                fr1_reason = "suspect_nets[%d] is not an object" % i
                break
            for key in ("net_name", "gate_instance", "role"):
                if key not in entry:
                    fr1_ok = False
                    fr1_reason = "suspect_nets[%d] missing '%s'" % (i, key)
                    break
            if not fr1_ok:
                break
            if not isinstance(entry["net_name"], str) or not isinstance(entry["gate_instance"], str):
                fr1_ok = False
                fr1_reason = "suspect_nets[%d] net_name/gate_instance must be strings" % i
                break
            if entry["role"] not in ("trigger", "payload", "benign"):
                fr1_ok = False
                fr1_reason = "suspect_nets[%d] role '%s' not in [trigger,payload,benign]" % (i, entry["role"])
                break

    tc = report.get("trigger_condition") if fr1_ok else None
    if fr1_ok:
        if "address" not in tc or "control_inputs" not in tc:
            fr1_ok = False
            fr1_reason = "trigger_condition missing 'address' or 'control_inputs'"
        elif not isinstance(tc.get("control_inputs"), dict):
            fr1_ok = False
            fr1_reason = "trigger_condition.control_inputs must be an object"
        else:
            control_inputs = tc["control_inputs"]
            declared_control_ports = input_ports - {"clk", "addr", "rst"}
            for cname in control_inputs.keys():
                if cname not in ports:
                    fr1_ok = False
                    fr1_reason = "control_inputs key '%s' is not a declared port in decoder_netlist.v" % cname
                    break
            if fr1_ok and "write_en" not in control_inputs:
                if "write_en" in declared_control_ports:
                    fr1_ok = False
                    fr1_reason = "control_inputs must include 'write_en' as declared in decoder_netlist.v"

    record("FR1", fr1_ok, fr1_reason)

    # =========================================================
    # FR2: design_under_test literal + address format
    # =========================================================
    fr2_ok = True
    fr2_reason = ""
    if not isinstance(report.get("design_under_test"), str) or report.get("design_under_test") != "decoder_netlist.v":
        fr2_ok = False
        fr2_reason = "design_under_test must equal 'decoder_netlist.v' (got %r)" % (report.get("design_under_test"),)
    else:
        addr_val = None
        try:
            addr_val = report["trigger_condition"]["address"]
        except Exception:
            fr2_ok = False
            fr2_reason = "trigger_condition.address missing"
        if fr2_ok:
            if not isinstance(addr_val, str) or not re.match(r'^[01]{3}$', addr_val):
                fr2_ok = False
                fr2_reason = "trigger_condition.address must be a 3-character '0'/'1' string (got %r)" % (addr_val,)

    record("FR2", fr2_ok, fr2_reason)

    # =========================================================
    # FR3: affected_outputs are valid output ports; >=2 if trojan_present
    # =========================================================
    fr3_ok = True
    fr3_reason = ""
    affected = report.get("affected_outputs")
    if not isinstance(affected, list):
        fr3_ok = False
        fr3_reason = "affected_outputs is not a list"
    else:
        bad = [a for a in affected if a not in output_ports]
        if bad:
            fr3_ok = False
            fr3_reason = "affected_outputs contains names not declared as output ports in decoder_netlist.v: %s" % bad
        elif report.get("trojan_present") is True and len(set(affected)) < 2:
            fr3_ok = False
            fr3_reason = "affected_outputs must contain at least 2 distinct entries when trojan_present is true (got %s)" % affected

    record("FR3", fr3_ok, fr3_reason)

    # =========================================================
    # FR4: single-address scoping (schema must not encode multi-address
    # blanket claims -- trigger_condition/affected_outputs must be a
    # singular object/list, not an array-of-conditions)
    # =========================================================
    fr4_ok = True
    fr4_reason = ""
    if not isinstance(report.get("trigger_condition"), dict):
        fr4_ok = False
        fr4_reason = "trigger_condition must be a single object (scoped to one address), not a list"
    elif not isinstance(report.get("affected_outputs"), list):
        fr4_ok = False
        fr4_reason = "affected_outputs must be a single flat list of output names"
    else:
        for item in report.get("affected_outputs", []):
            if not isinstance(item, str):
                fr4_ok = False
                fr4_reason = "affected_outputs entries must be plain strings, not nested structures (found %r)" % (item,)
                break

    record("FR4", fr4_ok, fr4_reason)

    # =========================================================
    # Run exhaustive simulation (needed for SR2, SR3, SR5)
    # =========================================================
    sim_table, sim_err = run_exhaustive_simulation()

    # =========================================================
    # SR1: trojan_present == true
    # =========================================================
    sr1_ok = report.get("trojan_present") is True
    record("SR1", sr1_ok, "" if sr1_ok else "trojan_present must be true (got %r)" % (report.get("trojan_present"),))

    # =========================================================
    # SR2: trigger_condition.address == '011', control_inputs.write_en == '1'
    # =========================================================
    sr2_ok = True
    sr2_reason = ""
    tc = report.get("trigger_condition") if isinstance(report.get("trigger_condition"), dict) else {}
    addr_str = tc.get("address") if isinstance(tc, dict) else None
    control_inputs = tc.get("control_inputs") if isinstance(tc, dict) else {}
    write_en_val = None
    if isinstance(control_inputs, dict):
        for k, v in control_inputs.items():
            if k.strip().lower() == "write_en":
                write_en_val = str(v).strip()
                break

    if not isinstance(addr_str, str) or addr_str.strip() != "011":
        sr2_ok = False
        sr2_reason = "trigger_condition.address must be '011' (got %r)" % (addr_str,)
    elif write_en_val != "1":
        sr2_ok = False
        sr2_reason = "trigger_condition.control_inputs['write_en'] must be '1' (got %r)" % (write_en_val,)
    else:
        if sim_table is not None:
            vec = sim_table.get(("011", "1"))
            if vec is None:
                sr2_ok = False
                sr2_reason = "simulation did not produce a vector for addr=011,we=1"
            else:
                asserted = {k for k, v in vec.items() if v == "1"}
                if len(asserted) < 2:
                    sr2_ok = False
                    sr2_reason = ("simulation cross-check: addr=011,we=1 does not assert multiple "
                                  "bank write-enables in decoder_netlist.v (got %s)" % asserted)
        else:
            sr2_ok = False
            sr2_reason = "exhaustive simulation unavailable for cross-check: %s" % sim_err

    record("SR2", sr2_ok, sr2_reason)

    # =========================================================
    # SR3: affected_outputs == {bank0_we, bank2_we} exactly
    # =========================================================
    sr3_ok = True
    sr3_reason = ""
    affected_set = set(report.get("affected_outputs") or [])
    expected_set = {"bank0_we", "bank2_we"}
    if affected_set != expected_set:
        sr3_ok = False
        sr3_reason = "affected_outputs must equal exactly %s (got %s)" % (sorted(expected_set), sorted(affected_set))
    else:
        if sim_table is not None:
            vec = sim_table.get(("011", "1"))
            if vec is not None:
                ground_truth_asserted = {k for k, v in vec.items() if v == "1"}
                if ground_truth_asserted != expected_set:
                    sr3_ok = False
                    sr3_reason = ("simulation cross-check mismatch: ground truth asserted set at "
                                  "addr=011,we=1 is %s, expected %s" % (sorted(ground_truth_asserted), sorted(expected_set)))
            else:
                sr3_ok = False
                sr3_reason = "simulation did not produce a vector for addr=011,we=1"
        else:
            sr3_ok = False
            sr3_reason = "exhaustive simulation unavailable for cross-check: %s" % sim_err

    record("SR3", sr3_ok, sr3_reason)

    # =========================================================
    # SR4: suspect_nets identifies the actual bridging gate (structural)
    # =========================================================
    sr4_ok = True
    sr4_reason = ""
    try:
        trace = trace_bank2_structural_suspects(ports, instances, assigns)
    except Exception as e:
        trace = {"candidate_names": set(), "bank2_alias_instances": set(),
                  "bank2_alias_nets": set(), "minterm3_signal_nets": set()}
        sr4_ok = False
        sr4_reason = "internal structural trace failed: %s" % str(e)

    if sr4_ok:
        candidates = trace["candidate_names"]
        if not candidates:
            sr4_ok = False
            sr4_reason = "could not structurally identify any bank2_we aliasing gate in decoder_netlist.v (parser found none)"
        else:
            suspect_entries = report.get("suspect_nets") or []
            match_found = False
            for entry in suspect_entries:
                if not isinstance(entry, dict):
                    continue
                role = entry.get("role")
                if role not in ("trigger", "payload"):
                    continue
                net_name = str(entry.get("net_name", "")).strip()
                gate_instance = str(entry.get("gate_instance", "")).strip()
                if net_name in candidates or gate_instance in candidates:
                    match_found = True
                    break
                if any(net_name.lower() == c.lower() or gate_instance.lower() == c.lower()
                       for c in candidates):
                    match_found = True
                    break
            if not match_found:
                sr4_ok = False
                sr4_reason = ("suspect_nets does not identify the structural bridging gate "
                              "feeding bank2_we from the address==011 decode tap with role "
                              "'trigger' or 'payload' (expected one of net/instance names: %s)"
                              % sorted(candidates))

    record("SR4", sr4_ok, sr4_reason)

    # =========================================================
    # SR5: no false-positive anomalies beyond addr=011
    # =========================================================
    sr5_ok = True
    sr5_reason = ""
    if sim_table is None:
        sr5_ok = False
        sr5_reason = "exhaustive simulation failed, cannot cross-check false positives: %s" % sim_err
    else:
        gt_anomalies = ground_truth_anomalous_addresses(sim_table)  # addr -> set(asserted)
        reported_addr = addr_str if isinstance(addr_str, str) else None

        if "011" not in gt_anomalies:
            sr5_ok = False
            sr5_reason = ("exhaustive simulation ground truth does not show an anomaly at addr=011 "
                          "(got anomalous addresses: %s)" % sorted(gt_anomalies.keys()))
        elif reported_addr not in gt_anomalies:
            sr5_ok = False
            sr5_reason = ("reported trigger_condition.address (%r) is not the address exhibiting "
                          "the ground-truth anomaly (%s)" % (reported_addr, sorted(gt_anomalies.keys())))
        else:
            other_anomalous = set(gt_anomalies.keys()) - {reported_addr}
            if other_anomalous:
                sr5_ok = False
                sr5_reason = ("exhaustive simulation shows additional anomalous addresses beyond the "
                              "reported one: %s" % sorted(other_anomalous))

    record("SR5", sr5_ok, sr5_reason)

    # =========================================================
    # Final verdict
    # =========================================================
    all_pass = all(ok for ok, _ in results.values())
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()