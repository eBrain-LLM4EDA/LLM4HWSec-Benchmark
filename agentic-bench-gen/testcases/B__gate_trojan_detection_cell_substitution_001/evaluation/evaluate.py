#!/usr/bin/env python3
"""
evaluate.py -- Grader for gate_trojan_detection_cell_substitution_001

Grades submission/trojan_report.json against inputs/netlist.v ground truth.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------

INPUTS_DIR = "inputs"
NETLIST_PATH = os.path.join(INPUTS_DIR, "netlist.v")
PRIMITIVE_CELLS_PATH = os.path.join(INPUTS_DIR, "primitive_cells.v")
DESIGN_BRIEF_PATH = os.path.join(INPUTS_DIR, "design_brief.md")

SUBMISSION_PATH = os.path.join("submission", "trojan_report.json")

TB_PATH = os.path.join("evaluation", "tb_perm_check.v")

VALID_CELL_TYPES = {
    "BUF1", "INV1", "AND2", "OR2", "XOR2", "XNOR2", "NAND2", "NOR2"
}

# Ground truth constants (private to this harness; not disclosed to
# participants via any public-facing document).
GT_INSTANCE = "u_eq2"
GT_FOUND = "XOR2"
GT_EXPECTED = "XNOR2"

results = []  # list of (req_id, passed_bool, message)


def record(req_id, passed, message=""):
    if passed:
        print("[TEST] PASS: {}".format(req_id))
    else:
        print("[TEST] FAIL: {}: {}".format(req_id, message))
    results.append((req_id, passed, message))


ALL_REQ_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4", "SR5"]


def load_text_file(path):
    if not os.path.isfile(path):
        return None
    with open(path, "r") as f:
        return f.read()


netlist_text = load_text_file(NETLIST_PATH)
if netlist_text is None:
    print("[TEST] FAIL: SETUP: {} not found".format(NETLIST_PATH))
    sys.exit(1)

primitive_cells_text = load_text_file(PRIMITIVE_CELLS_PATH)
if primitive_cells_text is None:
    print("[TEST] FAIL: SETUP: {} not found".format(PRIMITIVE_CELLS_PATH))
    sys.exit(1)

# ----------------------------------------------------------------------
# Submission loading -- only checks existence of the file here. The
# actual JSON parse is deferred to check_fr1() so that malformed JSON
# is attributed specifically to FR1 rather than short-circuiting every
# requirement with a generic SETUP failure. A missing file, however,
# is a genuine infrastructure problem (no answer submitted at all) and
# legitimately fails every requirement with SETUP.
# ----------------------------------------------------------------------

submission_raw = None

if not os.path.isfile(SUBMISSION_PATH):
    for rid in ALL_REQ_IDS:
        print("[TEST] FAIL: SETUP: {} not found".format(SUBMISSION_PATH))
        results.append((rid, False, "{} not found".format(SUBMISSION_PATH)))
    sys.exit(1)

try:
    with open(SUBMISSION_PATH, "r") as f:
        submission_raw = f.read()
except Exception as e:
    for rid in ALL_REQ_IDS:
        print("[TEST] FAIL: SETUP: could not read {}: {}".format(SUBMISSION_PATH, e))
        results.append((rid, False, "could not read {}: {}".format(SUBMISSION_PATH, e)))
    sys.exit(1)

# Shared parsed-report state: populated by check_fr1(). If parsing
# fails, parsed_report stays None and every subsequent check must
# treat that as an unambiguous FAIL (never crash / never silently
# treat it as some other requirement's failure reason only).
parsed_report = None
parse_error_message = None


def get_report():
    """Return the parsed report dict, or {} if parsing failed."""
    if isinstance(parsed_report, dict):
        return parsed_report
    return {}


# ----------------------------------------------------------------------
# Parse netlist.v for instance names and cell types
# ----------------------------------------------------------------------

# Matches lines like:  XOR2  u_eq2 (.A(id_in[2]), .B(id_auth[2]), .Y(eq[2]));
# or with #(...) parameter blocks omitted (none expected here), tolerant
# of whitespace/newlines between cell type, instance name, and port list.
INSTANCE_RE = re.compile(
    r'\b(' + '|'.join(sorted(VALID_CELL_TYPES, key=len, reverse=True)) + r')'
    r'\s+(\w+)\s*\(',
    re.MULTILINE
)

instance_cell_type = {}  # instance_name -> cell_type
for m in INSTANCE_RE.finditer(netlist_text):
    cell_type, inst_name = m.group(1), m.group(2)
    instance_cell_type[inst_name] = cell_type

valid_instance_names = set(instance_cell_type.keys())

# Sanity: ground truth instance must actually exist in the parsed netlist
# (guards against a broken parse regex silently making SR2/SR3 vacuous).
gt_instance_exists = GT_INSTANCE in valid_instance_names
gt_actual_found_type = instance_cell_type.get(GT_INSTANCE)


# ----------------------------------------------------------------------
# Golden reference model
# ----------------------------------------------------------------------

def bits4(v):
    """Return list of 4 bits [b0,b1,b2,b3] (LSB first) for int v in 0..15."""
    return [(v >> i) & 1 for i in range(4)]


def grant_ref(id_in, id_auth):
    a = bits4(id_in)
    b = bits4(id_auth)
    eq = [1 if a[i] == b[i] else 0 for i in range(4)]
    return eq[0] & eq[1] & eq[2] & eq[3]


# ----------------------------------------------------------------------
# Dynamic simulation via iverilog/vvp (used for SR4)
# ----------------------------------------------------------------------

def run_simulation():
    """
    Compiles and runs the fixed testbench against inputs/primitive_cells.v
    and inputs/netlist.v, sweeping all 256 (id_in, id_auth) combinations.
    Returns dict: (id_in_int, id_auth_int) -> grant_int
    or raises RuntimeError with a message on compile/run failure.
    """
    if not os.path.isfile(TB_PATH):
        raise RuntimeError("SETUP:{} not found".format(TB_PATH))

    with tempfile.TemporaryDirectory() as tmpdir:
        sim_bin = os.path.join(tmpdir, "sim.vvp")
        compile_cmd = [
            "iverilog", "-g2012", "-o", sim_bin,
            PRIMITIVE_CELLS_PATH, NETLIST_PATH, TB_PATH
        ]
        try:
            cp = subprocess.run(
                compile_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=30
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("compile timed out")
        except FileNotFoundError:
            raise RuntimeError("SETUP:iverilog not found on PATH")

        if cp.returncode != 0:
            stderr_snip = cp.stderr.decode(errors="replace")[-800:]
            raise RuntimeError("compile failed: {}".format(stderr_snip))

        try:
            rp = subprocess.run(
                ["vvp", sim_bin], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=30
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("run timed out")
        except FileNotFoundError:
            raise RuntimeError("SETUP:vvp not found on PATH")

        if rp.returncode != 0:
            stderr_snip = rp.stderr.decode(errors="replace")[-800:]
            raise RuntimeError("run crashed: {}".format(stderr_snip))

        stdout_text = rp.stdout.decode(errors="replace")

    sim_results = {}
    line_re = re.compile(r'RESULT\s+([01]{4})\s+([01]{4})\s+([01])')
    for line in stdout_text.splitlines():
        m = line_re.search(line)
        if m:
            id_in_bin, id_auth_bin, grant_bin = m.groups()
            id_in_int = int(id_in_bin, 2)
            id_auth_int = int(id_auth_bin, 2)
            grant_int = int(grant_bin, 2)
            sim_results[(id_in_int, id_auth_int)] = grant_int

    if not sim_results:
        raise RuntimeError(
            "no RESULT lines parsed from simulation output "
            "(stdout snippet: {})".format(stdout_text[-500:])
        )

    return sim_results


sim_error = None
sim_results = None
sim_setup_error = None
try:
    sim_results = run_simulation()
except RuntimeError as e:
    msg = str(e)
    if msg.startswith("SETUP:"):
        sim_setup_error = msg[len("SETUP:"):]
    else:
        sim_error = msg
except Exception as e:
    sim_error = "unexpected exception during simulation setup: {}".format(e)


# ----------------------------------------------------------------------
# FR1: valid JSON, required top-level keys with correct types
# ----------------------------------------------------------------------

def check_fr1():
    global parsed_report, parse_error_message
    req_id = "FR1"

    # Local, FR1-scoped JSON parse. Any parse failure (including an
    # unterminated string literal, trailing garbage, etc.) is caught
    # here explicitly and reported as an FR1 failure -- it must never
    # propagate as an uncaught exception nor be silently attributed to
    # a different requirement.
    try:
        loaded = json.loads(submission_raw)
    except Exception as e:
        parsed_report = None
        parse_error_message = "invalid JSON: {}".format(e)
        record(req_id, False, parse_error_message)
        return False

    if not isinstance(loaded, dict):
        parsed_report = None
        parse_error_message = "submission is not a JSON object"
        record(req_id, False, parse_error_message)
        return False

    parsed_report = loaded

    verdict = parsed_report.get("verdict")
    suspect_instances = parsed_report.get("suspect_instances")
    justification = parsed_report.get("justification")

    if not isinstance(verdict, str) or verdict not in ("trojan_free", "trojan_detected"):
        record(req_id, False,
               "'verdict' missing or not one of trojan_free/trojan_detected")
        return False

    if not isinstance(suspect_instances, list) or \
            not all(isinstance(x, str) for x in suspect_instances):
        record(req_id, False, "'suspect_instances' missing or not an array of strings")
        return False

    if not isinstance(justification, str) or len(justification.strip()) == 0:
        record(req_id, False, "'justification' missing or empty")
        return False

    record(req_id, True)
    return True


fr1_ok = check_fr1()


# ----------------------------------------------------------------------
# FR2: mismatching_inputs required and well-formed when trojan_detected
# ----------------------------------------------------------------------

def check_fr2():
    req_id = "FR2"

    if parsed_report is None:
        record(req_id, False,
               "cannot evaluate: submission JSON failed to parse ({})".format(
                   parse_error_message or "unknown parse error"))
        return False

    report = get_report()
    verdict = report.get("verdict")
    if verdict != "trojan_detected":
        record(req_id, True)
        return True

    mismatching_inputs = report.get("mismatching_inputs")
    if not isinstance(mismatching_inputs, list) or len(mismatching_inputs) == 0:
        record(req_id, False,
               "'mismatching_inputs' missing/empty despite verdict=trojan_detected")
        return False

    bin4_re = re.compile(r'^[01]{4}$')
    for entry in mismatching_inputs:
        if not isinstance(entry, str) or not bin4_re.match(entry):
            record(req_id, False,
                   "mismatching_inputs entry '{}' is not a 4-char binary string".format(entry))
            return False

    record(req_id, True)
    return True


fr2_ok = check_fr2()


# ----------------------------------------------------------------------
# FR3: suspect_instances reference real netlist instances
# ----------------------------------------------------------------------

def check_fr3():
    req_id = "FR3"

    if parsed_report is None:
        record(req_id, False,
               "cannot evaluate: submission JSON failed to parse ({})".format(
                   parse_error_message or "unknown parse error"))
        return False

    report = get_report()
    suspect_instances = report.get("suspect_instances")
    if not isinstance(suspect_instances, list):
        record(req_id, False, "'suspect_instances' missing or not a list")
        return False

    if len(suspect_instances) == 0:
        record(req_id, True)
        return True

    for name in suspect_instances:
        if not isinstance(name, str) or name not in valid_instance_names:
            record(req_id, False,
                   "suspect instance '{}' does not exist in {}".format(name, NETLIST_PATH))
            return False

    record(req_id, True)
    return True


fr3_ok = check_fr3()


# ----------------------------------------------------------------------
# FR4: cell_type_analysis structure
# ----------------------------------------------------------------------

def check_fr4():
    req_id = "FR4"

    if parsed_report is None:
        record(req_id, False,
               "cannot evaluate: submission JSON failed to parse ({})".format(
                   parse_error_message or "unknown parse error"))
        return False

    report = get_report()
    verdict = report.get("verdict")
    suspect_instances = report.get("suspect_instances")

    if verdict != "trojan_detected":
        record(req_id, True)
        return True

    if not isinstance(suspect_instances, list) or len(suspect_instances) == 0:
        record(req_id, True)
        return True

    cell_type_analysis = report.get("cell_type_analysis")
    if not isinstance(cell_type_analysis, dict):
        record(req_id, False, "'cell_type_analysis' missing or not an object")
        return False

    for name in suspect_instances:
        entry = cell_type_analysis.get(name)
        if not isinstance(entry, dict):
            record(req_id, False,
                   "cell_type_analysis missing entry for suspect instance '{}'".format(name))
            return False
        found = entry.get("found")
        expected = entry.get("expected")
        if not isinstance(found, str) or found not in VALID_CELL_TYPES:
            record(req_id, False,
                   "cell_type_analysis['{}'].found is missing/invalid ('{}')".format(name, found))
            return False
        if not isinstance(expected, str) or expected not in VALID_CELL_TYPES:
            record(req_id, False,
                   "cell_type_analysis['{}'].expected is missing/invalid ('{}')".format(name, expected))
            return False

    record(req_id, True)
    return True


fr4_ok = check_fr4()


# ----------------------------------------------------------------------
# SR1: verdict must be trojan_detected
# ----------------------------------------------------------------------

def check_sr1():
    req_id = "SR1"

    if parsed_report is None:
        record(req_id, False,
               "cannot evaluate: submission JSON failed to parse ({})".format(
                   parse_error_message or "unknown parse error"))
        return False

    report = get_report()
    verdict = report.get("verdict")
    if verdict == "trojan_detected":
        record(req_id, True)
        return True
    record(req_id, False, "verdict does not report trojan_detected (got '{}')".format(verdict))
    return False


sr1_ok = check_sr1()


# ----------------------------------------------------------------------
# SR2: suspect_instances must contain the ground-truth instance
# ----------------------------------------------------------------------

def check_sr2():
    req_id = "SR2"

    if parsed_report is None:
        record(req_id, False,
               "cannot evaluate: submission JSON failed to parse ({})".format(
                   parse_error_message or "unknown parse error"))
        return False

    if not gt_instance_exists:
        record(req_id, False,
               "harness internal error: ground-truth instance '{}' not found via parser".format(GT_INSTANCE))
        return False

    report = get_report()
    suspect_instances = report.get("suspect_instances")
    if not isinstance(suspect_instances, list) or len(suspect_instances) == 0:
        record(req_id, False, "'suspect_instances' is empty; ground-truth instance not reported")
        return False

    # All listed names must exist in the netlist (reuse FR3 semantics) and
    # at least one of them must be the ground-truth instance.
    for name in suspect_instances:
        if not isinstance(name, str) or name not in valid_instance_names:
            record(req_id, False,
                   "suspect_instances contains nonexistent name '{}'".format(name))
            return False

    if GT_INSTANCE not in suspect_instances:
        record(req_id, False,
               "ground-truth instance '{}' not present in suspect_instances {}".format(
                   GT_INSTANCE, suspect_instances))
        return False

    record(req_id, True)
    return True


sr2_ok = check_sr2()


# ----------------------------------------------------------------------
# SR3: cell_type_analysis for the ground-truth instance must be correct
# ----------------------------------------------------------------------

def check_sr3():
    req_id = "SR3"

    if parsed_report is None:
        record(req_id, False,
               "cannot evaluate: submission JSON failed to parse ({})".format(
                   parse_error_message or "unknown parse error"))
        return False

    if not gt_instance_exists:
        record(req_id, False,
               "harness internal error: ground-truth instance '{}' not found via parser".format(GT_INSTANCE))
        return False

    report = get_report()
    cell_type_analysis = report.get("cell_type_analysis")
    if not isinstance(cell_type_analysis, dict):
        record(req_id, False, "'cell_type_analysis' missing or not an object")
        return False

    entry = cell_type_analysis.get(GT_INSTANCE)
    if not isinstance(entry, dict):
        record(req_id, False,
               "cell_type_analysis missing entry for ground-truth instance '{}'".format(GT_INSTANCE))
        return False

    found = entry.get("found")
    expected = entry.get("expected")

    if found != gt_actual_found_type:
        record(req_id, False,
               "cell_type_analysis['{}'].found = '{}' but actual parsed cell type in netlist.v is '{}'".format(
                   GT_INSTANCE, found, gt_actual_found_type))
        return False

    if expected != GT_EXPECTED:
        record(req_id, False,
               "cell_type_analysis['{}'].expected = '{}' but expected primitive should be '{}' "
               "(matching sibling equality cells)".format(GT_INSTANCE, expected, GT_EXPECTED))
        return False

    record(req_id, True)
    return True


sr3_ok = check_sr3()


# ----------------------------------------------------------------------
# SR4: at least one mismatching_inputs entry dynamically confirmed
# ----------------------------------------------------------------------

def check_sr4():
    req_id = "SR4"

    try:
        if parsed_report is None:
            record(req_id, False,
                   "cannot evaluate: submission JSON failed to parse ({})".format(
                       parse_error_message or "unknown parse error"))
            return False

        if sim_setup_error is not None:
            print("[TEST] FAIL: SETUP: {}".format(sim_setup_error))
            results.append((req_id, False, sim_setup_error))
            return False

        if sim_error is not None:
            record(req_id, False, "simulation of inputs/netlist.v failed: {}".format(sim_error))
            return False

        if sim_results is None or len(sim_results) == 0:
            record(req_id, False, "simulation produced no usable results")
            return False

        report = get_report()
        verdict = report.get("verdict")
        mismatching_inputs = report.get("mismatching_inputs")

        if verdict != "trojan_detected":
            record(req_id, False,
                   "verdict is not trojan_detected; no mismatching_inputs to verify")
            return False

        if not isinstance(mismatching_inputs, list) or len(mismatching_inputs) == 0:
            record(req_id, False, "'mismatching_inputs' missing/empty")
            return False

        bin4_re = re.compile(r'^[01]{4}$')
        confirmed = False
        per_entry_reasons = []

        for entry in mismatching_inputs:
            if not isinstance(entry, str) or not bin4_re.match(entry):
                per_entry_reasons.append("'{}': not a valid 4-bit binary string".format(entry))
                continue

            id_in_int = int(entry, 2)

            # Independently re-derive, across the FULL sweep of all 16
            # possible id_auth values (since id_auth is driven by the
            # testbench per the pinned public interface, not tied off
            # inside netlist.v), whether the simulated netlist's grant
            # output genuinely deviates from the golden reference model
            # for this specific id_in value at ANY id_auth. This is an
            # independent re-computation against grant_ref -- it does
            # not trust the submission's verdict, suspect_instances, or
            # cell_type_analysis in any way.
            deviation_found_for_entry = False
            checked_auths = 0
            for id_auth_int in range(16):
                key = (id_in_int, id_auth_int)
                if key not in sim_results:
                    continue
                checked_auths += 1
                sim_grant = sim_results[key]
                ref_grant = grant_ref(id_in_int, id_auth_int)
                if sim_grant != ref_grant:
                    deviation_found_for_entry = True
                    break

            if checked_auths == 0:
                per_entry_reasons.append(
                    "'{}': no simulated data available for this id_in across the id_auth sweep".format(entry))
                continue

            if deviation_found_for_entry:
                confirmed = True
                break
            else:
                per_entry_reasons.append(
                    "'{}': simulated grant matched golden reference for ALL {} sampled id_auth values "
                    "(no discrepancy found)".format(entry, checked_auths))

        if not confirmed:
            record(req_id, False,
                   "no claimed mismatching_inputs entry reproduced a real simulated deviation from the "
                   "golden reference model across the full id_auth sweep; details: {}".format(
                       "; ".join(per_entry_reasons) if per_entry_reasons else "no valid entries to check"))
            return False

        record(req_id, True)
        return True

    except Exception as e:
        record(req_id, False, "unexpected exception during SR4 dynamic verification: {}".format(e))
        return False


sr4_ok = check_sr4()


# ----------------------------------------------------------------------
# SR5: combined gate -- must have correct instance, cell-type, AND
# dynamically-confirmed mismatching input, otherwise naive/guessed
# submissions must fail.
# ----------------------------------------------------------------------

def check_sr5():
    req_id = "SR5"
    if sr1_ok and sr2_ok and sr3_ok and sr4_ok:
        record(req_id, True)
        return True
    failed_parts = []
    if not sr1_ok:
        failed_parts.append("SR1")
    if not sr2_ok:
        failed_parts.append("SR2")
    if not sr3_ok:
        failed_parts.append("SR3")
    if not sr4_ok:
        failed_parts.append("SR4")
    record(req_id, False,
           "prerequisite check(s) failed: {}".format(", ".join(failed_parts)))
    return False


sr5_ok = check_sr5()


# ----------------------------------------------------------------------
# Final aggregation
# ----------------------------------------------------------------------

any_failed = any(not passed for (_, passed, _) in results)
sys.exit(1 if any_failed else 0)