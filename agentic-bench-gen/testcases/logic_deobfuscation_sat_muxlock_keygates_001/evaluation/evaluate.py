#!/usr/bin/env python3
"""
evaluate.py -- Grader for logic_deobfuscation_sat_muxlock_keygates_001

Reads:
  inputs/locked_netlist.v          (reference netlist structure)
  inputs/locking_description.md    (informational cross-reference only)
  inputs/primary_io_list.txt        (not required for grading logic)
  submission/recovered_key.json     (the graded answer file)
  evaluation/private/ground_truth.json (hidden ground truth)
  evaluation/private/grading_lib.py (pure helper functions)

Emits one '[TEST] PASS: <id>' or '[TEST] FAIL: <id>: <reason>' line per
requirement id: FR1, FR2, FR3, FR4, SR1, SR2, SR3.

Exit code 0 iff all checks pass, else 1.
"""

import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INPUTS_DIR = os.path.join(REPO_ROOT, "inputs")
SUBMISSION_PATH = os.path.join(REPO_ROOT, "submission", "recovered_key.json")
PRIVATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "private")
GROUND_TRUTH_PATH = os.path.join(PRIVATE_DIR, "ground_truth.json")

LOCKED_NETLIST_PATH = os.path.join(INPUTS_DIR, "locked_netlist.v")
LOCKING_DESC_PATH = os.path.join(INPUTS_DIR, "locking_description.md")
PRIMARY_IO_PATH = os.path.join(INPUTS_DIR, "primary_io_list.txt")

# Make sure we can import the private grading_lib module.
sys.path.insert(0, PRIVATE_DIR)

results = {}  # requirement_id -> (bool passed, str reason_or_empty)


def record(req_id, passed, reason=""):
    if req_id in results:
        # Should not happen, but guard against double-emission.
        return
    results[req_id] = (passed, reason)
    if passed:
        print("[TEST] PASS: %s" % req_id)
    else:
        print("[TEST] FAIL: %s: %s" % (req_id, reason))


def fail_setup_and_exit(missing_path):
    print("[TEST] FAIL: SETUP: %s not found" % missing_path)
    sys.exit(1)


def read_text_file(path, rel_label):
    if not os.path.isfile(path):
        fail_setup_and_exit(rel_label)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        fail_setup_and_exit(rel_label + " (read error: %s)" % e)


