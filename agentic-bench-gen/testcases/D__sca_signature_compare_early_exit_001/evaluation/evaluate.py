#!/usr/bin/env python3
"""
evaluate.py - Grader for sca_signature_compare_early_exit_001

Grades submission/vulnerability_report.json against ground truth obtained
by simulating the fixed baseline RTL (inputs/signature_compare.v) with a
reference testbench (evaluation/tb_reference.v) via iverilog/vvp.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SUBMISSION_PATH = os.path.join(REPO_ROOT, "submission", "vulnerability_report.json")
SIG_COMPARE_PATH = os.path.join(REPO_ROOT, "inputs", "signature_compare.v")
TB_HARNESS_PATH = os.path.join(REPO_ROOT, "inputs", "testbench_harness.v")
TB_REFERENCE_PATH = os.path.join(REPO_ROOT, "evaluation", "tb_reference.v")

results = []  # list of (id, passed_bool, reason)


def record(req_id, passed, reason=""):
    if passed:
        print("[TEST] PASS: %s" % req_id)
    else:
        print("[TEST] FAIL: %s: %s" % (req_id, reason))
    results.append((req_id, passed, reason))


def fail_setup(path_desc):
    print("[TEST] FAIL: SETUP: %s not found" % path_desc)
    sys.exit(1)


def run_reference_sim():
    """Compile and run the reference testbench against the fixed baseline
    RTL under test. Returns a dict: label -> {"cycles": int, "match": int}
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        sim_path = os.path.join(tmpdir, "sim.vvp")
        compile_cmd = [
            "iverilog", "-g2012", "-o", sim_path,
            SIG_COMPARE_PATH, TB_REFERENCE_PATH,
        ]
        try:
            proc = subprocess.run(
                compile_cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=30
            )
        except subprocess.TimeoutExpired:
            print("[TEST] FAIL: SETUP: iverilog compile timed out")
            sys.exit(1)
        if proc.returncode != 0:
            print("[TEST] FAIL: SETUP: iverilog compile failed: %s" % (proc.stderr.strip()[:500]))
            sys.exit(1)

        try:
            run_proc = subprocess.run(
                ["vvp", sim_path], cwd=REPO_ROOT, capture_output=True, text=True, timeout=30
            )
        except subprocess.TimeoutExpired:
            print("[TEST] FAIL: SETUP: vvp simulation timed out")
            sys.exit(1)

        output = run_proc.stdout

    cases = {}
    # Lines look like: "CASE full_match CYCLES=18 MATCH=1"
    pattern = re.compile(r'CASE\s+(\S+)\s+CYCLES=(\d+)\s+MATCH=(\d+)')
    for m in pattern.finditer(output):
        label = m.group(1)
        cycles = int(m.group(2))
        match_val = int(m.group(3))
        cases[label] = {"cycles": cycles, "match": match_val}

    if not cases:
        print("[TEST] FAIL: SETUP: could not parse reference simulation output")
        print("---- vvp stdout ----")
        print(output)
        sys.exit(1)

    return cases


def get_measured(cases, mismatch_pos):
    """mismatch_pos: -1 for full match, else 0..15"""
    if mismatch_pos == -1:
        label = "full_match"
    else:
        label = "mismatch_pos_%d" % mismatch_pos
    if label not in cases:
        return None
    return cases[label]


def try_parse_linear_formula(text):
    """Attempt to extract a linear relationship cycles = slope*k + intercept
    from free text, using regex only (no eval on arbitrary text).

    Supports patterns like:
      "k + 2", "mismatch_index + 2", "position + 2", "k+2"
      "2*k + 1", "k*1 + 2"
    Returns (slope, intercept) or None if it cannot find a confident match.
    """
    if not isinstance(text, str):
        return None

    t = text.lower()

    # Normalize common variable names to a single token 'k'
    var_names = [
        "mismatch_index", "mismatch_position", "first_mismatch",
        "byte_position", "position", "index", "k"
    ]
    # Replace longest names first to avoid partial clobbering
    for name in sorted(var_names, key=len, reverse=True):
        t = re.sub(r'\b' + re.escape(name) + r'\b', 'k', t)

    # Look for patterns of the form: k <op> N  or  N <op> k
    # slope*k + intercept, allow optional explicit multiplier like "1*k" or "k*1"
    candidates = []

    # Pattern: (coef)*k +/- intercept   e.g. "k + 2", "1*k + 2", "k*1+2"
    m = re.search(
        r'(\d+)?\s*\*?\s*\bk\b\s*\*?\s*(\d+)?\s*([+\-])\s*(\d+)',
        t
    )
    if m:
        coef1 = m.group(1)
        coef2 = m.group(2)
        sign = m.group(3)
        intercept_str = m.group(4)
        slope = 1
        if coef1:
            slope = int(coef1)
        elif coef2:
            slope = int(coef2)
        intercept = int(intercept_str)
        if sign == "-":
            intercept = -intercept
        candidates.append((slope, intercept))

    # Pattern: N + k  (intercept first)
    m2 = re.search(r'(\d+)\s*([+\-])\s*\bk\b', t)
    if m2:
        intercept_str = m2.group(1)
        sign = m2.group(2)
        intercept = int(intercept_str)
        # "N - k" would mean slope = -1; "N + k" means slope = 1
        slope = 1 if sign == "+" else -1
        candidates.append((slope, intercept))

    if not candidates:
        return None

    # Prefer the first found candidate
    return candidates[0]


