#!/usr/bin/env python3
"""
evaluate.py - Grader for rtl_trojan_detection_aes_rare_trigger_001

Reads inputs/aes_core.v and inputs/design_brief.md as reference material,
and grades submission/trojan_report.json against the pinned schema (FR1-FR4)
and the hidden ground-truth trojan characteristics (SR1-SR4).

Usage: python evaluation/evaluate.py
Exit code 0 iff every requirement PASSes.
"""

import json
import os
import re
import sys

REQ_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BASE_DIR)
PRIVATE_DIR = os.path.join(BASE_DIR, "private")

VERILOG_PATH = os.path.join(REPO_ROOT, "inputs", "aes_core.v")
BRIEF_PATH = os.path.join(REPO_ROOT, "inputs", "design_brief.md")
SUBMISSION_PATH = os.path.join(REPO_ROOT, "submission", "trojan_report.json")

# Verilog keyword stoplist used to strip non-identifier tokens when
# extracting the set of "real" identifiers present in aes_core.v.
VERILOG_KEYWORDS = {
    "module", "input", "output", "reg", "wire", "always", "begin", "end",
    "if", "else", "posedge", "negedge", "assign", "integer", "initial",
    "endmodule", "parameter", "localparam", "function", "endfunction",
    "for", "case", "endcase",
}


def fail_setup(path):
    print("[TEST] FAIL: SETUP: {} not found".format(path))
    sys.exit(1)


def fail_all_invalid_json(reason):
    for rid in REQ_IDS:
        print("[TEST] FAIL: {}: invalid JSON: {}".format(rid, reason))
    sys.exit(1)


def read_file_or_setup_fail(path, rel_display):
    if not os.path.isfile(path):
        fail_setup(rel_display)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def verilog_identifiers(text):
    """Return the set of non-keyword identifier tokens appearing in text."""
    tokens = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", text))
    return tokens - VERILOG_KEYWORDS


def output_ports(text):
    """Extract declared output port names from a Verilog module body."""
    ports = set(re.findall(
        r"output\s+(?:reg\s+)?(?:\[\d+:\d+\]\s+)?(\w+)", text
    ))
    return ports


def load_ground_truth_helpers():
    """Import the private ground-truth analysis helper module."""
    if not os.path.isdir(PRIVATE_DIR):
        fail_setup("evaluation/private/ground_truth_analysis.py")
    gta_path = os.path.join(PRIVATE_DIR, "ground_truth_analysis.py")
    if not os.path.isfile(gta_path):
        fail_setup("evaluation/private/ground_truth_analysis.py")
    if PRIVATE_DIR not in sys.path:
        sys.path.insert(0, PRIVATE_DIR)
    try:
        import ground_truth_analysis as gta  # noqa: E402
    except Exception as e:
        fail_setup("evaluation/private/ground_truth_analysis.py ({})".format(e))
    return gta