def main():
    # ---------------------------------------------------------------
    # SETUP: verify required input artifacts exist (fixed filenames).
    # ---------------------------------------------------------------
    if not os.path.isfile(LOCKED_NETLIST_PATH):
        fail_setup_and_exit("inputs/locked_netlist.v")
    if not os.path.isfile(LOCKING_DESC_PATH):
        fail_setup_and_exit("inputs/locking_description.md")
    if not os.path.isfile(PRIMARY_IO_PATH):
        fail_setup_and_exit("inputs/primary_io_list.txt")

    netlist_text = read_text_file(LOCKED_NETLIST_PATH, "inputs/locked_netlist.v")
    locking_desc_text = read_text_file(LOCKING_DESC_PATH, "inputs/locking_description.md")
    # primary_io_list.txt is read for completeness/reference; not used in logic.
    _ = read_text_file(PRIMARY_IO_PATH, "inputs/primary_io_list.txt")

    if not os.path.isfile(GROUND_TRUTH_PATH):
        fail_setup_and_exit("evaluation/private/ground_truth.json")
    try:
        with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
            ground_truth = json.load(f)
    except Exception as e:
        fail_setup_and_exit("evaluation/private/ground_truth.json (parse error: %s)" % e)

    try:
        import grading_lib
    except Exception as e:
        print("[TEST] FAIL: SETUP: evaluation/private/grading_lib.py import error: %s" % e)
        sys.exit(1)

    # ---------------------------------------------------------------
    # Parse locked_netlist.v: key port width N and keymux instance count.
    # ---------------------------------------------------------------
    # Match: input [W-1:0] key ;  (or "input wire [W-1:0] key")
    key_width = None
    m = re.search(
        r'input\s+(?:wire\s+|reg\s+|logic\s+)?\[\s*(\d+)\s*:\s*0\s*\]\s*key\b',
        netlist_text,
    )
    if m:
        key_width = int(m.group(1)) + 1
    else:
        # Fallback: try to find "input [0:W-1] key" style variants with different
        # bit ordering just in case.
        m2 = re.search(
            r'input\s+(?:wire\s+|reg\s+|logic\s+)?\[\s*0\s*:\s*(\d+)\s*\]\s*key\b',
            netlist_text,
        )
        if m2:
            key_width = int(m2.group(1)) + 1

    # Count distinct instance names containing 'keymux'.
    # Verilog instance pattern: <module_type> <instance_name> ( ... );
    # We search for identifiers containing 'keymux' that appear as instance
    # names (i.e. preceded by a module/gate type keyword and whitespace, and
    # followed by whitespace then '(').
    keymux_instance_names = set()
    for im in re.finditer(r'([A-Za-z_][A-Za-z0-9_$]*)\s*\(', netlist_text):
        ident = im.group(1)
        if "keymux" in ident:
            keymux_instance_names.add(ident)
    keymux_count = len(keymux_instance_names)

    # Cross-reference locking_description.md's stated count (informational only).
    stated_count = None
    md_match = re.search(r'exactly\s*\*\*(\d+)\*\*', locking_desc_text)
    if md_match:
        try:
            stated_count = int(md_match.group(1))
        except ValueError:
            stated_count = None
    # (stated_count is not authoritative; used only as an informational
    # cross-check and does not itself gate any requirement.)

    # ---------------------------------------------------------------
    # Ground truth fields.
    # ---------------------------------------------------------------
    truth_key_bits = ground_truth.get("key_bits", "")
    truth_key_gates = ground_truth.get("key_gates", [])
    truth_key_width = ground_truth.get("key_width", key_width)

    # Prefer the width parsed from the actual netlist if available; fall back
    # to ground truth's recorded width if netlist parsing somehow failed.
    N = key_width if key_width is not None else truth_key_width

    true_indices = sorted(set(g["key_bit_index"] for g in truth_key_gates))
    truth_pairs = set(
        (g["instance_name"], int(g["key_bit_index"])) for g in truth_key_gates
    )

    # ---------------------------------------------------------------
    # Load submission.
    # ---------------------------------------------------------------
    if not os.path.isfile(SUBMISSION_PATH):
        fail_setup_and_exit("submission/recovered_key.json")

    raw_text = None
    try:
        with open(SUBMISSION_PATH, "r", encoding="utf-8") as f:
            raw_text = f.read()
    except Exception as e:
        fail_setup_and_exit("submission/recovered_key.json (read error: %s)" % e)

    parse_error = None
    submission = None
    try:
        submission = json.loads(raw_text)
    except Exception as e:
        parse_error = str(e)

    # ---------------------------------------------------------------
    # FR1: key_bits is a string of exactly N chars, each '0' or '1'.
    # ---------------------------------------------------------------
    if submission is None:
        record("FR1", False, "recovered_key.json is not valid JSON: %s" % parse_error)
    else:
        key_bits = submission.get("key_bits", None)
        if not isinstance(key_bits, str):
            record("FR1", False, "'key_bits' field missing or not a string")
        elif N is None:
            record("FR1", False, "could not determine key port width N from locked_netlist.v")
        elif len(key_bits) != N:
            record(
                "FR1",
                False,
                "'key_bits' length %d does not match expected N=%d" % (len(key_bits), N),
            )
        elif not re.fullmatch(r'[01]+', key_bits):
            record("FR1", False, "'key_bits' contains non-binary characters")
        else:
            record("FR1", True)

    # ---------------------------------------------------------------
    # FR2: key_gates is a well-formed array of {instance_name, key_bit_index,
    # resolved_value} objects.
    # ---------------------------------------------------------------
    submitted_gate_tuples = None
    if submission is None:
        record("FR2", False, "recovered_key.json is not valid JSON: %s" % parse_error)
    else:
        key_gates = submission.get("key_gates", None)
        if not isinstance(key_gates, list):
            record("FR2", False, "'key_gates' field missing or not a JSON array")
        else:
            try:
                submitted_gate_tuples = grading_lib.parse_key_gates_field(key_gates)
                record("FR2", True)
            except ValueError as e:
                record("FR2", False, str(e))

    # ---------------------------------------------------------------
    # FR3: len(key_gates) == number of keymux instances actually present.
    # ---------------------------------------------------------------
    if submission is None:
        record("FR3", False, "recovered_key.json is not valid JSON: %s" % parse_error)
    else:
        key_gates = submission.get("key_gates", None)
        if not isinstance(key_gates, list):
            record("FR3", False, "'key_gates' field missing or not a JSON array")
        elif keymux_count == 0:
            record("FR3", False, "no keymux instances found in locked_netlist.v (parser error)")
        elif len(key_gates) != keymux_count:
            record(
                "FR3",
                False,
                "submitted key_gates count %d != actual keymux instance count %d in locked_netlist.v"
                % (len(key_gates), keymux_count),
            )
        else:
            record("FR3", True)

    # ---------------------------------------------------------------
    # FR4: strict JSON parse (no trailing commas/comments already implied by
    # json.loads success) + top-level 'notes' field present and is a string.
    # ---------------------------------------------------------------
    if submission is None:
        record("FR4", False, "recovered_key.json is not valid strict JSON: %s" % parse_error)
    else:
        notes = submission.get("notes", None)
        if not isinstance(submission, dict):
            record("FR4", False, "top-level JSON value is not an object")
        elif "notes" not in submission:
            record("FR4", False, "missing top-level 'notes' field")
        elif not isinstance(notes, str):
            record("FR4", False, "'notes' field present but is not a string")
        else:
            record("FR4", True)

    # ---------------------------------------------------------------
    # SR1: F1 over (instance_name, key_bit_index) pairs vs hidden ground
    # truth loci >= 0.9.
    # ---------------------------------------------------------------
    if submission is None or submitted_gate_tuples is None:
        record("SR1", False, "cannot compute key_gate_localization_accuracy: key_gates malformed or JSON invalid")
    else:
        submitted_pairs = set((name, idx) for (name, idx, _val) in submitted_gate_tuples)
        precision, recall, f1 = grading_lib.compute_f1(submitted_pairs, truth_pairs)
        if f1 >= 0.9:
            record("SR1", True)
        else:
            missing = truth_pairs - submitted_pairs
            extra = submitted_pairs - truth_pairs
            record(
                "SR1",
                False,
                "F1=%.3f (<0.9); missing=%d extra=%d pairs vs hidden ground truth"
                % (f1, len(missing), len(extra)),
            )

    # ---------------------------------------------------------------
    # SR2: per-bit match of submitted key_bits vs hidden ground-truth key at
    # true lock indices >= 0.9.
    # ---------------------------------------------------------------
    if submission is None:
        record("SR2", False, "cannot compute key_recovery_rate: recovered_key.json invalid JSON")
    else:
        key_bits = submission.get("key_bits", None)
        if not isinstance(key_bits, str):
            record("SR2", False, "cannot compute key_recovery_rate: 'key_bits' missing or not a string")
        else:
            rate = grading_lib.compute_key_recovery_rate(key_bits, truth_key_bits, true_indices)
            if rate >= 0.9:
                record("SR2", True)
            else:
                mismatched = [
                    i for i in true_indices
                    if i >= len(key_bits) or i >= len(truth_key_bits) or key_bits[i] != truth_key_bits[i]
                ]
                record(
                    "SR2",
                    False,
                    "key_recovery_rate=%.3f (<0.9); mismatched true-lock bit indices=%s"
                    % (rate, mismatched),
                )

    # ---------------------------------------------------------------
    # SR3: self-check that a naive/empty synthetic baseline answer is
    # correctly rejected by the same grading_lib functions used above,
    # using a structural (submission-independent) signal: an empty
    # key_gates array must (a) score F1<0.9 for localization and (b) have
    # a key_gates count that does not equal the actual keymux_count parsed
    # from locked_netlist.v (which must be >0). This holds regardless of
    # what the correct key vector's bit values happen to be for this
    # netlist, so it does not rely on key_recovery_rate as the
    # non-triviality signal.
    # ---------------------------------------------------------------
    try:
        synth_key_gates = []  # empty, like the shipped naive baseline

        synth_pairs = set()  # no gates submitted
        _p, _r, synth_f1 = grading_lib.compute_f1(synth_pairs, truth_pairs)
        synth_count = len(synth_key_gates)

        localization_rejected = synth_f1 < 0.9
        count_mismatch_rejected = (keymux_count > 0) and (synth_count != keymux_count)

        if localization_rejected and count_mismatch_rejected:
            record("SR3", True)
        else:
            record(
                "SR3",
                False,
                "self-check failed: naive baseline scored F1=%.3f (expected <0.9) "
                "and key_gates count %d vs actual keymux_count %d (expected mismatch); "
                "evaluator would incorrectly accept the shipped naive/empty baseline"
                % (synth_f1, synth_count, keymux_count),
            )
    except Exception as e:
        record("SR3", False, "self-check computation raised an error: %s" % e)

    # ---------------------------------------------------------------
    # Final verdict.
    # ---------------------------------------------------------------
    all_passed = all(passed for (passed, _reason) in results.values())
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()