def check_fr1(report, cases):
    req_id = "FR1"
    measured = get_measured(cases, -1)
    if measured is None:
        record(req_id, False, "could not obtain measured full-match verdict from reference sim")
        return
    expected_verdict = "match" if measured["match"] == 1 else "mismatch"

    bb = report.get("baseline_behavior")
    if not isinstance(bb, dict):
        record(req_id, False, "baseline_behavior missing or not an object")
        return
    val = bb.get("full_match_verdict")
    if not isinstance(val, str) or not val.strip():
        record(req_id, False, "baseline_behavior.full_match_verdict missing or empty")
        return
    if val.strip().lower() != expected_verdict:
        record(req_id, False, "full_match_verdict='%s' does not match measured '%s'" % (val, expected_verdict))
        return
    record(req_id, True)


def check_fr2(report, cases):
    req_id = "FR2"
    measured = get_measured(cases, 0)
    if measured is None:
        record(req_id, False, "could not obtain measured mismatch-at-0 verdict from reference sim")
        return
    expected_verdict = "match" if measured["match"] == 1 else "mismatch"

    bb = report.get("baseline_behavior")
    if not isinstance(bb, dict):
        record(req_id, False, "baseline_behavior missing or not an object")
        return
    val = bb.get("mismatch_at_zero_verdict")
    if not isinstance(val, str) or not val.strip():
        record(req_id, False, "baseline_behavior.mismatch_at_zero_verdict missing or empty")
        return
    if val.strip().lower() != expected_verdict:
        record(req_id, False, "mismatch_at_zero_verdict='%s' does not match measured '%s'" % (val, expected_verdict))
        return
    record(req_id, True)


def check_fr3(report):
    req_id = "FR3"
    problems = []

    for key in ["early_exit_signal", "cycle_relationship", "constant_time_fix"]:
        val = report.get(key)
        if not isinstance(val, str) or not val.strip():
            problems.append("'%s' missing/empty/non-string" % key)

    bb = report.get("baseline_behavior")
    if not isinstance(bb, dict):
        problems.append("'baseline_behavior' missing or not an object")
    else:
        for sub in ["full_match_verdict", "mismatch_at_zero_verdict"]:
            val = bb.get(sub)
            if not isinstance(val, str) or not val.strip():
                problems.append("'baseline_behavior.%s' missing/empty/non-string" % sub)

    if "proposed_fix_preserves_correctness" not in report:
        problems.append("'proposed_fix_preserves_correctness' missing")
    elif not isinstance(report.get("proposed_fix_preserves_correctness"), bool):
        problems.append("'proposed_fix_preserves_correctness' not boolean")

    if problems:
        record(req_id, False, "; ".join(problems))
        return
    record(req_id, True)


def check_fr4(report):
    req_id = "FR4"
    if "proposed_fix_preserves_correctness" not in report:
        record(req_id, False, "'proposed_fix_preserves_correctness' field missing")
        return
    val = report.get("proposed_fix_preserves_correctness")
    if not isinstance(val, bool):
        record(req_id, False, "'proposed_fix_preserves_correctness' is not a boolean")
        return
    if val is not True:
        record(req_id, False, "'proposed_fix_preserves_correctness' is False; a valid fix must preserve correctness")
        return
    record(req_id, True)


def extract_signal_names(sig_source):
    """Extract candidate reg/wire identifiers declared in the RTL source."""
    names = set()
    for m in re.finditer(r'\b(?:reg|wire)\s+(?:\[[^\]]+\]\s+)?(\w+)\s*[;,=]', sig_source):
        names.add(m.group(1))
    return names


