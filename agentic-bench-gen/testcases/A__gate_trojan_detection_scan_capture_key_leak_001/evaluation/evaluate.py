#!/usr/bin/env python3
"""
evaluate.py - Grader for gate_trojan_detection_scan_capture_key_leak_001

Grades submission/trojan_report.json against the input netlist artifacts
under inputs/. See evaluation/README.md for the participant-facing
schema description.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

INPUTS_DIR = "inputs"
SUBMISSION_PATH = os.path.join("submission", "trojan_report.json")

NETLIST_PATH = os.path.join(INPUTS_DIR, "key_core_netlist.v")
DESIGN_BRIEF_PATH = os.path.join(INPUTS_DIR, "design_brief.md")
SCAN_ORDER_PATH = os.path.join(INPUTS_DIR, "scan_chain_order.txt")

TB_PATH = os.path.join("evaluation", "tb_scan_leak.v")

# ---------------------------------------------------------------------
# Ground truth constants (private semantics; file itself is not
# participant-facing since it lives under evaluation/, but we avoid
# any commentary revealing CWE/threat details here).
# ---------------------------------------------------------------------
KEY_FLOPS = {"key_ff0", "key_ff1", "key_ff2", "key_ff3"}
KEY_MUXES = {"u_smux_key0", "u_smux_key1", "u_smux_key2", "u_smux_key3"}

# Generic/templated rationale text used by the shipped naive baseline;
# a submission whose rationale exactly matches this (after normalizing
# whitespace/case) is treated as non-substantive.
BASELINE_GENERIC_RATIONALE_NORMALIZED = "no trojan detected in this design"

CONDITIONALITY_TERMS = [
    "scan_en",
    "scan-en",
    "scan en",
    "scan mode",
    "scan-mode",
    "capture",
    "shift",
]

# Terms that, near a mention of scan_en, indicate the rationale is
# asserting a conditional/gated relationship (leak only occurs when
# scan_en is asserted), as opposed to merely mentioning the signal name
# in passing.
GATING_QUALIFIER_TERMS = [
    "when",
    "if ",
    "asserted",
    "assert",
    "only",
    "gated",
    "gate",
    "during",
    "while",
    "enabled",
    "high",
    "=1",
    "= 1",
    "==1",
    "== 1",
]

# Negative/always-on phrasing that reframes the leak as a constant,
# permanent, or control-signal-independent wiring defect. Presence of
# any of these phrases contradicts scan-mode conditionality and must
# fail SR4 even if conditionality keywords are also present.
NEGATIVE_ALWAYS_ON_TERMS = [
    "permanent",
    "permanently",
    "always on",
    "always-on",
    "always present",
    "always active",
    "always leak",
    "always leaks",
    "always exposed",
    "regardless of any control signal",
    "regardless of scan_en",
    "regardless of the control signal",
    "regardless of any test-mode signal",
    "stuck",
    "unrelated to any test-mode signal",
    "unrelated to any control signal",
    "unrelated to scan_en",
    "independent of scan_en",
    "independent of any control signal",
    "independent of the control signal",
    "independent of any test-mode signal",
    "every cycle",
    "in every mode",
    "in all modes",
    "at all times regardless",
    "constant wiring",
    "constant connectivity",
    "hardwired connection",
    "hard-wired connection",
    "not gated by any signal",
    "not gated by scan_en",
]

results = []  # list of (requirement_id, bool_pass, reason)


def record(req_id, passed, reason=""):
    if passed:
        print("[TEST] PASS: {}".format(req_id))
    else:
        print("[TEST] FAIL: {}: {}".format(req_id, reason))
    results.append((req_id, passed, reason))


def fail_setup(path):
    print("[TEST] FAIL: SETUP: {} not found".format(path))
    sys.exit(1)


# ---------------------------------------------------------------------
# Load required input artifacts (SETUP failures if any missing).
# ---------------------------------------------------------------------
for p in (NETLIST_PATH, DESIGN_BRIEF_PATH, SCAN_ORDER_PATH):
    if not os.path.isfile(p):
        fail_setup(p)

with open(NETLIST_PATH, "r", encoding="utf-8") as f:
    netlist_text = f.read()

with open(SCAN_ORDER_PATH, "r", encoding="utf-8") as f:
    scan_order_text = f.read()

if not os.path.isfile(SUBMISSION_PATH):
    fail_setup(SUBMISSION_PATH)

with open(SUBMISSION_PATH, "r", encoding="utf-8") as f:
    submission_raw = f.read()


# ---------------------------------------------------------------------
# Lightweight regex-based Verilog instance parser.
#
# Matches lines/statements of the form:
#   MODULE_TYPE instance_name ( .port(sig), ... );
# possibly spanning multiple lines. We scan for the pattern:
#   <Identifier> <ws> <Identifier> <ws>* \(
# where the first identifier is not a Verilog keyword and is followed
# eventually by a '(' before a ';' - i.e. a module instantiation.
# ---------------------------------------------------------------------
VERILOG_KEYWORDS = {
    "module", "endmodule", "input", "output", "inout", "wire", "reg",
    "logic", "assign", "always", "begin", "end", "if", "else", "posedge",
    "negedge", "parameter", "localparam", "function", "endfunction",
    "task", "endtask", "generate", "endgenerate", "case", "endcase",
    "initial", "for", "while",
}


def parse_instance_names(text):
    # Strip comments to avoid false matches.
    no_line_comments = re.sub(r"//.*", "", text)
    no_block_comments = re.sub(r"/\*.*?\*/", "", no_line_comments, flags=re.DOTALL)

    instances = set()
    # Pattern: word boundary, TYPE (identifier), whitespace, INSTNAME
    # (identifier), optional whitespace, then '('.
    pattern = re.compile(
        r"(?<![\w])([A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        re.MULTILINE,
    )
    for m in pattern.finditer(no_block_comments):
        mod_type, inst_name = m.group(1), m.group(2)
        if mod_type in VERILOG_KEYWORDS or inst_name in VERILOG_KEYWORDS:
            continue
        # Heuristic: module type is typically declared uppercase/camel
        # in this design's cell library or a user module name; instance
        # name is whatever the author chose. We accept broadly and just
        # collect inst_name as a candidate instance identifier.
        instances.add(inst_name)
    return instances


valid_instance_names = parse_instance_names(netlist_text)
valid_instance_names_lower = {n.lower() for n in valid_instance_names}


# ---------------------------------------------------------------------
# Parse the submission JSON (FR1).
# ---------------------------------------------------------------------
submission = None
fr1_pass = True
fr1_reason = ""

try:
    submission = json.loads(submission_raw)
except Exception as e:
    fr1_pass = False
    fr1_reason = "invalid JSON: {}".format(e)

required_fields = {
    "trojan_detected": bool,
    "suspect_flops": list,
    "suspect_muxes": list,
    "confidence": (int, float),
    "rationale": str,
}

if fr1_pass:
    if not isinstance(submission, dict):
        fr1_pass = False
        fr1_reason = "top-level JSON value is not an object"
    else:
        missing = []
        wrong_type = []
        for field, expected_type in required_fields.items():
            if field not in submission:
                missing.append(field)
                continue
            value = submission[field]
            if field == "trojan_detected":
                # bool must be strictly bool (not 0/1 int, since Python
                # bool is a subclass of int this still works correctly
                # for JSON true/false -> Python True/False).
                if not isinstance(value, bool):
                    wrong_type.append(field)
            elif field == "confidence":
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    wrong_type.append(field)
            else:
                if not isinstance(value, expected_type):
                    wrong_type.append(field)
                elif expected_type is list:
                    if not all(isinstance(x, str) for x in value):
                        wrong_type.append(field)
        if missing:
            fr1_pass = False
            fr1_reason = "missing required field(s): {}".format(", ".join(missing))
        elif wrong_type:
            fr1_pass = False
            fr1_reason = "field(s) with wrong type: {}".format(", ".join(wrong_type))

record("FR1", fr1_pass, fr1_reason)


# Helper accessors that degrade gracefully if FR1 failed, so downstream
# checks can still run deterministically and report their own failures
# rather than crashing.
def get_field(name, default):
    if isinstance(submission, dict) and name in submission:
        return submission[name]
    return default


trojan_detected = get_field("trojan_detected", None)
suspect_flops_raw = get_field("suspect_flops", None)
suspect_muxes_raw = get_field("suspect_muxes", None)
confidence_raw = get_field("confidence", None)
rationale_raw = get_field("rationale", None)

suspect_flops = suspect_flops_raw if isinstance(suspect_flops_raw, list) else []
suspect_flops = [s for s in suspect_flops if isinstance(s, str)]
suspect_muxes = suspect_muxes_raw if isinstance(suspect_muxes_raw, list) else []
suspect_muxes = [s for s in suspect_muxes if isinstance(s, str)]


# ---------------------------------------------------------------------
# FR2: every listed suspect_flops/suspect_muxes entry must reference a
# real instance name found in the netlist.
# ---------------------------------------------------------------------
fr2_pass = True
fr2_reason = ""

if not isinstance(suspect_flops_raw, list) or not isinstance(suspect_muxes_raw, list):
    fr2_pass = False
    fr2_reason = "suspect_flops/suspect_muxes not present as lists"
else:
    bad_entries = []
    for name in suspect_flops + suspect_muxes:
        if name.lower() not in valid_instance_names_lower:
            bad_entries.append(name)
    if bad_entries:
        fr2_pass = False
        fr2_reason = "entries not found as real netlist instances: {}".format(
            ", ".join(sorted(set(bad_entries))[:10])
        )

record("FR2", fr2_pass, fr2_reason)


# ---------------------------------------------------------------------
# FR3: confidence numeric in [0.0, 1.0].
# ---------------------------------------------------------------------
fr3_pass = True
fr3_reason = ""

if confidence_raw is None or isinstance(confidence_raw, bool) or not isinstance(confidence_raw, (int, float)):
    fr3_pass = False
    fr3_reason = "confidence missing or non-numeric"
elif not (0.0 <= float(confidence_raw) <= 1.0):
    fr3_pass = False
    fr3_reason = "confidence {} outside [0.0, 1.0]".format(confidence_raw)

record("FR3", fr3_pass, fr3_reason)


# ---------------------------------------------------------------------
# FR4: rationale non-empty string >= 20 chars after stripping.
# ---------------------------------------------------------------------
fr4_pass = True
fr4_reason = ""

if rationale_raw is None or not isinstance(rationale_raw, str):
    fr4_pass = False
    fr4_reason = "rationale missing or not a string"
elif len(rationale_raw.strip()) < 20:
    fr4_pass = False
    fr4_reason = "rationale shorter than 20 characters after stripping"

record("FR4", fr4_pass, fr4_reason)


# ---------------------------------------------------------------------
# SR1: recall over key flops >= 3 of 4.
# ---------------------------------------------------------------------
submitted_flops_lower = {s.lower() for s in suspect_flops}
matched_flops = {f for f in KEY_FLOPS if f.lower() in submitted_flops_lower}

sr1_pass = len(matched_flops) >= 3
sr1_reason = "" if sr1_pass else "only {}/4 key flops identified ({})".format(
    len(matched_flops), sorted(matched_flops)
)
record("SR1", sr1_pass, sr1_reason)


# ---------------------------------------------------------------------
# SR2: recall over key splicing muxes >= 3 of 4.
# ---------------------------------------------------------------------
submitted_muxes_lower = {s.lower() for s in suspect_muxes}
matched_muxes = {m for m in KEY_MUXES if m.lower() in submitted_muxes_lower}

sr2_pass = len(matched_muxes) >= 3
sr2_reason = "" if sr2_pass else "only {}/4 key splice muxes identified ({})".format(
    len(matched_muxes), sorted(matched_muxes)
)
record("SR2", sr2_pass, sr2_reason)


# ---------------------------------------------------------------------
# SR3: trojan_detected must be exactly True.
# ---------------------------------------------------------------------
sr3_pass = trojan_detected is True
sr3_reason = "" if sr3_pass else "trojan_detected reported as {} instead of true".format(
    trojan_detected
)
record("SR3", sr3_pass, sr3_reason)


# ---------------------------------------------------------------------
# SR4: rationale must reflect scan-mode conditionality, not generic
# boilerplate, and must NOT reframe the leak as a permanent/always-on
# wiring defect independent of any control signal (contradiction
# catch). Optionally corroborate ground truth via iverilog/vvp
# simulation of tb_scan_leak.v against the netlist (this simulation
# validates that the leak mechanism we test against is real; it does
# NOT grade the submission's wording, and its unavailability does not
# penalize the submission).
# ---------------------------------------------------------------------

def normalize(s):
    return re.sub(r"\s+", " ", s.strip().lower())


rationale_text = rationale_raw if isinstance(rationale_raw, str) else ""
rationale_norm = normalize(rationale_text)

is_generic_baseline_text = (
    BASELINE_GENERIC_RATIONALE_NORMALIZED in rationale_norm
    or rationale_norm == BASELINE_GENERIC_RATIONALE_NORMALIZED
)


def has_scan_en_gating_assertion(text):
    """
    Detect a positive assertion that the leak is conditional on
    scan_en: look for occurrences of 'scan_en' (or 'scan-en'/'scan en')
    with a gating/conditional qualifier term within a small window of
    characters on either side. This distinguishes "the mux is
    controlled by scan_en" (mere mention) too, but combined with the
    generic CONDITIONALITY_TERMS check below and the negative-phrase
    veto, this is sufficient to require the rationale to actually
    engage with the conditional nature of the leak rather than just
    dropping the keyword.
    """
    scan_en_variants = [m.start() for pat in ("scan_en", "scan-en", "scan en")
                        for m in re.finditer(re.escape(pat), text)]
    if not scan_en_variants:
        return False
    window = 40
    for idx in scan_en_variants:
        start = max(0, idx - window)
        end = min(len(text), idx + window)
        snippet = text[start:end]
        for qualifier in GATING_QUALIFIER_TERMS:
            if qualifier in snippet:
                return True
    return False


has_conditionality_term = any(term in rationale_norm for term in CONDITIONALITY_TERMS)
has_gating_assertion = has_scan_en_gating_assertion(rationale_norm)
has_negative_always_on = any(term in rationale_norm for term in NEGATIVE_ALWAYS_ON_TERMS)

sr4_pass = (
    (has_conditionality_term or has_gating_assertion)
    and not has_negative_always_on
    and not is_generic_baseline_text
)

sr4_reason_parts = []
if not (has_conditionality_term or has_gating_assertion):
    sr4_reason_parts.append(
        "rationale lacks scan-mode-conditionality language (expected terms like scan_en/capture/shift, "
        "or an explicit scan_en-gated assertion)"
    )
if has_negative_always_on:
    sr4_reason_parts.append(
        "rationale describes the leak as permanent/always-on/control-signal-independent, "
        "contradicting scan-mode conditionality"
    )
if is_generic_baseline_text:
    sr4_reason_parts.append("rationale matches generic non-substantive boilerplate text")
sr4_reason = "; ".join(sr4_reason_parts)


def run_optional_simulation_corroboration():
    """
    Attempts to independently corroborate the ground-truth leak using
    iverilog/vvp against the real netlist and testbench, comparing
    scan_en=0 vs scan_en=1 scan_out behavior. This is used only to
    validate the evaluator's own understanding of the design; its
    result does not affect SR4's pass/fail decision on the submission,
    and any failure/timeout/toolchain-absence here is silently
    tolerated.
    """
    iverilog = shutil.which("iverilog")
    vvp = shutil.which("vvp")
    if not iverilog or not vvp or not os.path.isfile(TB_PATH):
        return None

    tmpdir = tempfile.mkdtemp(prefix="scan_leak_")
    sim_out = os.path.join(tmpdir, "sim.vvp")
    try:
        compile_proc = subprocess.run(
            [iverilog, "-g2012", "-o", sim_out, NETLIST_PATH, TB_PATH],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if compile_proc.returncode != 0:
            return None
        run_proc = subprocess.run(
            [vvp, sim_out],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return run_proc.stdout
    except Exception:
        return None
    finally:
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


# Best-effort corroboration; result intentionally not used to alter
# verdicts, only potentially useful for debugging/logging.
_ = run_optional_simulation_corroboration()

record("SR4", sr4_pass, sr4_reason)


# ---------------------------------------------------------------------
# Final verdict.
# ---------------------------------------------------------------------
all_passed = all(passed for (_id, passed, _reason) in results)
sys.exit(0 if all_passed else 1)