#!/usr/bin/env python3
"""
evaluate.py -- Grader for sfa_rom_addr_leak_001 (Secret-dependent ROM address-bus
leakage in a substitution-table lookup module).

Reads inputs/subst_lookup.v, inputs/address_traces.json, inputs/design_brief.md
for reference. Grades submission/vulnerability_report.json.

Emits deterministic [TEST] PASS/FAIL lines per requirement id and exits 0/1.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

INPUTS_DIR = "inputs"
SUBMISSION_PATH = os.path.join("submission", "vulnerability_report.json")

RTL_PATH = os.path.join(INPUTS_DIR, "subst_lookup.v")
TRACES_PATH = os.path.join(INPUTS_DIR, "address_traces.json")
BRIEF_PATH = os.path.join(INPUTS_DIR, "design_brief.md")

TB_EQUIV_PATH = os.path.join("evaluation", "tb_equiv.v")

IVERILOG_TIMEOUT = 30
VVP_TIMEOUT = 30

results = {}  # requirement_id -> (passed: bool, message: str)


def emit(req_id, passed, reason=""):
    if passed:
        print("[TEST] PASS: {}".format(req_id))
    else:
        print("[TEST] FAIL: {}: {}".format(req_id, reason))
    results[req_id] = (passed, reason)


def fail_all(req_ids, reason):
    for r in req_ids:
        if r not in results:
            emit(r, False, reason)


def read_file(path):
    with open(path, "r") as f:
        return f.read()


def which(tool):
    return shutil.which(tool) is not None


# ---------------------------------------------------------------------------
# Setup: load reference inputs and submission
# ---------------------------------------------------------------------------

all_req_ids = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3"]

for fname in [RTL_PATH, TRACES_PATH, BRIEF_PATH]:
    if not os.path.exists(fname):
        print("[TEST] FAIL: SETUP: {} not found".format(fname))
        sys.exit(1)

if not os.path.exists(TB_EQUIV_PATH):
    print("[TEST] FAIL: SETUP: {} not found".format(TB_EQUIV_PATH))
    sys.exit(1)

rtl_text = read_file(RTL_PATH)

try:
    traces_text = read_file(TRACES_PATH)
    traces = json.loads(traces_text)
    if not isinstance(traces, list) or len(traces) == 0:
        print("[TEST] FAIL: SETUP: {} does not contain a non-empty list".format(TRACES_PATH))
        sys.exit(1)
except Exception as e:
    print("[TEST] FAIL: SETUP: failed to parse {}: {}".format(TRACES_PATH, e))
    sys.exit(1)

if not os.path.exists(SUBMISSION_PATH):
    print("[TEST] FAIL: SETUP: {} not found".format(SUBMISSION_PATH))
    sys.exit(1)

submission_raw = None
report = None
try:
    submission_raw = read_file(SUBMISSION_PATH)
    report = json.loads(submission_raw)
except Exception as e:
    # FR1 fails outright, and everything downstream that depends on the
    # report content must also fail deterministically.
    reason = "submission is not valid JSON: {}".format(e)
    emit("FR1", False, reason)
    fail_all(all_req_ids, "cannot evaluate: " + reason)
    sys.exit(1)

if not isinstance(report, dict):
    reason = "submission JSON root is not an object"
    emit("FR1", False, reason)
    fail_all(all_req_ids, "cannot evaluate: " + reason)
    sys.exit(1)

# ---------------------------------------------------------------------------
# FR1: required fields present with correct types
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {
    "leaking_signals": list,
    "non_leaking_signals": list,
    "recovered_secret_key": int,
    "leakage_relationship": str,
    "mitigation_patch": str,
    "mitigation_rationale": str,
}

fr1_errors = []
for field, expected_type in REQUIRED_FIELDS.items():
    if field not in report:
        fr1_errors.append("missing field '{}'".format(field))
        continue
    value = report[field]
    if expected_type is int:
        # bool is a subclass of int in Python; explicitly reject bools.
        if isinstance(value, bool) or not isinstance(value, int):
            fr1_errors.append("field '{}' is not an int".format(field))
    elif expected_type is list:
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            fr1_errors.append("field '{}' is not a list of strings".format(field))
    elif expected_type is str:
        if not isinstance(value, str):
            fr1_errors.append("field '{}' is not a string".format(field))

if fr1_errors:
    emit("FR1", False, "; ".join(fr1_errors))
else:
    emit("FR1", True)

fr1_ok = results["FR1"][0]

# Safe accessors (default empty/sentinel values used only when FR1 already failed,
# so downstream checks still produce deterministic FAILs referencing the missing data).
leaking_signals = report.get("leaking_signals", [])
if not isinstance(leaking_signals, list):
    leaking_signals = []
non_leaking_signals = report.get("non_leaking_signals", [])
if not isinstance(non_leaking_signals, list):
    non_leaking_signals = []
recovered_secret_key = report.get("recovered_secret_key", None)
leakage_relationship = report.get("leakage_relationship", "")
if not isinstance(leakage_relationship, str):
    leakage_relationship = ""
mitigation_patch = report.get("mitigation_patch", "")
if not isinstance(mitigation_patch, str):
    mitigation_patch = ""

# ---------------------------------------------------------------------------
# FR2: recovered_secret_key consistent with ALL trace entries
# ---------------------------------------------------------------------------

def check_fr2():
    if recovered_secret_key is None or isinstance(recovered_secret_key, bool) or not isinstance(recovered_secret_key, int):
        return False, "recovered_secret_key missing or not an int"
    if recovered_secret_key < 0 or recovered_secret_key > 15:
        return False, "recovered_secret_key {} out of range [0,15]".format(recovered_secret_key)

    mismatches = []
    for idx, entry in enumerate(traces):
        try:
            pub = entry["public_index"]
            obs = entry["observed_rom_addr"]
        except Exception:
            return False, "address_traces.json entry {} missing required fields".format(idx)
        if not isinstance(pub, int) or not isinstance(obs, int):
            return False, "address_traces.json entry {} has non-integer fields".format(idx)
        predicted = pub ^ recovered_secret_key
        if predicted != obs:
            mismatches.append(idx)

    if mismatches:
        return False, "recovered_secret_key={} fails to predict observed_rom_addr for {} of {} trace entries (e.g. index {})".format(
            recovered_secret_key, len(mismatches), len(traces), mismatches[0])
    return True, ""


fr2_ok, fr2_reason = check_fr2()
emit("FR2", fr2_ok, fr2_reason)

# ---------------------------------------------------------------------------
# FR3: leaking_signals/non_leaking_signals non-empty, drawn from valid names
# structurally parsed from inputs/subst_lookup.v
# ---------------------------------------------------------------------------

def parse_valid_signal_names(rtl):
    names = set()

    # Port declarations: input/output wire/reg/logic [W:0] name
    port_pattern = re.compile(
        r'(?:input|output)\s+(?:wire\s+|reg\s+|logic\s+)?(?:\[\s*\d+\s*:\s*\d+\s*\]\s*)?(\w+)\s*[,;)]'
    )
    for m in port_pattern.finditer(rtl):
        names.add(m.group(1))

    # wire/reg declarations: wire [3:0] lookup_index;  reg [3:0] rom_addr_q;
    decl_pattern = re.compile(
        r'\b(?:wire|reg|logic)\s+(?:\[\s*\d+\s*:\s*\d+\s*\]\s*)?(\w+(?:\s*,\s*\w+)*)\s*;'
    )
    for m in decl_pattern.finditer(rtl):
        group = m.group(1)
        for nm in group.split(','):
            nm = nm.strip()
            if nm:
                names.add(nm)

    # assign statements: assign lookup_index = ...
    assign_pattern = re.compile(r'\bassign\s+(\w+)\s*=')
    for m in assign_pattern.finditer(rtl):
        names.add(m.group(1))

    # always-block registered assignments: rom_addr_q <= ...
    nonblock_pattern = re.compile(r'\b(\w+)\s*<=')
    for m in nonblock_pattern.finditer(rtl):
        names.add(m.group(1))

    # blocking assignments inside always blocks: table_data_r = ...
    block_pattern = re.compile(r'\b(\w+)\s*=[^=]')
    for m in block_pattern.finditer(rtl):
        names.add(m.group(1))

    return names


valid_signal_names = parse_valid_signal_names(rtl_text)

# The canonical interface/internal names per public_spec.interface must always
# be considered valid even if a resynthesized/renamed submission's own RTL
# differs textually -- but since we only have the ORIGINAL subst_lookup.v to
# parse against (participants do not edit inputs/), this set anchors names
# to what's actually present in the provided netlist, per the pinned interface.
CANONICAL_NAMES = {
    "rom_addr_q", "lookup_index", "table_data", "secret_key",
    "public_index", "clk", "rst_n",
}
valid_signal_names |= CANONICAL_NAMES


def check_fr3():
    if len(leaking_signals) == 0:
        return False, "leaking_signals is empty"
    if len(non_leaking_signals) == 0:
        return False, "non_leaking_signals is empty"

    bad_leaking = [s for s in leaking_signals if s not in valid_signal_names]
    if bad_leaking:
        return False, "leaking_signals contains unknown signal name(s): {}".format(bad_leaking)

    bad_nonleaking = [s for s in non_leaking_signals if s not in valid_signal_names]
    if bad_nonleaking:
        return False, "non_leaking_signals contains unknown signal name(s): {}".format(bad_nonleaking)

    return True, ""


fr3_ok, fr3_reason = check_fr3()
emit("FR3", fr3_ok, fr3_reason)

# ---------------------------------------------------------------------------
# SR1: rom_addr_q AND lookup_index leaking; table_data exclusively non-leaking
# ---------------------------------------------------------------------------

def check_sr1():
    if "rom_addr_q" not in leaking_signals:
        return False, "'rom_addr_q' missing from leaking_signals"
    if "lookup_index" not in leaking_signals:
        return False, "'lookup_index' missing from leaking_signals"
    if "table_data" in leaking_signals:
        return False, "'table_data' incorrectly listed in leaking_signals"
    if "table_data" not in non_leaking_signals:
        return False, "'table_data' missing from non_leaking_signals"
    return True, ""


sr1_ok, sr1_reason = check_sr1()
emit("SR1", sr1_ok, sr1_reason)

# ---------------------------------------------------------------------------
# SR2: leakage_relationship expresses XOR relation; recovered_secret_key
# already verified under FR2 (zero tolerance)
# ---------------------------------------------------------------------------

def normalize(text):
    t = text.lower()
    t = t.replace("xor", "^")
    t = re.sub(r'\s+', ' ', t)
    return t


def check_sr2():
    if not fr2_ok:
        return False, "recovered_secret_key not verified against all trace entries (FR2 failed): {}".format(fr2_reason)

    norm = normalize(leakage_relationship)

    has_pub = ("public_index" in norm) or ("pub" in norm)
    has_key = ("secret_key" in norm) or ("key" in norm)
    has_addr = ("rom_addr_q" in norm) or ("observed_rom_addr" in norm) or ("rom_addr" in norm) or ("address" in norm) or ("addr" in norm)
    has_xor = "^" in norm

    if not has_xor:
        return False, "leakage_relationship does not express an XOR relationship: '{}'".format(leakage_relationship)
    if not has_pub:
        return False, "leakage_relationship does not reference public_index: '{}'".format(leakage_relationship)
    if not has_key:
        return False, "leakage_relationship does not reference secret_key: '{}'".format(leakage_relationship)
    if not has_addr:
        return False, "leakage_relationship does not reference the address/rom_addr signal: '{}'".format(leakage_relationship)

    return True, ""


sr2_ok, sr2_reason = check_sr2()
emit("SR2", sr2_ok, sr2_reason)

# ---------------------------------------------------------------------------
# SR3: static fail-on-presence scan of mitigation_patch for secret-dependent
# addressing (XOR of public_index/secret_key used to index memory)
# ---------------------------------------------------------------------------

def strip_comments(v):
    v = re.sub(r'//.*', '', v)
    v = re.sub(r'/\*.*?\*/', '', v, flags=re.DOTALL)
    return v


def check_sr3():
    patch = strip_comments(mitigation_patch)
    norm = re.sub(r'\s+', '', patch)

    # Vulnerability in baseline:
    #   "wire [3:0] lookup_index; ... assign lookup_index = public_index ^ secret_key;"
    #   then "rom_addr_q <= lookup_index;" and "case (rom_addr_q) ... endcase"
    # i.e. a signal defined as XOR(public_index, secret_key) [directly or via an
    # intermediate registered signal] that is subsequently used as an array/case
    # index. We flag any of the following constructs:

    # 1) Direct indexing with an inline XOR expression:
    #    mem[public_index^secret_key], case(public_index^secret_key), rom[...]
    direct_index_pattern = re.compile(
        r'(?:\[|case\s*\(\s*)\s*\(?\s*(?:public_index\s*\^\s*secret_key|secret_key\s*\^\s*public_index)\s*\)?\s*[\]\)]'
    )
    if direct_index_pattern.search(norm):
        return False, "mitigation_patch indexes memory directly with (public_index ^ secret_key)"

    # 2) An intermediate wire/reg assigned the XOR, later used as an index/case selector.
    #    e.g. assign lookup_index = public_index ^ secret_key; ... case(lookup_index)
    #    or  rom_addr_q <= lookup_index; case(rom_addr_q)
    assign_xor_pattern = re.compile(
        r'(\w+)\s*(?:<=|=)\s*\(?\s*(?:public_index\s*\^\s*secret_key|secret_key\s*\^\s*public_index)\s*\)?\s*;'
    )
    xor_targets = set(m.group(1) for m in assign_xor_pattern.finditer(norm))

    if xor_targets:
        # follow one level of indirection: target <= other_target; then other_target used as index
        indirect_pattern = re.compile(r'(\w+)\s*<=\s*(\w+)\s*;')
        propagated = set(xor_targets)
        changed = True
        # limited fixed number of propagation passes (bounded, deterministic)
        for _ in range(5):
            if not changed:
                break
            changed = False
            for m in indirect_pattern.finditer(norm):
                dst, src = m.group(1), m.group(2)
                if src in propagated and dst not in propagated:
                    propagated.add(dst)
                    changed = True

        for name in propagated:
            index_pattern = re.compile(
                r'(?:\[\s*' + re.escape(name) + r'\s*\]|case\s*\(\s*' + re.escape(name) + r'\s*\))'
            )
            if index_pattern.search(norm):
                return False, "mitigation_patch uses signal '{}' (derived from public_index^secret_key) as a memory/case index".format(name)

    return True, ""


sr3_ok, sr3_reason = check_sr3()
emit("SR3", sr3_ok, sr3_reason)

# ---------------------------------------------------------------------------
# FR4: mitigation_patch compiles and is functionally equivalent to the
# original module across all 256 (public_index, secret_key) combinations
# ---------------------------------------------------------------------------

def extract_patched_module_name(patch_text):
    """Find the module name declared in mitigation_patch. Prefer a module
    literally named subst_lookup_patched; otherwise fall back to the first
    'module <name>' declaration found (excluding subst_lookup itself, to
    avoid colliding with the original during co-simulation)."""
    names = re.findall(r'\bmodule\s+(\w+)', patch_text)
    if not names:
        return None
    for n in names:
        if n == "subst_lookup_patched":
            return n
    for n in names:
        if n != "subst_lookup":
            return n
    return names[0]


def check_fr4():
    if not which("iverilog") or not which("vvp"):
        return False, "iverilog/vvp toolchain not available; cannot verify syntactic validity and functional equivalence"

    if not mitigation_patch.strip():
        return False, "mitigation_patch is empty"

    patched_name = extract_patched_module_name(mitigation_patch)
    if patched_name is None:
        return False, "mitigation_patch does not contain a 'module ... endmodule' declaration"

    # If the patch declares its module under the SAME name as the original
    # (subst_lookup), we cannot co-simulate both original and patched in one
    # compilation unit without a name clash. Rename the patched module's
    # declaration and its endmodule-adjacent references minimally via a
    # textual macro-free approach: wrap the patch text, renaming only the
    # `module <name>` and any internal self-reference isn't needed since
    # Verilog modules don't self-reference by name internally.
    patch_text = mitigation_patch
    final_patched_name = patched_name
    if patched_name == "subst_lookup":
        final_patched_name = "subst_lookup_patched_renamed"
        patch_text = re.sub(
            r'\bmodule\s+subst_lookup\b',
            'module ' + final_patched_name,
            patch_text,
            count=1,
        )

    tmpdir = tempfile.mkdtemp(prefix="sfa_eval_")
    try:
        orig_path = os.path.join(tmpdir, "subst_lookup.v")
        patch_path = os.path.join(tmpdir, "mitigation_patch.v")
        tb_path = os.path.join(tmpdir, "tb_equiv.v")
        sim_out = os.path.join(tmpdir, "sim.vvp")

        shutil.copyfile(RTL_PATH, orig_path)
        with open(patch_path, "w") as f:
            f.write(patch_text)

        tb_template = read_file(TB_EQUIV_PATH)
        tb_rendered = tb_template.replace("PATCHED_MODULE_NAME", final_patched_name)
        with open(tb_path, "w") as f:
            f.write(tb_rendered)

        # Step 1: syntax-only check of the patch in isolation (-t null)
        syntax_cmd = ["iverilog", "-g2005", "-t", "null", patch_path]
        try:
            proc = subprocess.run(
                syntax_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=IVERILOG_TIMEOUT
            )
        except subprocess.TimeoutExpired:
            return False, "mitigation_patch syntax check (iverilog -t null) timed out"
        if proc.returncode != 0:
            stderr_txt = proc.stderr.decode("utf-8", errors="replace")
            return False, "mitigation_patch failed to compile: {}".format(stderr_txt[:800])

        # Step 2: co-compile original + patch + testbench, elaborate & run
        compile_cmd = ["iverilog", "-g2005", "-o", sim_out, orig_path, patch_path, tb_path]
        try:
            proc = subprocess.run(
                compile_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=IVERILOG_TIMEOUT
            )
        except subprocess.TimeoutExpired:
            return False, "co-compilation of testbench with mitigation_patch timed out"
        if proc.returncode != 0:
            stderr_txt = proc.stderr.decode("utf-8", errors="replace")
            return False, "testbench co-compilation failed: {}".format(stderr_txt[:800])

        try:
            proc = subprocess.run(
                ["vvp", sim_out], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=VVP_TIMEOUT
            )
        except subprocess.TimeoutExpired:
            return False, "simulation run (vvp) timed out"
        if proc.returncode != 0:
            stderr_txt = proc.stderr.decode("utf-8", errors="replace")
            return False, "simulation run (vvp) crashed: {}".format(stderr_txt[:800])

        stdout_txt = proc.stdout.decode("utf-8", errors="replace")

        if "TB_DONE" not in stdout_txt:
            return False, "simulation did not complete (TB_DONE marker not found); output: {}".format(stdout_txt[-800:])

        combo_lines = re.findall(
            r'COMBO\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', stdout_txt
        )
        if len(combo_lines) < 256:
            return False, "simulation reported only {} of 256 required (public_index,secret_key) combinations".format(len(combo_lines))

        mismatches = []
        seen = set()
        for pub_s, key_s, orig_s, patched_s in combo_lines:
            pub, key, orig_v, patched_v = int(pub_s), int(key_s), int(orig_s), int(patched_s)
            seen.add((pub, key))
            if orig_v != patched_v:
                mismatches.append((pub, key, orig_v, patched_v))

        if len(seen) < 256:
            return False, "simulation did not cover all 256 distinct (public_index,secret_key) combinations (covered {})".format(len(seen))

        if mismatches:
            ex = mismatches[0]
            return False, "mitigation_patch table_data diverges from original for {} of 256 combinations (e.g. public_index={}, secret_key={}: orig={} patched={})".format(
                len(mismatches), ex[0], ex[1], ex[2], ex[3])

        return True, ""
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


fr4_ok, fr4_reason = check_fr4()
emit("FR4", fr4_ok, fr4_reason)

# ---------------------------------------------------------------------------
# Final verdict
# ---------------------------------------------------------------------------

all_passed = all(results[r][0] for r in all_req_ids)
sys.exit(0 if all_passed else 1)