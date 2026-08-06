#!/usr/bin/env python3
"""
evaluate.py -- Grader for gate_trojan_detection_power_isolation_bypass_001

Grades submission/trojan_report.json against the reference netlist under
inputs/. Uses iverilog/vvp to exhaustively simulate the netlist over all
32 (secure_data[3:0], power_down) combinations to derive ground truth
(trojan presence, affected output bits, and bypass-path instance names)
purely from observed/parsed behavior -- no hardcoded netlist knowledge.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUTS_DIR = os.path.join(REPO_ROOT, "inputs")
SUBMISSION_PATH = os.path.join(REPO_ROOT, "submission", "trojan_report.json")
NETLIST_PATH = os.path.join(INPUTS_DIR, "isolation_wrapper_netlist.v")
PRIMLIB_PATH = os.path.join(INPUTS_DIR, "primitive_library.v")
TB_PATH = os.path.join(REPO_ROOT, "evaluation", "tb_isolation.v")

SIM_TIMEOUT = 30

results = []  # list of (req_id, passed_bool, message)


def record(req_id, passed, msg=""):
    if passed:
        print("[TEST] PASS: %s" % req_id)
    else:
        print("[TEST] FAIL: %s: %s" % (req_id, msg))
    results.append((req_id, passed, msg))


def fail_setup_all(req_ids, msg):
    for rid in req_ids:
        record(rid, False, "SETUP: " + msg)


ALL_REQ_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]


def read_file_or_setup_fail(path, label):
    if not os.path.isfile(path):
        fail_setup_all(ALL_REQ_IDS, "%s not found" % label)
        print_summary_and_exit()
    with open(path, "r") as f:
        return f.read()


def print_summary_and_exit():
    failed = [r for r in results if not r[1]]
    if failed:
        sys.exit(1)
    else:
        sys.exit(0)


# ---------------------------------------------------------------------------
# Step 0: locate required files
# ---------------------------------------------------------------------------

missing = []
if not os.path.isfile(NETLIST_PATH):
    missing.append("inputs/isolation_wrapper_netlist.v")
if not os.path.isfile(PRIMLIB_PATH):
    missing.append("inputs/primitive_library.v")
if not os.path.isfile(TB_PATH):
    missing.append("evaluation/tb_isolation.v")

if missing:
    fail_setup_all(ALL_REQ_IDS, "required file(s) not found: " + ", ".join(missing))
    print_summary_and_exit()

if not os.path.isfile(SUBMISSION_PATH):
    fail_setup_all(ALL_REQ_IDS, "submission/trojan_report.json not found")
    print_summary_and_exit()

with open(NETLIST_PATH, "r") as f:
    netlist_text = f.read()

with open(SUBMISSION_PATH, "r") as f:
    raw_submission_text = f.read()

# ---------------------------------------------------------------------------
# Step 1: parse submission JSON (needed for all FR/SR checks)
# ---------------------------------------------------------------------------

submission = None
json_parse_error = None
try:
    submission = json.loads(raw_submission_text)
except Exception as e:
    json_parse_error = str(e)

# ---------------------------------------------------------------------------
# Step 2: FR1 -- schema validation
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {
    "trojan_present": bool,
    "confidence": (int, float),
    "suspect_nodes": list,
    "affected_outputs": list,
    "violating_condition": str,
    "analysis_summary": str,
}

fr1_ok = True
fr1_msg = ""

if json_parse_error is not None:
    fr1_ok = False
    fr1_msg = "submission is not valid JSON: %s" % json_parse_error
elif not isinstance(submission, dict):
    fr1_ok = False
    fr1_msg = "top-level JSON value is not an object"
else:
    missing_fields = []
    wrong_type_fields = []
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in submission:
            missing_fields.append(field)
            continue
        val = submission[field]
        if expected_type is bool:
            # bool is subclass of int in python; must check strictly
            if not isinstance(val, bool):
                wrong_type_fields.append(field)
        elif expected_type == (int, float):
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                wrong_type_fields.append(field)
        elif expected_type is list:
            if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
                wrong_type_fields.append(field)
        elif expected_type is str:
            if not isinstance(val, str):
                wrong_type_fields.append(field)

    if missing_fields:
        fr1_ok = False
        fr1_msg = "missing required field(s): " + ", ".join(missing_fields)
    elif wrong_type_fields:
        fr1_ok = False
        fr1_msg = "field(s) with wrong type: " + ", ".join(wrong_type_fields)
    else:
        conf = submission.get("confidence")
        if isinstance(conf, (int, float)) and not isinstance(conf, bool):
            if conf < 0.0 or conf > 1.0:
                fr1_ok = False
                fr1_msg = "confidence %r out of range [0.0, 1.0]" % conf

record("FR1", fr1_ok, fr1_msg)

# If FR1 fails hard (no dict at all), we cannot safely proceed to inspect
# other fields; fail everything else as well with a clear reason.
if not isinstance(submission, dict):
    for rid in ["FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]:
        record(rid, False, "cannot evaluate: submission JSON is malformed/missing required structure")
    print_summary_and_exit()


def safe_get(field, default):
    val = submission.get(field, default)
    return val


trojan_present = safe_get("trojan_present", None)
suspect_nodes = safe_get("suspect_nodes", None)
affected_outputs = safe_get("affected_outputs", None)
violating_condition = safe_get("violating_condition", None)

if not isinstance(suspect_nodes, list):
    suspect_nodes = []
if not isinstance(affected_outputs, list):
    affected_outputs = []
if not isinstance(violating_condition, str):
    violating_condition = ""

# ---------------------------------------------------------------------------
# Step 3: FR2 -- trojan_present must be true
# ---------------------------------------------------------------------------

if isinstance(trojan_present, bool) and trojan_present is True:
    record("FR2", True)
else:
    record("FR2", False, "trojan_present is %r, expected true" % (trojan_present,))

# ---------------------------------------------------------------------------
# Step 4: parse netlist for structural instance names (AND2/OR2/MUX2)
# ---------------------------------------------------------------------------
# Verilog instantiation syntax (allowing optional parameter list):
#   TYPE #( ... )? NAME ( .port(net), .port2(net2), ... ) ;
# We capture: instance type, instance name, and the full port-connection body.

INSTANCE_RE = re.compile(
    r'\b(AND2|OR2|MUX2)\b\s*(?:#\s*\([^)]*\)\s*)?'
    r'([A-Za-z_][A-Za-z0-9_$]*)\s*'
    r'\(\s*(.*?)\s*\)\s*;',
    re.DOTALL,
)

# named port connection: .portname(netexpr)
PORT_CONN_RE = re.compile(r'\.\s*([A-Za-z_][A-Za-z0-9_$]*)\s*\(\s*([^()]*?)\s*\)')

instances = []  # list of dicts: {type, name, ports: {portname: net_expr}}
for m in INSTANCE_RE.finditer(netlist_text):
    itype, iname, body = m.group(1), m.group(2), m.group(3)
    ports = {}
    for pm in PORT_CONN_RE.finditer(body):
        pname, pnet = pm.group(1), pm.group(2).strip()
        ports[pname] = pnet
    instances.append({"type": itype, "name": iname, "ports": ports})

valid_instance_names = set(inst["name"] for inst in instances)

# Also parse any `assign` statements to extract net-to-net / net-to-port
# connectivity (e.g. `assign public_out[0] = net_bypass_bit0;`), so we can
# build a driver graph purely from netlist syntax.
ASSIGN_RE = re.compile(
    r'\bassign\s+([A-Za-z_][A-Za-z0-9_$]*(?:\s*\[\s*\d+\s*\])?)\s*=\s*([^;]+);'
)
assigns = []
for m in ASSIGN_RE.finditer(netlist_text):
    lhs, rhs = m.group(1), m.group(2).strip()
    assigns.append((lhs, rhs))


def normalize_net_token(tok):
    """Strip whitespace; collapse bit-select spacing e.g. 'foo [0]' -> 'foo[0]'."""
    tok = tok.strip()
    tok = re.sub(r'\s*\[\s*(\d+)\s*\]', r'[\1]', tok)
    return tok


# Build a mapping from a net/wire base name -> set of instance names whose
# output ('y' port) drives that net, and a mapping from instance name -> set
# of net names appearing on its input ports ('a', 'b', 'sel').
net_driven_by = {}   # net_name -> set(instance_name)
inst_inputs = {}      # instance_name -> set(net_name) referenced on input ports
inst_output_net = {}  # instance_name -> net_name on 'y' port

for inst in instances:
    name = inst["name"]
    ports = inst["ports"]
    inputs_here = set()
    for pname, pnet in ports.items():
        pnet_norm = normalize_net_token(pnet)
        if pname == "y":
            inst_output_net[name] = pnet_norm
            net_driven_by.setdefault(pnet_norm, set()).add(name)
        else:
            inputs_here.add(pnet_norm)
    inst_inputs[name] = inputs_here

# Also register assign-based drivers: if `assign lhs = rhs;`, then lhs is
# "driven by" whatever instance(s) drive rhs (if rhs is a simple net name),
# and rhs contributes as an "input-like" dependency of lhs's driving graph.
assign_driven_by = {}  # lhs_net -> set of rhs net tokens it depends on
for lhs, rhs in assigns:
    lhs_norm = normalize_net_token(lhs)
    # rhs might be a simple identifier (possibly with bit-select) or an
    # expression; extract identifier-like tokens referenced.
    rhs_tokens = re.findall(r'[A-Za-z_][A-Za-z0-9_$]*(?:\s*\[\s*\d+\s*\])?', rhs)
    rhs_tokens = [normalize_net_token(t) for t in rhs_tokens]
    assign_driven_by.setdefault(lhs_norm, set()).update(rhs_tokens)

# ---------------------------------------------------------------------------
# Step 5: FR3 -- suspect_nodes must include at least one real instance name
# ---------------------------------------------------------------------------

fr3_matches = [s for s in suspect_nodes if s in valid_instance_names]
if fr3_matches:
    record("FR3", True)
else:
    record("FR3", False,
           "no suspect_nodes entry matches a real instance name in isolation_wrapper_netlist.v "
           "(valid instances: %s)" % (sorted(valid_instance_names),))

# ---------------------------------------------------------------------------
# Step 6: FR4 -- affected_outputs well-formed bit-indexed references
# ---------------------------------------------------------------------------

OUTPUT_BIT_RE = re.compile(r'^public_out\[([0-3])\]$')

fr4_ok = True
fr4_msg = ""
if len(affected_outputs) == 0:
    fr4_ok = False
    fr4_msg = "affected_outputs is empty"
else:
    bad = [s for s in affected_outputs if not OUTPUT_BIT_RE.match(s)]
    if bad:
        fr4_ok = False
        fr4_msg = "affected_outputs contains malformed entries (expected 'public_out[N]' N=0-3): %s" % bad

record("FR4", fr4_ok, fr4_msg)

# ---------------------------------------------------------------------------
# Step 7: run exhaustive simulation via iverilog/vvp to get ground truth
# ---------------------------------------------------------------------------

def run_simulation():
    """
    Compile and run the testbench against the real netlist + primitive
    library. Returns a list of 32 dicts:
      {"secure_data": int(0-15), "power_down": int(0/1), "public_out": int(0-15)}
    or raises RuntimeError with a diagnostic message on failure.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        sim_bin = os.path.join(tmpdir, "sim.vvp")
        compile_cmd = [
            "iverilog", "-g2012", "-o", sim_bin,
            NETLIST_PATH, PRIMLIB_PATH, TB_PATH,
        ]
        try:
            proc = subprocess.run(
                compile_cmd, cwd=REPO_ROOT,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=SIM_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("iverilog compilation timed out")
        except FileNotFoundError:
            raise RuntimeError("iverilog not found on PATH")

        if proc.returncode != 0:
            stderr_txt = proc.stderr.decode("utf-8", errors="replace")
            raise RuntimeError("compile failed: %s" % stderr_txt[:2000])

        try:
            run_proc = subprocess.run(
                ["vvp", sim_bin], cwd=REPO_ROOT,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=SIM_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("vvp simulation timed out")
        except FileNotFoundError:
            raise RuntimeError("vvp not found on PATH")

        if run_proc.returncode != 0:
            stderr_txt = run_proc.stderr.decode("utf-8", errors="replace")
            raise RuntimeError("simulation run failed: %s" % stderr_txt[:2000])

        out_text = run_proc.stdout.decode("utf-8", errors="replace")

        vec_re = re.compile(
            r'VEC\s+secure_data=([01]{4})\s+power_down=([01])\s+public_out=([01]{4})'
        )
        vectors = []
        for m in vec_re.finditer(out_text):
            sd_bits, pd_bit, po_bits = m.group(1), m.group(2), m.group(3)
            sd_val = int(sd_bits, 2)
            pd_val = int(pd_bit, 2)
            po_val = int(po_bits, 2)
            vectors.append({
                "secure_data": sd_val,
                "power_down": pd_val,
                "public_out": po_val,
            })

        if len(vectors) < 32:
            raise RuntimeError(
                "expected 32 simulated vectors, got %d; raw output: %s"
                % (len(vectors), out_text[:2000])
            )

        return vectors


sim_error = None
sim_vectors = None
try:
    sim_vectors = run_simulation()
except RuntimeError as e:
    sim_error = str(e)

# ---------------------------------------------------------------------------
# Step 8: compute ground truth from simulation
# ---------------------------------------------------------------------------

# expected contract: public_out = 0 when power_down=1, else public_out = secure_data
mismatched_bits = set()  # set of ints 0-3
mismatch_vectors = []    # list of (secure_data, power_down, actual_public_out, expected)

if sim_vectors is not None:
    for v in sim_vectors:
        sd = v["secure_data"]
        pd = v["power_down"]
        po = v["public_out"]
        expected = 0 if pd == 1 else sd
        if po != expected:
            mismatch_vectors.append((sd, pd, po, expected))
            diff = po ^ expected
            for bit in range(4):
                if (diff >> bit) & 1:
                    mismatched_bits.add(bit)

ground_truth_trojan_present = len(mismatched_bits) > 0

# ---------------------------------------------------------------------------
# Step 9: SR1 -- trojan_present must match simulated ground truth
# ---------------------------------------------------------------------------

if sim_error is not None:
    record("SR1", False, "could not establish ground truth via simulation: %s" % sim_error)
else:
    if isinstance(trojan_present, bool) and trojan_present == ground_truth_trojan_present:
        record("SR1", True)
    else:
        record("SR1", False,
               "trojan_present=%r but simulation shows ground truth=%r (mismatched bits=%s)"
               % (trojan_present, ground_truth_trojan_present, sorted(mismatched_bits)))

# ---------------------------------------------------------------------------
# Step 10: SR2 -- affected_outputs must equal exactly the mismatched bit set
# ---------------------------------------------------------------------------

if sim_error is not None:
    record("SR2", False, "could not establish ground truth via simulation: %s" % sim_error)
else:
    reported_bits = set()
    for s in affected_outputs:
        m = OUTPUT_BIT_RE.match(s)
        if m:
            reported_bits.add(int(m.group(1)))

    if reported_bits == mismatched_bits:
        record("SR2", True)
    else:
        record("SR2", False,
               "affected_outputs bits=%s do not exactly match ground-truth compromised bits=%s"
               % (sorted(reported_bits), sorted(mismatched_bits)))

# ---------------------------------------------------------------------------
# Step 11: SR3 -- suspect_nodes must include an instance on the fan-in cone
#          of a mismatched output bit
# ---------------------------------------------------------------------------


def resolve_output_bit_source_net(bit_index):
    """
    Find the net expression that ultimately drives public_out[bit_index],
    by scanning assign statements and port connections in the netlist for
    references to 'public_out[bit_index]' or a vector assignment to
    'public_out' as LHS.
    Returns a normalized net token string, or None if not resolvable.
    """
    target_indexed = "public_out[%d]" % bit_index

    # Direct: assign public_out[N] = <net>;
    for lhs, rhs in assigns:
        lhs_norm = normalize_net_token(lhs)
        if lhs_norm == target_indexed:
            rhs_tokens = re.findall(r'[A-Za-z_][A-Za-z0-9_$]*(?:\s*\[\s*\d+\s*\])?', rhs)
            if rhs_tokens:
                return normalize_net_token(rhs_tokens[0])

    # Also consider: an instance whose output port 'y' is directly wired to
    # public_out[N] (e.g. .y(public_out[N]) in the instantiation itself).
    for inst in instances:
        y_net = inst["ports"].get("y")
        if y_net is not None and normalize_net_token(y_net) == target_indexed:
            return inst["name"]  # the instance itself is the direct driver

    return None


def backward_reachable_instances(start_token, max_depth=50):
    """
    Given a starting token (either a net name or an instance name), walk
    backward through the driver graph (net_driven_by, inst_inputs,
    assign_driven_by) to collect all instance names in the fan-in cone.
    """
    visited_nets = set()
    visited_insts = set()
    frontier = [start_token]
    depth = 0

    # If start_token is itself a known instance name, seed with its inputs.
    if start_token in valid_instance_names:
        visited_insts.add(start_token)
        frontier = list(inst_inputs.get(start_token, set()))

    while frontier and depth < max_depth:
        depth += 1
        next_frontier = []
        for tok in frontier:
            if tok in visited_nets:
                continue
            visited_nets.add(tok)

            # Which instances drive this net via their 'y' port?
            drivers = net_driven_by.get(tok, set())
            for d in drivers:
                if d not in visited_insts:
                    visited_insts.add(d)
                    for inp_net in inst_inputs.get(d, set()):
                        if inp_net not in visited_nets:
                            next_frontier.append(inp_net)

            # Which assign statements drive this net (possibly indexed)?
            # Try exact match and also base-name match (vector assigns).
            for lhs_net, rhs_nets in assign_driven_by.items():
                if lhs_net == tok:
                    for rn in rhs_nets:
                        if rn not in visited_nets:
                            next_frontier.append(rn)
                        # rn might itself be an instance-driven net
                        for d in net_driven_by.get(rn, set()):
                            if d not in visited_insts:
                                visited_insts.add(d)
                                for inp_net in inst_inputs.get(d, set()):
                                    if inp_net not in visited_nets:
                                        next_frontier.append(inp_net)
        frontier = next_frontier

    return visited_insts


if sim_error is not None:
    record("SR3", False, "could not establish ground truth via simulation: %s" % sim_error)
elif not mismatched_bits:
    record("SR3", False,
           "no compromised bit identified by simulation; cannot validate suspect_nodes bypass-path relevance")
else:
    # Build the union of fan-in-cone instances across all mismatched bits.
    relevant_instances = set()
    unresolved_bits = []
    for bit in mismatched_bits:
        src = resolve_output_bit_source_net(bit)
        if src is None:
            unresolved_bits.append(bit)
            continue
        cone = backward_reachable_instances(src)
        relevant_instances |= cone

    if not relevant_instances:
        record("SR3", False,
               "could not structurally resolve any instance on the fan-in cone of compromised bit(s) %s "
               "(unresolved bits: %s)" % (sorted(mismatched_bits), unresolved_bits))
    else:
        matched = [s for s in suspect_nodes if s in relevant_instances]
        if matched:
            record("SR3", True)
        else:
            record("SR3", False,
                   "suspect_nodes %s does not include any instance on the fan-in cone of the compromised "
                   "bit(s) %s (expected one of: %s)"
                   % (suspect_nodes, sorted(mismatched_bits), sorted(relevant_instances)))

# ---------------------------------------------------------------------------
# Step 12: SR4 -- violating_condition must correctly describe the trigger
# ---------------------------------------------------------------------------

def mentions_power_down_asserted(text):
    t = text.lower()
    patterns = [
        r'power_down\s*=\s*1\b',
        r'power_down\s*==\s*1\b',
        r'power_down\s+is\s+(?:asserted|set|high|1)\b',
        r'power[_\s]?down\s+asserted\b',
        r'\bpower_down\b.{0,20}\basserted\b',
        r'\bpower_down\b.{0,20}\b(?:high|set|1)\b',
    ]
    return any(re.search(p, t) for p in patterns)


def mentions_secure_data_bit0_set(text):
    t = text.lower()
    patterns = [
        r'secure_data\s*\[\s*0\s*\]\s*=\s*1\b',
        r'secure_data\s*\[\s*0\s*\]\s*==\s*1\b',
        r'secure_data\s*\[\s*0\s*\]\s+is\s+(?:set|1|high)\b',
        r'secure_data\s*\[\s*0\s*\]\b.{0,20}\b(?:set|1|high|asserted)\b',
        r'\bbit\s*0\b.{0,30}\bsecure_data\b.{0,20}\b(?:set|1|high)\b',
        r'secure_data\[0\]',  # loose fallback: presence of exact indexed token near '1'
        r'\bbit\s*0\s+(?:of\s+)?secure_data\b.{0,20}\b(?:set|1|high)\b',
    ]
    # require at least one strong pattern OR ('secure_data[0]' token AND a '1' nearby)
    if re.search(r'secure_data\s*\[\s*0\s*\]', t):
        # ensure a '1'/set/high/asserted appears reasonably near it
        idx = re.search(r'secure_data\s*\[\s*0\s*\]', t).end()
        window = t[idx:idx + 40]
        if re.search(r'(?:=\s*1\b|==\s*1\b|\bset\b|\bhigh\b|\basserted\b|\b1\b)', window):
            return True
    return any(re.search(p, t) for p in patterns[:5])


sr4_text_ok = mentions_power_down_asserted(violating_condition) and mentions_secure_data_bit0_set(violating_condition)

if sim_error is not None:
    record("SR4", False, "could not cross-simulate violating vector: %s" % sim_error)
elif not sr4_text_ok:
    record("SR4", False,
           "violating_condition does not clearly describe power_down=1 AND secure_data[0]=1 as the "
           "failing condition: %r" % violating_condition)
else:
    # Cross-simulate the specific vector: secure_data[0]=1, power_down=1,
    # other secure_data bits = 0. Confirm public_out[0]=1 (i.e. the leak).
    target_vec = None
    for v in sim_vectors:
        if v["power_down"] == 1 and (v["secure_data"] & 0x1) == 1 and v["secure_data"] == 0x1:
            target_vec = v
            break

    if target_vec is None:
        record("SR4", False, "could not locate simulated vector for secure_data=0001, power_down=1")
    else:
        po = target_vec["public_out"]
        bit0 = po & 0x1
        if bit0 == 1:
            record("SR4", True)
        else:
            record("SR4", False,
                   "simulation of power_down=1, secure_data[0]=1 yields public_out[0]=%d, "
                   "not the claimed leak (expected 1)" % bit0)

# ---------------------------------------------------------------------------
# Final: exit code
# ---------------------------------------------------------------------------

print_summary_and_exit()