def check_sr1(report, sig_source):
    req_id = "SR1"
    val = report.get("early_exit_signal")
    if not isinstance(val, str) or not val.strip():
        record(req_id, False, "'early_exit_signal' missing or empty")
        return

    text = val.lower()

    # Direct identifier match against declared signals in the RTL relevant to
    # the early-exit branch.
    declared_names = extract_signal_names(sig_source)
    relevant_identifiers = {
        n for n in declared_names
        if n.lower() in ("mismatch_found", "done", "running")
    }

    matched_identifier = any(name.lower() in text for name in relevant_identifiers)

    # Also accept a clear functional/semantic description of the same net:
    # referencing the comparison of expected_byte/received_byte causing an
    # early assertion of done before all bytes are consumed.
    semantic_patterns = [
        r'expected_byte\s*!=\s*received_byte',
        r'expected.*(?:!=|differ|mismatch).*received',
        r'first\s+mismatch(?:ing)?\s+byte',
        r'mismatch[_\s]*found',
        r'early[-_\s]*(?:exit|terminat|assert(?:ion)?\s+of\s+done)',
    ]
    matched_semantic = any(re.search(p, text) for p in semantic_patterns)

    if not (matched_identifier or matched_semantic):
        record(req_id, False,
               "early_exit_signal '%s' does not identify the mismatch-triggered early-termination "
               "logic (expected reference to e.g. 'mismatch_found' or the expected_byte != received_byte "
               "condition causing early done assertion)" % val)
        return

    record(req_id, True)


def check_sr2(report, cases):
    req_id = "SR2"
    text = report.get("cycle_relationship")
    if not isinstance(text, str) or not text.strip():
        record(req_id, False, "'cycle_relationship' missing or empty")
        return

    parsed = try_parse_linear_formula(text)
    if parsed is None:
        record(req_id, False,
               "could not parse a linear cycle-count formula (slope*k + intercept) from "
               "'cycle_relationship' text: %r" % text)
        return

    slope, intercept = parsed

    mismatches = []
    for k in range(16):
        measured = get_measured(cases, k)
        if measured is None:
            mismatches.append("k=%d: no measured data" % k)
            continue
        predicted = slope * k + intercept
        if abs(predicted - measured["cycles"]) > 1:
            mismatches.append(
                "k=%d predicted=%d measured=%d" % (k, predicted, measured["cycles"])
            )

    # Full-match case: try to detect an explicit override in the text (e.g.
    # "full match takes 18 cycles"); otherwise fall back to evaluating the
    # formula at k=16 (one past the last mismatch position), which is the
    # natural extension of "k = position of first mismatch" reasoning used
    # in the ground truth (full match behaves like a mismatch that would
    # occur at position 16).
    full_measured = get_measured(cases, -1)
    if full_measured is not None:
        full_match_override = None
        fm = re.search(r'full[\s_-]*match[^0-9]{0,40}?(\d+)\s*cycle', text.lower())
        if fm:
            full_match_override = int(fm.group(1))

        if full_match_override is not None:
            predicted_full = full_match_override
        else:
            predicted_full = slope * 16 + intercept

        if abs(predicted_full - full_measured["cycles"]) > 1:
            mismatches.append(
                "full_match predicted=%d measured=%d" % (predicted_full, full_measured["cycles"])
            )

    if mismatches:
        record(req_id, False,
               "cycle_relationship formula (slope=%d, intercept=%d) fails to predict measured "
               "cycle counts within +/-1 for: %s" % (slope, intercept, "; ".join(mismatches)))
        return

    record(req_id, True)


def check_sr3(report):
    req_id = "SR3"
    text = report.get("constant_time_fix")
    if not isinstance(text, str) or not text.strip():
        record(req_id, False, "'constant_time_fix' missing or empty")
        return

    t = text.lower()

    element_a_patterns = [
        r'remove\w*\s+(?:the\s+)?early[-_\s]*(?:exit|terminat|return)',
        r'no\s+early[-_\s]*(?:exit|terminat)',
        r'eliminat\w*\s+(?:the\s+)?early[-_\s]*(?:exit|terminat)',
        r'without\s+early[-_\s]*(?:exit|terminat)',
        r'do\s+not\s+(?:exit|terminate|return)\s+early',
        r'never\s+(?:exit|terminate)\s+early',
    ]
    element_b_patterns = [
        r'all\s+16\s+bytes?',
        r'full\s+(?:16[-\s]?byte\s+)?scan',
        r'unconditionally\s+consum\w*',
        r'consum\w*\s+(?:all\s+)?(?:16\s+)?bytes?\s+(?:unconditionally|regardless)',
        r'every\s+byte.*regardless',
        r'scan\s+(?:the\s+)?entire\s+signature',
    ]
    element_c_patterns = [
        r'sticky',
        r'accumulat\w*\s+(?:mismatch|flag)',
        r'latch\w*\s+mismatch',
        r'or[-\s]?ed?\s+each\s+cycle',
        r'bitwise\s+or',
        r'persistent\s+(?:mismatch\s+)?flag',
        r'mismatch\s+flag.*(?:accumulat|latch|sticky|persist)',
    ]

    matched_a = any(re.search(p, t) for p in element_a_patterns)
    matched_b = any(re.search(p, t) for p in element_b_patterns)
    matched_c = any(re.search(p, t) for p in element_c_patterns)

    missing = []
    if not matched_a:
        missing.append("no early-exit removal")
    if not matched_b:
        missing.append("unconditional full 16-byte scan")
    if not matched_c:
        missing.append("sticky/accumulated mismatch flag")

    if missing:
        record(req_id, False,
               "constant_time_fix is missing required remediation element(s): %s (text=%r)" %
               (", ".join(missing), text))
        return

    record(req_id, True)


