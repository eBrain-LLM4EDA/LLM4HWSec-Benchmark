#!/usr/bin/env python3
"""
evaluate.py - Grader for rtl_opcode_privilege_trojan_001

Reads the fixed RTL inputs under inputs/ (decode_ctrl.v, opcode_map.txt),
cross-checks them via iverilog/vvp simulation, and grades the participant's
answer file at submission/trojan_report.json against the hidden ground
truth loaded from evaluation/private/ground_truth.json.

Emits one '[TEST] PASS: <id>' or '[TEST] FAIL: <id>: <reason>' line per
requirement (FR1-FR4, SR1-SR4) and exits 0 iff all pass, else 1.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INPUTS_DIR = os.path.join(REPO_ROOT, "inputs")
EVAL_DIR = os.path.join(REPO_ROOT, "evaluation")
SUBMISSION_PATH = os.path.join(REPO_ROOT, "submission", "trojan_report.json")

DECODE_CTRL_V = os.path.join(INPUTS_DIR, "decode_ctrl.v")
OPCODE_MAP_TXT = os.path.join(INPUTS_DIR, "opcode_map.txt")
TB_PATH = os.path.join(EVAL_DIR, "tb_decode_ctrl.v")
GROUND_TRUTH_PATH = os.path.join(EVAL_DIR, "private", "ground_truth.json")

RESULTS = []  # list of (req_id, passed_bool, message)


def record(req_id, passed, message=""):
    RESULTS.append((req_id, passed, message))
    if passed:
        print("[TEST] PASS: %s" % req_id)
    else:
        print("[TEST] FAIL: %s: %s" % (req_id, message))


def fatal_setup(req_ids, path):
    for rid in req_ids:
        record(rid, False, "SETUP: %s not found" % path)


# ---------------------------------------------------------------------------
# Helpers: load fixed input artifacts
# ---------------------------------------------------------------------------

def load_opcode_map(path):
    """Parse opcode_map.txt into {opcode_int: (we, alu_bits_str, valid, priv)}."""
    doc = {}
    if not os.path.isfile(path):
        return None
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 6:
                continue
            tok = parts[0]
            if not re.match(r'^0[xX][0-9a-fA-F]+$', tok):
                continue
            try:
                opcode = int(tok, 16)
                we = int(parts[2])
                alu_bits = parts[3]
                valid = int(parts[4])
                priv = int(parts[5])
            except (ValueError, IndexError):
                continue
            if 0 <= opcode <= 255:
                doc[opcode] = (we, alu_bits, valid, priv)
    return doc


def run_simulation():
    """
    Compile inputs/decode_ctrl.v with evaluation/tb_decode_ctrl.v via iverilog,
    run with vvp, parse OPCRES lines.
    Returns (ok, reason, sim_results) where sim_results maps
    opcode_int -> (we, priv, alu_bits_str, valid).
    """
    if not os.path.isfile(DECODE_CTRL_V):
        return False, "compile failed: inputs/decode_ctrl.v not found", {}
    if not os.path.isfile(TB_PATH):
        return False, "compile failed: evaluation/tb_decode_ctrl.v not found", {}

    with tempfile.TemporaryDirectory() as tmpdir:
        sim_path = os.path.join(tmpdir, "sim.vvp")
        try:
            compile_proc = subprocess.run(
                ["iverilog", "-g2012", "-o", sim_path, DECODE_CTRL_V, TB_PATH],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            return False, "compile failed: iverilog timed out", {}
        except FileNotFoundError:
            return False, "compile failed: iverilog not found on PATH", {}

        if compile_proc.returncode != 0:
            stderr = compile_proc.stderr.decode("utf-8", errors="replace")
            first_line = stderr.strip().splitlines()[0] if stderr.strip() else "unknown error"
            return False, "compile failed: %s" % first_line, {}

        try:
            run_proc = subprocess.run(
                ["vvp", sim_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            return False, "run crashed/timed out", {}
        except FileNotFoundError:
            return False, "run crashed/timed out: vvp not found on PATH", {}

        stdout = run_proc.stdout.decode("utf-8", errors="replace")

        sim_results = {}
        pattern = re.compile(
            r'OPCRES\s+([0-9a-fA-F]{2})\s+([01])\s+([01])\s+([01]{3})\s+([01])'
        )
        for line in stdout.splitlines():
            m = pattern.search(line)
            if m:
                opcode = int(m.group(1), 16)
                we = int(m.group(2))
                priv = int(m.group(3))
                alu = m.group(4)
                valid = int(m.group(5))
                sim_results[opcode] = (we, priv, alu, valid)

        if run_proc.returncode != 0 and len(sim_results) < 256:
            return False, "run crashed/timed out: vvp exited nonzero with incomplete output", sim_results

        if len(sim_results) != 256:
            return False, (
                "run crashed/timed out: expected 256 OPCRES lines, got %d" % len(sim_results)
            ), sim_results

        return True, "", sim_results


# ---------------------------------------------------------------------------
# Helpers: normalize submission fields
# ---------------------------------------------------------------------------

def normalize_opcode(value):
    """Parse a trigger_opcode string into an int 0-255, or None if unparseable."""
    if isinstance(value, (int, float)):
        try:
            v = int(value)
            if 0 <= v <= 255:
                return v
        except (ValueError, TypeError):
            return None
        return None
    if not isinstance(value, str):
        return None
    t = value.strip()
    if not t:
        return None

    # Verilog-style literal: 8'hE7 / 8'b11100111 / 8'd231
    m = re.match(r"^\d*'([bBhHdDoO])([0-9a-fA-F_xXzZ]+)$", t)
    if m:
        base = m.group(1).lower()
        digits = m.group(2).replace('_', '')
        try:
            if base == 'b':
                return int(digits, 2)
            if base == 'h':
                return int(digits, 16)
            if base == 'd':
                return int(digits, 10)
            if base == 'o':
                return int(digits, 8)
        except ValueError:
            return None

    # 0x / 0X hex prefix
    m2 = re.match(r'^0[xX]([0-9a-fA-F]+)$', t)
    if m2:
        try:
            v = int(m2.group(1), 16)
            return v if 0 <= v <= 255 else None
        except ValueError:
            return None

    # 0b / 0B binary prefix
    m3 = re.match(r'^0[bB]([01]+)$', t)
    if m3:
        try:
            v = int(m3.group(1), 2)
            return v if 0 <= v <= 255 else None
        except ValueError:
            return None

    # Plain 1-2 char hex (e.g. "E7", "7f")
    m4 = re.match(r'^[0-9a-fA-F]{1,2}$', t)
    if m4:
        try:
            v = int(t, 16)
            return v if 0 <= v <= 255 else None
        except ValueError:
            return None

    # Plain decimal (1-3 digits)
    m5 = re.match(r'^\d{1,3}$', t)
    if m5:
        try:
            v = int(t, 10)
            return v if 0 <= v <= 255 else None
        except ValueError:
            return None

    # Fallback: search for an embedded 0xHH token in a free-text description
    m6 = re.search(r'0[xX]([0-9a-fA-F]{2})', t)
    if m6:
        try:
            v = int(m6.group(1), 16)
            return v if 0 <= v <= 255 else None
        except ValueError:
            return None

    # Fallback: search for an embedded bare 2-hex-digit token like "E7"
    m7 = re.search(r'(?<![0-9a-fA-Z])([0-9a-fA-F]{2})(?![0-9a-zA-Z])', t)
    if m7:
        try:
            v = int(m7.group(1), 16)
            return v if 0 <= v <= 255 else None
        except ValueError:
            return None

    return None


def normalize_confidence(value):
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f


def is_substantive_rationale(rationale, evidence_keywords, banned_generic_phrases):
    if not isinstance(rationale, str):
        return False
    stripped = rationale.strip()
    if len(stripped) < 40:
        return False
    lowered = stripped.lower()
    # If the entire rationale (modulo trailing punctuation) IS one of the
    # banned generic boilerplate phrases, it's not substantive.
    normalized_for_banned = lowered.rstrip('. !')
    for phrase in banned_generic_phrases:
        if normalized_for_banned == phrase.lower().rstrip('. !'):
            return False
    has_keyword = any(kw.lower() in lowered for kw in evidence_keywords)
    return has_keyword


# ---------------------------------------------------------------------------
# Main grading logic
# ---------------------------------------------------------------------------

def main():
    all_req_ids = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]

    # --- Load ground truth (private) ---
    if not os.path.isfile(GROUND_TRUTH_PATH):
        fatal_setup(all_req_ids, "evaluation/private/ground_truth.json")
        sys.exit(1)
    try:
        with open(GROUND_TRUTH_PATH, "r") as f:
            ground_truth = json.load(f)
    except (ValueError, OSError) as e:
        fatal_setup(all_req_ids, "evaluation/private/ground_truth.json (%s)" % e)
        sys.exit(1)

    gt_opcode_int = ground_truth.get("trigger_opcode_int", 231)
    gt_payload_regex_str = ground_truth.get("payload_match_regex", r"privilege_?ok")
    gt_fp_signal_names = [s.lower() for s in ground_truth.get(
        "fp_signal_names", ["alu_op", "valid", "write_enable"])]
    gt_evidence_keywords = ground_truth.get("evidence_keywords", [])
    gt_banned_phrases = ground_truth.get("banned_generic_phrases", [])

    payload_pattern = re.compile(gt_payload_regex_str, re.IGNORECASE)

    # --- Load opcode_map.txt ---
    if not os.path.isfile(OPCODE_MAP_TXT):
        fatal_setup(all_req_ids, "inputs/opcode_map.txt")
        sys.exit(1)
    documented = load_opcode_map(OPCODE_MAP_TXT)
    if documented is None:
        fatal_setup(all_req_ids, "inputs/opcode_map.txt")
        sys.exit(1)

    # --- Load decode_ctrl.v presence check (existence only; content used via sim) ---
    if not os.path.isfile(DECODE_CTRL_V):
        fatal_setup(all_req_ids, "inputs/decode_ctrl.v")
        sys.exit(1)

    # --- Load submission ---
    if not os.path.isfile(SUBMISSION_PATH):
        fatal_setup(all_req_ids, "submission/trojan_report.json")
        sys.exit(1)

    submission_raw = None
    submission_parse_error = None
    try:
        with open(SUBMISSION_PATH, "r") as f:
            submission_raw = json.load(f)
    except (ValueError, OSError) as e:
        submission_parse_error = str(e)

    # --- FR4: schema validity ---
    fr4_ok = True
    fr4_reason = ""
    candidates_raw = []
    if submission_parse_error is not None:
        fr4_ok = False
        fr4_reason = "invalid JSON: %s" % submission_parse_error
    elif not isinstance(submission_raw, dict):
        fr4_ok = False
        fr4_reason = "top-level submission is not a JSON object"
    elif "candidates" not in submission_raw:
        fr4_ok = False
        fr4_reason = "missing top-level 'candidates' key"
    elif not isinstance(submission_raw["candidates"], list):
        fr4_ok = False
        fr4_reason = "'candidates' is not a list"
    else:
        candidates_raw = submission_raw["candidates"]
        for idx, cand in enumerate(candidates_raw):
            if not isinstance(cand, dict):
                fr4_ok = False
                fr4_reason = "candidate[%d] is not an object" % idx
                break
            if not isinstance(cand.get("trigger_opcode"), str):
                fr4_ok = False
                fr4_reason = "candidate[%d] missing/invalid string field 'trigger_opcode'" % idx
                break
            if not isinstance(cand.get("payload_signal"), str):
                fr4_ok = False
                fr4_reason = "candidate[%d] missing/invalid string field 'payload_signal'" % idx
                break
            conf = normalize_confidence(cand.get("confidence"))
            if conf is None or not (0.0 <= conf <= 1.0):
                fr4_ok = False
                fr4_reason = "candidate[%d] missing/invalid numeric field 'confidence' in [0,1]" % idx
                break
            rationale = cand.get("rationale")
            if not isinstance(rationale, str) or len(rationale.strip()) == 0:
                fr4_ok = False
                fr4_reason = "candidate[%d] missing/invalid non-empty string field 'rationale'" % idx
                break

    record("FR4", fr4_ok, fr4_reason)

    # --- Build normalized candidate list (best-effort, used regardless of FR4) ---
    normalized_candidates = []
    if isinstance(submission_raw, dict) and isinstance(submission_raw.get("candidates"), list):
        for cand in submission_raw["candidates"]:
            if not isinstance(cand, dict):
                continue
            opcode_int = normalize_opcode(cand.get("trigger_opcode"))
            payload_raw = cand.get("payload_signal")
            payload_lower = payload_raw.strip().lower() if isinstance(payload_raw, str) else ""
            confidence = normalize_confidence(cand.get("confidence"))
            if confidence is None:
                confidence = 0.0
            rationale = cand.get("rationale") if isinstance(cand.get("rationale"), str) else ""
            normalized_candidates.append({
                "opcode_int": opcode_int,
                "payload_lower": payload_lower,
                "confidence": confidence,
                "rationale": rationale,
            })

    # --- Run simulation for FR1/FR2/FR3 ---
    sim_ok, sim_reason, sim_results = run_simulation()

    if not sim_ok:
        record("FR1", False, sim_reason)
        record("FR2", False, sim_reason)
        record("FR3", False, sim_reason)
    else:
        record("FR1", True)

        # FR2: documented opcodes must match exactly
        fr2_ok = True
        fr2_reason = ""
        for opcode, (doc_we, doc_alu, doc_valid, doc_priv) in sorted(documented.items()):
            sim_row = sim_results.get(opcode)
            if sim_row is None:
                fr2_ok = False
                fr2_reason = "opcode 0x%02X missing from simulation output" % opcode
                break
            sim_we, sim_priv, sim_alu, sim_valid = sim_row
            if (sim_we != doc_we or sim_priv != doc_priv or
                    sim_alu != doc_alu or sim_valid != doc_valid):
                fr2_ok = False
                fr2_reason = (
                    "opcode 0x%02X mismatch: expected we=%d alu=%s valid=%d priv=%d, "
                    "got we=%d alu=%s valid=%d priv=%d" % (
                        opcode, doc_we, doc_alu, doc_valid, doc_priv,
                        sim_we, sim_alu, sim_valid, sim_priv
                    )
                )
                break
        record("FR2", fr2_ok, fr2_reason)

        # FR3: undocumented deviations must be reported
        deviation_set = set()
        for opcode in range(256):
            if opcode in documented:
                continue
            sim_row = sim_results.get(opcode)
            if sim_row is None:
                continue
            sim_we, sim_priv, sim_alu, sim_valid = sim_row
            if sim_we != 0 or sim_priv != 0 or sim_valid != 0:
                deviation_set.add(opcode)

        fr3_ok = True
        fr3_reason = ""
        if deviation_set:
            reported_opcodes = set(
                c["opcode_int"] for c in normalized_candidates if c["opcode_int"] is not None
            )
            for opcode in sorted(deviation_set):
                if opcode not in reported_opcodes:
                    fr3_ok = False
                    fr3_reason = "undocumented deviation 0x%02X undocumented in report" % opcode
                    break
        record("FR3", fr3_ok, fr3_reason)

    # --- SR1: payload correctly identified as privilege_ok, paired with 0xE7 ---
    sr1_ok = any(
        c["opcode_int"] == gt_opcode_int and payload_pattern.search(c["payload_lower"])
        for c in normalized_candidates
    )
    record("SR1", sr1_ok, "" if sr1_ok else
           "no candidate identifies payload_signal as privilege_ok for the 0xE7 trigger")

    # --- SR2: trigger opcode correctly identified as 0xE7, paired with privilege_ok payload ---
    sr2_ok = any(
        c["opcode_int"] == gt_opcode_int and payload_pattern.search(c["payload_lower"])
        for c in normalized_candidates
    )
    record("SR2", sr2_ok, "" if sr2_ok else
           "no candidate resolves trigger_opcode to 0xE7 paired with privilege_ok payload")

    # --- confirmed_exists: the fully correct, confident, substantive finding ---
    confirmed_exists = any(
        c["opcode_int"] == gt_opcode_int
        and payload_pattern.search(c["payload_lower"])
        and c["confidence"] >= 0.5
        and is_substantive_rationale(c["rationale"], gt_evidence_keywords, gt_banned_phrases)
        for c in normalized_candidates
    )

    # --- SR3: per-candidate false-positive control ---
    # Every candidate is inspected independently: a high-confidence candidate
    # that names a documented opcode (regardless of whether another candidate
    # correctly reports 0xE7) or an unrelated documented signal not matching
    # privilege_ok is itself a false positive and must FAIL SR3, even when a
    # correct 0xE7/privilege_ok candidate is also present in the array.
    sr3_ok = True
    sr3_reason = ""
    for c in normalized_candidates:
        if c["confidence"] < 0.5:
            continue
        opc = c["opcode_int"]
        payload_is_privok = bool(payload_pattern.search(c["payload_lower"]))
        is_documented_opcode = (opc is not None and opc in documented)
        is_unrelated_signal = (not payload_is_privok and c["payload_lower"] in gt_fp_signal_names)
        if is_documented_opcode or is_unrelated_signal:
            sr3_ok = False
            sr3_reason = (
                "high-confidence candidate names a documented opcode/unrelated signal "
                "(trigger_opcode=%r, payload_signal=%r, confidence=%.2f) as a trojan finding" % (
                    c.get("opcode_int"), c.get("payload_lower"), c.get("confidence")
                )
            )
            break
    record("SR3", sr3_ok, sr3_reason)

    # --- SR4: rationale evidence quality ---
    sr4_ok = confirmed_exists
    record("SR4", sr4_ok, "" if sr4_ok else
           "no substantive evidence-based rationale for the correct finding")

    # --- Final verdict ---
    overall_pass = all(passed for (_, passed, _) in RESULTS)
    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()