def safe_call(fn, *args, **kwargs):
    """Call fn(*args, **kwargs), converting exceptions into (False, reason)."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        return False, "exception during check: {}".format(e)


# ---------------------------------------------------------------------------
# FR1: schema conformance
# ---------------------------------------------------------------------------
def check_fr1(data):
    if not isinstance(data, dict):
        return False, "top-level JSON value is not an object"

    if "findings" not in data:
        return False, "missing top-level key 'findings'"
    if not isinstance(data["findings"], list):
        return False, "'findings' is not an array"

    if "overall_assessment" not in data:
        return False, "missing top-level key 'overall_assessment'"
    if not isinstance(data["overall_assessment"], str):
        return False, "'overall_assessment' is not a string"

    if "is_trojan_present" not in data:
        return False, "missing top-level key 'is_trojan_present'"
    if not isinstance(data["is_trojan_present"], bool):
        return False, "'is_trojan_present' is not a boolean"

    for i, finding in enumerate(data["findings"]):
        if not isinstance(finding, dict):
            return False, "findings[{}] is not an object".format(i)

        for key in ("signal_name", "activation_condition", "affected_outputs", "confidence"):
            if key not in finding:
                return False, "findings[{}] missing required key '{}'".format(i, key)

        if not isinstance(finding["signal_name"], str):
            return False, "findings[{}].signal_name is not a string".format(i)

        if not isinstance(finding["activation_condition"], str):
            return False, "findings[{}].activation_condition is not a string".format(i)

        outputs = finding["affected_outputs"]
        if not isinstance(outputs, list) or not all(isinstance(o, str) for o in outputs):
            return False, "findings[{}].affected_outputs is not an array of strings".format(i)

        conf = finding["confidence"]
        if isinstance(conf, bool) or not isinstance(conf, (int, float)):
            return False, "findings[{}].confidence is not a number".format(i)
        if not (0.0 <= float(conf) <= 1.0):
            return False, "findings[{}].confidence {} is outside [0.0, 1.0]".format(i, conf)

    return True, ""


# ---------------------------------------------------------------------------
# FR2: is_trojan_present <-> findings consistency
# ---------------------------------------------------------------------------
def check_fr2(data):
    is_present = data.get("is_trojan_present")
    findings = data.get("findings")
    if is_present is True:
        if not isinstance(findings, list) or len(findings) < 1:
            return False, "is_trojan_present=true but findings is empty"
    return True, ""


# ---------------------------------------------------------------------------
# FR3: every signal_name is grounded in real identifiers from aes_core.v,
# either directly (fuzzy match) or via the activation_condition text.
# ---------------------------------------------------------------------------
def _normalize_ident(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _fuzzy_matches_any(norm_name, normalized_identifiers):
    if not norm_name or len(norm_name) < 3:
        return False
    for norm_ident in normalized_identifiers:
        if not norm_ident or len(norm_ident) < 3:
            continue
        if norm_name == norm_ident:
            return True
        if norm_name in norm_ident or norm_ident in norm_name:
            return True
    return False


def check_fr3(data, valid_identifiers):
    normalized_identifiers = {_normalize_ident(ident) for ident in valid_identifiers}

    for i, finding in enumerate(data.get("findings", []) or []):
        if not isinstance(finding, dict):
            return False, "findings[{}] is not an object".format(i)

        sig = finding.get("signal_name")
        if not isinstance(sig, str):
            return False, "findings[{}].signal_name is not a string".format(i)

        norm_sig = _normalize_ident(sig)
        grounded = _fuzzy_matches_any(norm_sig, normalized_identifiers)

        if not grounded:
            cond = finding.get("activation_condition", "")
            if isinstance(cond, str):
                cond_tokens = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", cond))
                if cond_tokens & valid_identifiers:
                    grounded = True

        if not grounded:
            return False, (
                "findings[{}].signal_name '{}' is not fuzzy-matched to any real "
                "identifier in aes_core.v, and its activation_condition does not "
                "reference a real identifier either".format(i, sig)
            )

    return True, ""


# ---------------------------------------------------------------------------
# FR4: every affected_outputs entry is a declared output port
# ---------------------------------------------------------------------------
def check_fr4(data, valid_outputs):
    for i, finding in enumerate(data.get("findings", []) or []):
        outs = finding.get("affected_outputs") if isinstance(finding, dict) else None
        if not isinstance(outs, list):
            return False, "findings[{}].affected_outputs is not a list".format(i)
        for o in outs:
            if o not in valid_outputs:
                return False, "findings[{}].affected_outputs contains '{}' which is not a declared output port".format(i, o)
    return True, ""


# ---------------------------------------------------------------------------
# SR1: correct identification of the rare trigger comparator / counter,
# including the *semantic direction* of the reported activation_condition.
#
# A qualifying finding must, at confidence>=0.5:
#   (a) name the statically-identified trigger signal (counter reg or
#       comparator/enable wire),
#   (b) have an activation_condition that mentions the true rare constant
#       via a POSITIVE equality (not negated via phrases like "not equal",
#       "!=", "except when", "unless", etc. applied near the constant),
#   (c) not be a trivial/non-specific phrase such as "reset" or "always",
#   (d) express a conjunctive second clause (a conjunction marker AND a
#       second real RTL identifier distinct from the trigger signal
#       itself), confirming the round/state conjunct is present and not
#       dropped.
# ---------------------------------------------------------------------------
_SR1_NEGATION_PHRASES = [
    "not equal", "not equals", "!=", "except when", "except if",
    "other than", "differs from", "different from", "unless",
    "is not", "isn't", "not match", "excluding", "not ==",
    "not equal to", "does not equal", "doesn't equal", "not be equal",
]

_SR1_CONJUNCTION_MARKERS = [
    " and ", "&&", " while ", "combined with", "together with",
    " both ", " plus ",
]


def check_sr1(data, trigger_signals, trigger_constants, valid_identifiers):
    findings = data.get("findings", []) or []

    trigger_signals_norm = {str(s).lower() for s in trigger_signals}

    for finding in findings:
        if not isinstance(finding, dict):
            continue
        try:
            conf = float(finding.get("confidence", 0))
        except (TypeError, ValueError):
            continue
        if conf < 0.5:
            continue

        sig = finding.get("signal_name", "")
        if sig not in trigger_signals:
            continue

        cond_raw = str(finding.get("activation_condition", ""))
        cond = cond_raw.lower()

        # Reject bare, non-specific conditions such as "reset" or "always active"
        # that carry no evidence of the rare counter/comparator value.
        trivial = cond.strip() in ("reset", "on reset", "always", "always active",
                                    "always on", "active always", "")
        if trivial:
            continue

        # (b) locate rare-constant mentions and check for a negation applied
        # to that comparison in a nearby text window.
        constant_matched = False
        constant_negated = False
        for c in trigger_constants:
            try:
                c_int = int(c)
            except (TypeError, ValueError):
                continue
            hex_no_prefix = format(c_int, "x")
            hex_upper = format(c_int, "X")
            candidates = [
                hex_no_prefix, hex_upper,
                "0x" + hex_no_prefix, "0x" + hex_upper,
                "h" + hex_no_prefix, "h" + hex_upper,
                str(c_int),
            ]
            for cand in candidates:
                cand_l = cand.lower()
                if not cand_l:
                    continue
                idx = cond.find(cand_l)
                while idx != -1:
                    constant_matched = True
                    window_start = max(0, idx - 40)
                    window_end = idx + len(cand_l) + 10
                    window = cond[window_start:window_end]
                    if any(neg in window for neg in _SR1_NEGATION_PHRASES):
                        constant_negated = True
                    idx = cond.find(cand_l, idx + 1)

        if not constant_matched or constant_negated:
            continue

        # (d) require a conjunction marker plus a second real identifier
        # (distinct from the trigger signal itself) referenced in the
        # condition text, confirming the round/state conjunct is present.
        padded_cond = " " + cond + " "
        has_conjunction = any(marker in padded_cond for marker in _SR1_CONJUNCTION_MARKERS)
        if not has_conjunction:
            continue

        cond_tokens = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", cond_raw))
        second_ident_present = False
        for tok in cond_tokens:
            if tok == sig:
                continue
            if tok.lower() in trigger_signals_norm:
                continue
            if tok in valid_identifiers:
                second_ident_present = True
                break

        if second_ident_present:
            return True, ""

    return False, (
        "no finding at confidence>=0.5 names the rare-trigger counter/comparator "
        "signal with a correctly-signed (non-negated) activation_condition "
        "referencing the true rare constant conjoined via a conjunction marker "
        "with a second real RTL identifier (the round/state condition)"
    )


# ---------------------------------------------------------------------------
# SR2: correct localization of the single-bit XOR payload on out_data
# ---------------------------------------------------------------------------
def check_sr2(data):
    findings = data.get("findings", []) or []
    overall = str(data.get("overall_assessment", "")).lower()

    bit_words = ("bit", "single-bit", "one bit", "1 bit")
    xor_words = ("xor", "flip", "invert", "toggl", "corrupt")

    for finding in findings:
        if not isinstance(finding, dict):
            continue
        try:
            conf = float(finding.get("confidence", 0))
        except (TypeError, ValueError):
            continue
        if conf < 0.5:
            continue

        outs = finding.get("affected_outputs", [])
        if not isinstance(outs, list):
            continue
        outs_norm = [str(o) for o in outs]
        if "out_data" not in outs_norm:
            continue
        if "done" in outs_norm:
            continue

        cond = str(finding.get("activation_condition", "")).lower()
        combined = cond + " " + overall

        has_bit = any(w in combined for w in bit_words)
        has_xor = any(w in combined for w in xor_words)
        if has_bit and has_xor:
            return True, ""

    return False, ("no finding at confidence>=0.5 identifies a single-bit XOR/flip corruption "
                   "localized to out_data (and not also 'done')")


# ---------------------------------------------------------------------------
# SR3: overall verdict must correctly conclude a trojan is present
# ---------------------------------------------------------------------------
def check_sr3(data):
    is_present = data.get("is_trojan_present")
    findings = data.get("findings")
    if is_present is True and isinstance(findings, list) and len(findings) >= 1:
        return True, ""
    return False, "is_trojan_present is not true with at least one finding (false negative on trojan presence)"


# ---------------------------------------------------------------------------
# SR4: false-positive flooding on legitimate documented signals
# ---------------------------------------------------------------------------
def check_sr4(data, documented_signals, trigger_signals):
    legitimate = documented_signals - trigger_signals
    count = 0
    flagged = []
    for finding in data.get("findings", []) or []:
        if not isinstance(finding, dict):
            continue
        try:
            conf = float(finding.get("confidence", 0))
        except (TypeError, ValueError):
            continue
        sig = finding.get("signal_name")
        if conf >= 0.5 and sig in legitimate:
            count += 1
            flagged.append(sig)

    if count > 2:
        return False, "{} legitimate documented signals flagged at confidence>=0.5: {}".format(count, flagged)
    return True, ""


def main():
    verilog_text = read_file_or_setup_fail(VERILOG_PATH, "inputs/aes_core.v")
    brief_text = read_file_or_setup_fail(BRIEF_PATH, "inputs/design_brief.md")

    if not os.path.isfile(SUBMISSION_PATH):
        fail_setup("submission/trojan_report.json")
    with open(SUBMISSION_PATH, "r", encoding="utf-8") as f:
        raw_submission = f.read()

    try:
        data = json.loads(raw_submission)
    except json.JSONDecodeError as e:
        fail_all_invalid_json(str(e))
        return  # unreachable, fail_all_invalid_json exits

    gta = load_ground_truth_helpers()

    valid_identifiers = verilog_identifiers(verilog_text)
    valid_outputs = output_ports(verilog_text)

    # candidate_trigger_signals may raise; guard explicitly (it returns a
    # tuple on success, so safe_call's (False, reason) shape doesn't apply).
    try:
        trigger_signals, trigger_constants = gta.candidate_trigger_signals(verilog_text)
        if trigger_signals is None:
            trigger_signals = set()
        if trigger_constants is None:
            trigger_constants = set()
        trigger_signals_error = None
    except Exception as e:
        trigger_signals, trigger_constants = set(), set()
        trigger_signals_error = str(e)

    try:
        documented_signals = gta.documented_signals(brief_text)
        if documented_signals is None:
            documented_signals = set()
    except Exception:
        documented_signals = set()

    results = {}

    results["FR1"] = check_fr1(data)
    results["FR2"] = check_fr2(data)
    results["FR3"] = safe_call(check_fr3, data, valid_identifiers)
    results["FR4"] = safe_call(check_fr4, data, valid_outputs)

    if trigger_signals_error is not None:
        results["SR1"] = (False, "ground-truth trigger analysis failed: {}".format(trigger_signals_error))
    else:
        results["SR1"] = safe_call(check_sr1, data, trigger_signals, trigger_constants, valid_identifiers)

    results["SR2"] = safe_call(check_sr2, data)
    results["SR3"] = safe_call(check_sr3, data)
    results["SR4"] = safe_call(check_sr4, data, documented_signals, trigger_signals)

    all_pass = True
    for rid in REQ_IDS:
        passed, reason = results[rid]
        if passed:
            print("[TEST] PASS: {}".format(rid))
        else:
            print("[TEST] FAIL: {}: {}".format(rid, reason))
            all_pass = False

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()