def check_sr4(report, cases):
    req_id = "SR4"

    false_claim_patterns = [
        r'already\s+constant[-\s]*time',
        r'no\s+timing\s+leak',
        r'not\s+(?:data[-\s]*dependent|vulnerable)',
        r'baseline\s+is\s+(?:already\s+)?secure',
        r'design\s+is\s+(?:already\s+)?constant[-\s]*time',
    ]

    fields_to_scan = []
    for key in ["cycle_relationship", "constant_time_fix", "early_exit_signal"]:
        val = report.get(key)
        if isinstance(val, str):
            fields_to_scan.append(val.lower())

    combined_text = " ".join(fields_to_scan)

    for p in false_claim_patterns:
        if re.search(p, combined_text):
            record(req_id, False,
                   "report falsely claims baseline design is already constant-time / has no leakage "
                   "(matched pattern %r)" % p)
            return

    # Also check: if cycle_relationship parses as a pure constant (slope==0)
    # while measured data actually varies with k, that's an implicit false
    # claim of constant-time baseline behavior.
    text = report.get("cycle_relationship")
    parsed = try_parse_linear_formula(text) if isinstance(text, str) else None

    # Determine whether measured cycles actually vary across k
    measured_cycles = []
    for k in range(16):
        m = get_measured(cases, k)
        if m is not None:
            measured_cycles.append(m["cycles"])
    varies = len(set(measured_cycles)) > 1

    if parsed is not None:
        slope, _ = parsed
        if slope == 0 and varies:
            record(req_id, False,
                   "cycle_relationship describes a constant (slope=0) cycle count, contradicting "
                   "measured cycle counts that vary with mismatch position")
            return
    else:
        # Could not parse a linear formula at all; check for an explicit
        # single-number-only claim like "always takes 18 cycles" with no
        # k-dependence language, which would also be a false claim if data varies.
        if isinstance(text, str):
            only_constant = re.fullmatch(r'[^0-9]{0,60}\d+\s*cycles?[^0-9]{0,60}', text.strip().lower())
            if only_constant and varies:
                record(req_id, False,
                       "cycle_relationship claims a single fixed cycle count with no data-dependence, "
                       "contradicting measured cycle counts that vary with mismatch position")
                return

    record(req_id, True)


def main():
    if not os.path.isfile(SIG_COMPARE_PATH):
        fail_setup("inputs/signature_compare.v")
    if not os.path.isfile(TB_HARNESS_PATH):
        fail_setup("inputs/testbench_harness.v")
    if not os.path.isfile(TB_REFERENCE_PATH):
        fail_setup("evaluation/tb_reference.v")

    if not os.path.isfile(SUBMISSION_PATH):
        fail_setup("submission/vulnerability_report.json")

    with open(SIG_COMPARE_PATH, "r") as f:
        sig_source = f.read()

    try:
        with open(SUBMISSION_PATH, "r") as f:
            report = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print("[TEST] FAIL: SETUP: submission/vulnerability_report.json is not valid JSON: %s" % e)
        sys.exit(1)

    if not isinstance(report, dict):
        print("[TEST] FAIL: SETUP: submission/vulnerability_report.json does not contain a JSON object")
        sys.exit(1)

    cases = run_reference_sim()

    check_fr1(report, cases)
    check_fr2(report, cases)
    check_fr3(report)
    check_fr4(report)

    check_sr1(report, sig_source)
    check_sr2(report, cases)
    check_sr3(report)
    check_sr4(report, cases)

    all_passed = all(passed for (_id, passed, _reason) in results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()