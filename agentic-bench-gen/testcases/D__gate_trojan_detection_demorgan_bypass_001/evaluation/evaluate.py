#!/usr/bin/env python3
"""
evaluate.py - grader for gate_trojan_detection_demorgan_bypass_001

Grades submission/trojan_report.json against ground truth derived
programmatically from inputs/perm_cone_netlist.v and
inputs/reference_truth_table.txt.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

NETLIST_PATH = "inputs/perm_cone_netlist.v"
TRUTH_TABLE_PATH = "inputs/reference_truth_table.txt"
SUBMISSION_PATH = "submission/trojan_report.json"
TB_PATH = "evaluation/tb_perm_cone.v"

overall_pass = True
results = []  # (req_id, passed, reason)


def record(req_id, passed, reason=""):
    global overall_pass
    if passed:
        print("[TEST] PASS: %s" % req_id)
    else:
        print("[TEST] FAIL: %s: %s" % (req_id, reason))
        overall_pass = False
    results.append((req_id, passed, reason))


def fail_setup(msg):
    print("[TEST] FAIL: SETUP: %s" % msg)
    sys.exit(1)


# ---------------------------------------------------------------------
# Load input artifacts
# ---------------------------------------------------------------------

def load_text(path):
    if not os.path.isfile(path):
        fail_setup("%s not found" % path)
    with open(path, "r") as f:
        return f.read()


netlist_text = load_text(NETLIST_PATH)
truth_text = load_text(TRUTH_TABLE_PATH)

if not os.path.isfile(SUBMISSION_PATH):
    fail_setup("%s not found" % SUBMISSION_PATH)

with open(SUBMISSION_PATH, "r") as f:
    raw_submission_text = f.read()

try:
    submission = json.loads(raw_submission_text)
except Exception as e:
    # Treat as a totally malformed report: fail every requirement.
    for rid in ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]:
        record(rid, False, "submission JSON parse error: %s" % e)
    sys.exit(1)


# ---------------------------------------------------------------------
# Parse reference truth table
# ---------------------------------------------------------------------

def parse_truth_table(text):
    table = {}
    line_re = re.compile(
        r'^\s*([01]{2})\s+([01]{3})\s*:\s*([01])\s*$'
    )
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = line_re.match(line)
        if not m:
            continue
        req_level, owner_id, grant = m.group(1), m.group(2), int(m.group(3))
        table[(req_level, owner_id)] = grant
    return table


truth_table = parse_truth_table(truth_text)
if len(truth_table) != 32:
    fail_setup(
        "reference_truth_table.txt did not yield 32 valid entries (got %d)"
        % len(truth_table)
    )


# ---------------------------------------------------------------------
# Gate-level Verilog netlist parser + simulator (regex-based, supports
# primitive-cell modules inv/nand2/nand3/nor2 instantiated with named
# port connections, plus simple wire alias declarations).
# ---------------------------------------------------------------------

PRIM_TYPES = {"inv", "nand2", "nand3", "nor2"}

# Matches instantiation lines like:
#   inv u_inv_a1 (.a(a1), .y(n_a1));
#   nand3 u_perm_nand3 (.a(o2), .b(n_o1), .c(o0), .y(owner_qual_n));
INSTANCE_RE = re.compile(
    r'\b(inv|nand2|nand3|nor2)\s+(\w+)\s*\(([^;]*?)\)\s*;',
    re.DOTALL,
)

# Matches named port connections like .a(o2) or .y(owner_qual_n)
PORT_CONN_RE = re.compile(r'\.\s*(\w+)\s*\(\s*([\w\[\]:]+)\s*\)')

# Matches simple wire alias declarations like:
#   wire a1 = req_level[1];
#   wire n_a1, n_a0;   (no init, ignored except as declared names)
WIRE_ASSIGN_RE = re.compile(
    r'\bwire\s+(\w+)\s*=\s*([\w\[\]]+)\s*(?:\[(\d+)\])?\s*;'
)


def strip_comments(text):
    # remove // line comments and /* */ block comments
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    text = re.sub(r'//.*', '', text)
    return text


def extract_module_body(text, module_name="perm_cone"):
    """Extract the body of `module perm_cone ( ... ) ... endmodule`."""
    pattern = re.compile(
        r'\bmodule\s+' + re.escape(module_name) + r'\b(.*?)\bendmodule\b',
        re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        return None
    return m.group(1)


def extract_instances(module_body):
    """Return list of (prim_type, instance_name, {port: signal})."""
    instances = []
    for m in INSTANCE_RE.finditer(module_body):
        prim_type, inst_name, ports_str = m.group(1), m.group(2), m.group(3)
        ports = {}
        for pm in PORT_CONN_RE.finditer(ports_str):
            port_name, sig = pm.group(1), pm.group(2)
            ports[port_name] = sig
        instances.append((prim_type, inst_name, ports))
    return instances


def extract_wire_aliases(module_body):
    """Return dict alias_name -> (base_signal, bit_index_or_None)."""
    aliases = {}
    for m in WIRE_ASSIGN_RE.finditer(module_body):
        alias_name, rhs, explicit_bit = m.group(1), m.group(2), m.group(3)
        # rhs might be like req_level[1] (bit index embedded in rhs itself)
        bit_m = re.match(r'(\w+)\[(\d+)\]', rhs)
        if bit_m:
            base_sig = bit_m.group(1)
            bit_idx = int(bit_m.group(2))
        else:
            base_sig = rhs
            bit_idx = None
        aliases[alias_name] = (base_sig, bit_idx)
    return aliases


def parse_all_instance_names(text):
    """Extract the set of ALL instance names in the whole file (for FR3),
    not just inside perm_cone module body, to be maximally permissive
    about where instances are declared."""
    cleaned = strip_comments(text)
    names = set()
    for m in INSTANCE_RE.finditer(cleaned):
        names.add(m.group(2))
    return names


cleaned_netlist = strip_comments(netlist_text)
module_body = extract_module_body(cleaned_netlist, "perm_cone")
if module_body is None:
    fail_setup("could not locate 'module perm_cone ... endmodule' in %s" % NETLIST_PATH)

netlist_instances = extract_instances(module_body)
wire_aliases = extract_wire_aliases(module_body)
all_instance_names = parse_all_instance_names(cleaned_netlist)

if len(netlist_instances) == 0:
    fail_setup("no primitive-cell instances found in perm_cone module body")


def eval_prim(prim_type, in_vals):
    """in_vals: list of 0/1 ints (order a,b[,c])."""
    if prim_type == "inv":
        a = in_vals[0]
        return 1 - a
    elif prim_type == "nand2":
        a, b = in_vals
        return 1 - (a & b)
    elif prim_type == "nand3":
        a, b, c = in_vals
        return 1 - (a & b & c)
    elif prim_type == "nor2":
        a, b = in_vals
        return 1 - (a | b)
    else:
        raise ValueError("unknown primitive type: %s" % prim_type)


INPUT_PORT_ORDER = {
    "inv": ["a"],
    "nand2": ["a", "b"],
    "nand3": ["a", "b", "c"],
    "nor2": ["a", "b"],
}


def resolve_signal_value(sig_name, signal_values, req_level_bits, owner_id_bits):
    """Resolve a signal name to a 0/1 value given current known signal_values
    dict, plus direct bit-vector indexing into req_level[n]/owner_id[n], plus
    wire alias definitions."""
    # direct indexed reference like req_level[1] or owner_id[2]
    idx_m = re.match(r'(\w+)\[(\d+)\]$', sig_name)
    if idx_m:
        base, idx = idx_m.group(1), int(idx_m.group(2))
        idx = int(idx)
        if base == "req_level":
            return req_level_bits[idx]
        if base == "owner_id":
            return owner_id_bits[idx]
        # fall through: maybe a multi-bit internal wire (not expected here)
        if base in signal_values:
            return signal_values[base]
        return None

    if sig_name == "req_level" or sig_name == "owner_id":
        # whole-vector reference unlikely for single-bit ports; unresolved
        return None

    if sig_name in signal_values:
        return signal_values[sig_name]

    if sig_name in wire_aliases:
        base_sig, bit_idx = wire_aliases[sig_name]
        if bit_idx is not None:
            if base_sig == "req_level":
                val = req_level_bits[bit_idx]
            elif base_sig == "owner_id":
                val = owner_id_bits[bit_idx]
            else:
                val = resolve_signal_value(
                    base_sig, signal_values, req_level_bits, owner_id_bits
                )
                if val is None:
                    return None
            signal_values[sig_name] = val
            return val
        else:
            val = resolve_signal_value(
                base_sig, signal_values, req_level_bits, owner_id_bits
            )
            if val is not None:
                signal_values[sig_name] = val
            return val

    return None


def simulate_netlist(req_level_str, owner_id_str, instances, forced_output=None):
    """Simulate perm_cone for a given input vector.

    req_level_str: 2-char '0'/'1' string, MSB first (bit index 1 is
    req_level_str[0], bit index 0 is req_level_str[1]) matching Verilog
    [1:0] convention where req_level[1] is the MSB.
    owner_id_str: 3-char '0'/'1' string, owner_id[2] is MSB.

    forced_output: optional dict {instance_name: forced_y_value} used for
    single-instance output-flip sensitivity analysis (SR3).

    Returns (grant_value, instance_output_values dict).
    """
    # Build bit arrays indexed by bit position (index 0 = LSB)
    req_level_bits = [int(req_level_str[1]), int(req_level_str[0])]  # [0]=LSB,[1]=MSB
    owner_id_bits = [
        int(owner_id_str[2]),
        int(owner_id_str[1]),
        int(owner_id_str[0]),
    ]  # [0]=LSB,[1],[2]=MSB

    signal_values = {}
    inst_outputs = {}

    forced_output = forced_output or {}

    max_iters = len(instances) + 5
    for _ in range(max_iters):
        changed = False
        for prim_type, inst_name, ports in instances:
            if inst_name in inst_outputs:
                continue
            in_names = INPUT_PORT_ORDER[prim_type]
            in_vals = []
            resolved = True
            for pname in in_names:
                if pname not in ports:
                    resolved = False
                    break
                sig = ports[pname]
                val = resolve_signal_value(
                    sig, signal_values, req_level_bits, owner_id_bits
                )
                if val is None:
                    resolved = False
                    break
                in_vals.append(val)
            if not resolved:
                continue
            if "y" not in ports:
                continue
            out_sig = ports["y"]
            if inst_name in forced_output:
                out_val = forced_output[inst_name]
            else:
                out_val = eval_prim(prim_type, in_vals)
            inst_outputs[inst_name] = out_val
            signal_values[out_sig] = out_val
            changed = True
        if not changed:
            break

    grant_val = resolve_signal_value(
        "grant", signal_values, req_level_bits, owner_id_bits
    )
    return grant_val, inst_outputs


ALL_VECTORS = []
for rl in range(4):
    for oid in range(8):
        req_level_str = format(rl, "02b")
        owner_id_str = format(oid, "03b")
        ALL_VECTORS.append((req_level_str, owner_id_str))


# ---------------------------------------------------------------------
# Compute ground truth: simulate all 32 vectors, compare to truth table.
# ---------------------------------------------------------------------

sim_grants = {}
sim_failed_vectors = []
for (req_level_str, owner_id_str) in ALL_VECTORS:
    grant_val, inst_outputs = simulate_netlist(req_level_str, owner_id_str, netlist_instances)
    if grant_val is None:
        sim_failed_vectors.append((req_level_str, owner_id_str))
    sim_grants[(req_level_str, owner_id_str)] = grant_val

if sim_failed_vectors:
    fail_setup(
        "Python gate-level simulator could not resolve 'grant' for vector(s) %s "
        "in %s; netlist parsing/simulation is required for grading."
        % (sim_failed_vectors[:3], NETLIST_PATH)
    )

# Ground-truth diverging vectors: (req_level, owner_id, expected_grant, observed_grant)
ground_truth_diverging = set()
for (req_level_str, owner_id_str) in ALL_VECTORS:
    expected = truth_table.get((req_level_str, owner_id_str))
    if expected is None:
        continue
    observed = sim_grants[(req_level_str, owner_id_str)]
    if observed != expected:
        ground_truth_diverging.add((req_level_str, owner_id_str, expected, observed))

trojan_actually_exists = len(ground_truth_diverging) > 0


# ---------------------------------------------------------------------
# Optional iverilog/vvp cross-check (informational only, not a graded
# requirement id); corroborates the Python simulator.
# ---------------------------------------------------------------------

def try_iverilog_cross_check():
    from shutil import which

    if which("iverilog") is None or which("vvp") is None:
        return  # silently skip
    if not os.path.isfile(TB_PATH):
        return  # silently skip if harness testbench not shipped
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            sim_path = os.path.join(tmpdir, "sim.vvp")
            compile_cmd = [
                "iverilog",
                "-g2012",
                "-o",
                sim_path,
                NETLIST_PATH,
                TB_PATH,
            ]
            proc = subprocess.run(
                compile_cmd, capture_output=True, timeout=30, text=True
            )
            if proc.returncode != 0:
                sys.stderr.write(
                    "[INFO] iverilog cross-check compile failed (non-fatal): %s\n"
                    % proc.stderr[:500]
                )
                return
            run_proc = subprocess.run(
                ["vvp", sim_path], capture_output=True, timeout=30, text=True
            )
            vec_re = re.compile(
                r'VEC\s+req_level=([01]{2})\s+owner_id=([01]{3})\s+grant=([01])'
            )
            iverilog_grants = {}
            for line in run_proc.stdout.splitlines():
                m = vec_re.search(line)
                if m:
                    iverilog_grants[(m.group(1), m.group(2))] = int(m.group(3))
            mismatches = []
            for key, py_val in sim_grants.items():
                iv_val = iverilog_grants.get(key)
                if iv_val is not None and iv_val != py_val:
                    mismatches.append((key, py_val, iv_val))
            if mismatches:
                sys.stderr.write(
                    "[WARN] iverilog cross-check disagrees with Python simulator "
                    "for %d vector(s); using Python simulator as authoritative: %s\n"
                    % (len(mismatches), mismatches[:3])
                )
            else:
                sys.stderr.write(
                    "[INFO] iverilog cross-check corroborates Python simulator "
                    "for all %d resolved vectors.\n" % len(iverilog_grants)
                )
    except Exception as e:
        sys.stderr.write("[INFO] iverilog cross-check skipped due to error: %s\n" % e)


try_iverilog_cross_check()


# ---------------------------------------------------------------------
# Compute ground-truth suspect instance set via single-instance
# output-flip sensitivity analysis, for each diverging vector.
# ---------------------------------------------------------------------

def compute_flip_sensitive_instances(req_level_str, owner_id_str, expected_grant):
    """For a given diverging vector, find the set of instance names whose
    single-output-flip (relative to the netlist's own simulated value)
    causes grant to match the reference expected_grant. This identifies
    which instance(s) are causally responsible for the divergence."""
    sensitive = set()
    baseline_grant, baseline_outputs = simulate_netlist(
        req_level_str, owner_id_str, netlist_instances
    )
    if baseline_grant == expected_grant:
        return sensitive  # not actually diverging at this vector

    for inst_name, orig_val in baseline_outputs.items():
        flipped_val = 1 - orig_val
        forced = {inst_name: flipped_val}
        flipped_grant, _ = simulate_netlist(
            req_level_str, owner_id_str, netlist_instances, forced_output=forced
        )
        if flipped_grant == expected_grant:
            sensitive.add(inst_name)
    return sensitive


ground_truth_suspects = set()
for (req_level_str, owner_id_str, expected, observed) in ground_truth_diverging:
    sensitive = compute_flip_sensitive_instances(req_level_str, owner_id_str, expected)
    ground_truth_suspects |= sensitive


# ---------------------------------------------------------------------
# FR1: schema/type checks
# ---------------------------------------------------------------------

def check_fr1(sub):
    if not isinstance(sub, dict):
        return False, "top-level JSON is not an object/dict"

    required_keys = [
        "trojan_detected",
        "suspect_instances",
        "diverging_vectors",
        "explanation",
    ]
    missing = [k for k in required_keys if k not in sub]
    if missing:
        return False, "missing required key(s): %s" % missing

    if not isinstance(sub["trojan_detected"], bool):
        return False, "trojan_detected must be a JSON boolean"

    if not isinstance(sub["suspect_instances"], list):
        return False, "suspect_instances must be a JSON array"
    for i, item in enumerate(sub["suspect_instances"]):
        if not isinstance(item, str):
            return False, "suspect_instances[%d] is not a string" % i

    if not isinstance(sub["diverging_vectors"], list):
        return False, "diverging_vectors must be a JSON array"
    for i, item in enumerate(sub["diverging_vectors"]):
        if not isinstance(item, dict):
            return False, "diverging_vectors[%d] is not an object" % i
        for key in ["req_level", "owner_id", "expected_grant", "observed_grant"]:
            if key not in item:
                return False, "diverging_vectors[%d] missing key '%s'" % (i, key)

    if not isinstance(sub["explanation"], str):
        return False, "explanation must be a string"

    return True, ""


fr1_ok, fr1_reason = check_fr1(submission)
record("FR1", fr1_ok, fr1_reason)


# ---------------------------------------------------------------------
# FR2: field-format checks on diverging_vectors entries
# ---------------------------------------------------------------------

def check_fr2(sub):
    if not isinstance(sub, dict) or not isinstance(sub.get("diverging_vectors"), list):
        return False, "diverging_vectors missing or not a list (see FR1)"

    for i, item in enumerate(sub["diverging_vectors"]):
        if not isinstance(item, dict):
            return False, "diverging_vectors[%d] is not an object" % i

        req_level = item.get("req_level")
        owner_id = item.get("owner_id")
        expected_grant = item.get("expected_grant")
        observed_grant = item.get("observed_grant")

        if not isinstance(req_level, str) or len(req_level) != 2 or any(
            c not in "01" for c in req_level
        ):
            return False, (
                "diverging_vectors[%d].req_level must be a 2-char binary string, got %r"
                % (i, req_level)
            )

        if not isinstance(owner_id, str) or len(owner_id) != 3 or any(
            c not in "01" for c in owner_id
        ):
            return False, (
                "diverging_vectors[%d].owner_id must be a 3-char binary string, got %r"
                % (i, owner_id)
            )

        if type(expected_grant) is not int or expected_grant not in (0, 1):
            return False, (
                "diverging_vectors[%d].expected_grant must be int 0 or 1, got %r"
                % (i, expected_grant)
            )

        if type(observed_grant) is not int or observed_grant not in (0, 1):
            return False, (
                "diverging_vectors[%d].observed_grant must be int 0 or 1, got %r"
                % (i, observed_grant)
            )

    return True, ""


fr2_ok, fr2_reason = check_fr2(submission)
record("FR2", fr2_ok, fr2_reason)


# ---------------------------------------------------------------------
# FR3: suspect_instances must reference real instance names in netlist
# ---------------------------------------------------------------------

def check_fr3(sub):
    if not isinstance(sub, dict) or not isinstance(sub.get("suspect_instances"), list):
        return False, "suspect_instances missing or not a list (see FR1)"

    unknown = []
    for item in sub["suspect_instances"]:
        if not isinstance(item, str):
            continue  # already caught by FR1
        if item not in all_instance_names:
            unknown.append(item)

    if unknown:
        return False, (
            "suspect_instances contains name(s) not present as instance "
            "identifiers in %s: %s" % (NETLIST_PATH, unknown)
        )
    return True, ""


fr3_ok, fr3_reason = check_fr3(submission)
record("FR3", fr3_ok, fr3_reason)


# ---------------------------------------------------------------------
# FR4: trojan_detected vs diverging_vectors emptiness consistency
# ---------------------------------------------------------------------

def check_fr4(sub):
    if not isinstance(sub, dict):
        return False, "top-level JSON is not an object/dict"
    if "trojan_detected" not in sub or "diverging_vectors" not in sub:
        return False, "missing trojan_detected or diverging_vectors (see FR1)"

    detected = sub["trojan_detected"]
    vectors = sub["diverging_vectors"]

    if not isinstance(vectors, list):
        return False, "diverging_vectors must be a list (see FR1)"

    if detected is False:
        if len(vectors) != 0:
            return False, (
                "trojan_detected is false but diverging_vectors is non-empty "
                "(len=%d)" % len(vectors)
            )
    elif detected is True:
        if len(vectors) < 1:
            return False, "trojan_detected is true but diverging_vectors is empty"
    else:
        return False, "trojan_detected is not a boolean (see FR1)"

    return True, ""


fr4_ok, fr4_reason = check_fr4(submission)
record("FR4", fr4_ok, fr4_reason)


# ---------------------------------------------------------------------
# SR1: trojan_detected must be true since ground truth divergence exists
# ---------------------------------------------------------------------

def check_sr1(sub):
    if not trojan_actually_exists:
        # No divergence exists in ground truth; either verdict would be
        # judged on its own merits elsewhere, but per spec this task's
        # ground truth always has a divergence. Still, handle gracefully.
        detected = sub.get("trojan_detected")
        if detected is False:
            return True, ""
        else:
            return True, ""
    detected = sub.get("trojan_detected")
    if detected is not True:
        return False, (
            "ground-truth exhaustive simulation found %d diverging vector(s) "
            "but submission.trojan_detected is %r (expected true)"
            % (len(ground_truth_diverging), detected)
        )
    return True, ""


sr1_ok, sr1_reason = check_sr1(submission)
record("SR1", sr1_ok, sr1_reason)


# ---------------------------------------------------------------------
# SR2: exact set equality of diverging_vectors against ground truth
# ---------------------------------------------------------------------

def normalize_submitted_vectors(sub):
    normed = set()
    vectors = sub.get("diverging_vectors")
    if not isinstance(vectors, list):
        return normed
    for item in vectors:
        if not isinstance(item, dict):
            continue
        req_level = item.get("req_level")
        owner_id = item.get("owner_id")
        expected_grant = item.get("expected_grant")
        observed_grant = item.get("observed_grant")
        if not (isinstance(req_level, str) and len(req_level) == 2 and all(c in "01" for c in req_level)):
            continue
        if not (isinstance(owner_id, str) and len(owner_id) == 3 and all(c in "01" for c in owner_id)):
            continue
        if type(expected_grant) is not int or expected_grant not in (0, 1):
            continue
        if type(observed_grant) is not int or observed_grant not in (0, 1):
            continue
        normed.add((req_level, owner_id, expected_grant, observed_grant))
    return normed


submitted_vectors_set = normalize_submitted_vectors(submission)


def check_sr2(submitted_set, truth_set):
    if submitted_set == truth_set:
        return True, ""
    missing = truth_set - submitted_set
    extra = submitted_set - truth_set
    reason_parts = []
    if missing:
        reason_parts.append("missing true diverging vector(s): %s" % sorted(missing))
    if extra:
        reason_parts.append("spurious/incorrect diverging vector(s): %s" % sorted(extra))
    return False, "; ".join(reason_parts) if reason_parts else "set mismatch"


sr2_ok, sr2_reason = check_sr2(submitted_vectors_set, ground_truth_diverging)
record("SR2", sr2_ok, sr2_reason)


# ---------------------------------------------------------------------
# SR3: suspect_instances must be a superset covering ground-truth
# flip-sensitive suspects.
# ---------------------------------------------------------------------

def check_sr3(sub, ground_truth_suspects):
    submitted_suspects = set()
    if isinstance(sub.get("suspect_instances"), list):
        for item in sub["suspect_instances"]:
            if isinstance(item, str):
                submitted_suspects.add(item)

    if not ground_truth_suspects:
        # No causal suspects identifiable (shouldn't normally happen when
        # trojan_actually_exists is True, but handle gracefully); require
        # at least that submission doesn't need any specific instance.
        return True, ""

    missing = ground_truth_suspects - submitted_suspects
    if missing:
        return False, (
            "suspect_instances is missing ground-truth-implicated instance(s): %s"
            % sorted(missing)
        )
    return True, ""


sr3_ok, sr3_reason = check_sr3(submission, ground_truth_suspects)
record("SR3", sr3_ok, sr3_reason)


# ---------------------------------------------------------------------
# SR4: false-positive rate must be exactly 0 across both vectors and
# suspect instances.
# ---------------------------------------------------------------------

def check_sr4(sub, submitted_vectors_set, ground_truth_diverging, ground_truth_suspects):
    submitted_suspects = set()
    if isinstance(sub.get("suspect_instances"), list):
        for item in sub["suspect_instances"]:
            if isinstance(item, str):
                submitted_suspects.add(item)

    extra_vectors = submitted_vectors_set - ground_truth_diverging
    extra_suspects = submitted_suspects - ground_truth_suspects

    total_submitted = len(submitted_vectors_set) + len(submitted_suspects)
    total_extra = len(extra_vectors) + len(extra_suspects)

    if total_submitted == 0:
        # Nothing submitted at all: cannot have zero false-positive rate
        # in a meaningful sense if a trojan truly exists and nothing
        # correct was reported (this mirrors the naive baseline case).
        if trojan_actually_exists:
            return False, (
                "no diverging_vectors or suspect_instances were submitted, "
                "so no true positives were reported despite a real divergence existing"
            )
        else:
            return True, ""

    fp_rate = total_extra / total_submitted

    if fp_rate != 0:
        return False, (
            "false_positive_rate=%.4f (extra vectors=%s, extra suspects=%s)"
            % (fp_rate, sorted(extra_vectors), sorted(extra_suspects))
        )

    # Even with fp_rate == 0, if nothing true was actually captured while
    # a trojan exists, this should already have failed SR2/SR3; SR4 itself
    # is purely about false positives among what was submitted.
    return True, ""


sr4_ok, sr4_reason = check_sr4(
    submission, submitted_vectors_set, ground_truth_diverging, ground_truth_suspects
)
record("SR4", sr4_ok, sr4_reason)


# ---------------------------------------------------------------------
# Final verdict
# ---------------------------------------------------------------------

if overall_pass:
    sys.exit(0)
else:
    sys.exit(1)