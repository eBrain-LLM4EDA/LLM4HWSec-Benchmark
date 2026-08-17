#!/usr/bin/env python3
"""
evaluation/evaluate.py

Grader for the scalar_mult_ctrl.v conditional-ADD timing-leak analysis task.

This script grades submission/vulnerability_report.json against the
reference RTL under inputs/. It never modifies inputs/ and never grades
RTL code itself; it grades the submitted report's format (FR1-FR4) and
substantive correctness (SR1-SR4), using an independent iverilog
simulation of the reference RTL as a cross-check oracle.
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
SUBMISSION_PATH = os.path.join(REPO_ROOT, "submission", "vulnerability_report.json")

REQUIRED_INPUT_FILES = [
    "scalar_mult_ctrl.v",
    "field_datapath.v",
    "fault_model.md",
    "design_brief.md",
]

TB_PATH = os.path.join(EVAL_DIR, "tb_cycle_count.v")
SCALAR_FILE = os.path.join(EVAL_DIR, "private", "scalar_input.txt")

TIMEOUT_S = 60

results = []  # list of (req_id, bool_pass, reason)


def record(req_id, ok, reason=""):
    if ok:
        print("[TEST] PASS: {}".format(req_id))
    else:
        print("[TEST] FAIL: {}: {}".format(req_id, reason))
    results.append((req_id, ok, reason))


def fail_setup_and_exit(path):
    print("[TEST] FAIL: SETUP: {} not found".format(path))
    sys.exit(1)


def hamming_weight(x):
    return bin(int(x) & 0xFFFF).count("1")


def pearson_corr(xs, ys):
    n = len(xs)
    if n < 2:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = sum((x - mean_x) ** 2 for x in xs)
    den_y = sum((y - mean_y) ** 2 for y in ys)
    if den_x <= 0 or den_y <= 0:
        return 0.0
    return num / ((den_x ** 0.5) * (den_y ** 0.5))


def _find_matching_brace(text, open_idx):
    """
    Given text and the index of an opening '{' at open_idx, scan forward
    respecting string literals and escape sequences to find the index of
    the matching closing '}'. Returns that index, or -1 if not found.
    """
    depth = 0
    i = open_idx
    n = len(text)
    in_string = False
    escape = False
    while i < n:
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def extract_json_object(raw_text):
    """
    Attempt to extract a top-level JSON object from raw_text using several
    increasingly permissive strategies:

      1. Strict json.loads() on the entire content.
      2. Look for a fenced code block (```json ... ``` or ``` ... ```) and
         attempt json.loads() on its inner content.
      3. Brace-matching scan: try every '{' in the text (in order) as a
         candidate start, find its matching outermost '}' (respecting
         string literals/escapes), and attempt json.loads() on that
         substring; return the first one that parses to a dict.

    Returns (parsed_dict_or_None, error_message_or_None).
    """
    # Strategy 1: strict parse of the whole file.
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            return parsed, None
    except Exception:
        pass

    # Strategy 2: fenced code block extraction.
    fence_patterns = [
        r"```json\s*(.*?)```",
        r"```\s*(.*?)```",
    ]
    for pat in fence_patterns:
        for m in re.finditer(pat, raw_text, re.DOTALL | re.IGNORECASE):
            candidate = m.group(1).strip()
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed, None
            except Exception:
                continue

    # Strategy 3: brace-matching scan over every '{' occurrence.
    last_error = None
    idx = 0
    n = len(raw_text)
    while idx < n:
        start = raw_text.find('{', idx)
        if start == -1:
            break
        end = _find_matching_brace(raw_text, start)
        if end == -1:
            # No matching close found starting here; try the next '{'.
            idx = start + 1
            continue
        candidate = raw_text[start:end + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed, None
        except Exception as e:
            last_error = str(e)
        idx = start + 1

    if last_error is not None:
        return None, "no valid top-level JSON object found (last parse error: {})".format(last_error)
    return None, "no top-level JSON object found in file content"


def run_reference_simulation():
    """
    Compile and run evaluation/tb_cycle_count.v against the reference RTL
    under inputs/. Returns (ref_dict_or_None, error_message_or_None), where
    ref_dict maps scalar(int) -> cycle_count(int).
    """
    tmpdir = tempfile.mkdtemp(prefix="sim_")
    sim_bin = os.path.join(tmpdir, "sim.vvp")

    ctrl_path = os.path.join(INPUTS_DIR, "scalar_mult_ctrl.v")
    dp_path = os.path.join(INPUTS_DIR, "field_datapath.v")

    compile_cmd = [
        "iverilog", "-g2012", "-o", sim_bin,
        ctrl_path, dp_path, TB_PATH,
    ]
    try:
        proc = subprocess.run(
            compile_cmd, cwd=REPO_ROOT,
            capture_output=True, text=True, timeout=TIMEOUT_S
        )
    except subprocess.TimeoutExpired:
        return None, "iverilog compile timed out"
    except FileNotFoundError as e:
        return None, "iverilog not found: {}".format(e)

    if proc.returncode != 0:
        return None, "iverilog compile failed: {}".format(
            (proc.stderr or proc.stdout or "").strip()[:800]
        )

    try:
        run_proc = subprocess.run(
            ["vvp", sim_bin], cwd=REPO_ROOT,
            capture_output=True, text=True, timeout=TIMEOUT_S
        )
    except subprocess.TimeoutExpired:
        return None, "vvp simulation timed out"
    except FileNotFoundError as e:
        return None, "vvp not found: {}".format(e)

    if run_proc.returncode != 0 and "DONE_ALL" not in (run_proc.stdout or ""):
        return None, "vvp run crashed: {}".format(
            (run_proc.stderr or run_proc.stdout or "").strip()[:800]
        )

    stdout = run_proc.stdout or ""
    ref = {}
    for line in stdout.splitlines():
        m = re.match(r"^CYCLE_RESULT\s+(\d+)\s+(\d+)\s*$", line.strip())
        if m:
            scalar_val = int(m.group(1))
            cyc_val = int(m.group(2))
            ref[scalar_val] = cyc_val

    if not ref:
        return None, "no CYCLE_RESULT lines produced by reference simulation: {}".format(
            stdout.strip()[:800]
        )

    return ref, None


def main():
    # ---------------------------------------------------------------
    # Setup checks: input artifacts
    # ---------------------------------------------------------------
    for fname in REQUIRED_INPUT_FILES:
        fpath = os.path.join(INPUTS_DIR, fname)
        if not os.path.isfile(fpath):
            fail_setup_and_exit(os.path.join("inputs", fname))

    if not os.path.isfile(TB_PATH):
        fail_setup_and_exit(os.path.relpath(TB_PATH, REPO_ROOT))
    if not os.path.isfile(SCALAR_FILE):
        fail_setup_and_exit(os.path.relpath(SCALAR_FILE, REPO_ROOT))

    if not os.path.isfile(SUBMISSION_PATH):
        fail_setup_and_exit(os.path.relpath(SUBMISSION_PATH, REPO_ROOT))

    # ---------------------------------------------------------------
    # Load submission JSON (robust extraction: strict parse, then fenced
    # code block, then brace-matching scan over the raw text).
    # ---------------------------------------------------------------
    report = None
    parse_error = None
    try:
        with open(SUBMISSION_PATH, "r") as f:
            raw = f.read()
    except Exception as e:
        raw = None
        parse_error = "could not read file: {}".format(e)

    if raw is not None:
        report, extract_err = extract_json_object(raw)
        if report is None:
            parse_error = extract_err

    if parse_error is not None or not isinstance(report, dict):
        reason = "could not parse vulnerability_report.json as a JSON object: {}".format(
            parse_error or "top-level value is not an object"
        )
        record("FR1", False, reason)
        # All other requirements can't be meaningfully evaluated either.
        for rid in ["FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]:
            record(rid, False, "cannot evaluate: vulnerability_report.json failed to parse")
        sys.exit(1)

    # ---------------------------------------------------------------
    # Run independent reference simulation (used by FR2 / SR2)
    # ---------------------------------------------------------------
    ref_table, sim_error = run_reference_simulation()

    # ---------------------------------------------------------------
    # FR1: required fields present & correctly typed
    # ---------------------------------------------------------------
    fr1_ok = True
    fr1_reasons = []

    required_str_fields = [
        "vulnerable_signal",
        "vulnerable_states",
        "timing_dependency_description",
        "remediation_description",
    ]
    for field in required_str_fields:
        val = report.get(field, None)
        if not isinstance(val, str) or len(val.strip()) == 0:
            fr1_ok = False
            fr1_reasons.append("field '{}' missing/empty/non-string".format(field))

    ccbs = report.get("cycle_counts_by_scalar", None)
    parsed_entries = []
    if not isinstance(ccbs, list) or len(ccbs) == 0:
        fr1_ok = False
        fr1_reasons.append("'cycle_counts_by_scalar' missing, empty, or not a list")
    else:
        for idx, entry in enumerate(ccbs):
            if not isinstance(entry, dict):
                fr1_ok = False
                fr1_reasons.append("entry {} in cycle_counts_by_scalar is not an object".format(idx))
                continue
            s = entry.get("scalar", None)
            c = entry.get("cycle_count", None)
            if isinstance(s, bool) or isinstance(c, bool):
                fr1_ok = False
                fr1_reasons.append("entry {} has boolean scalar/cycle_count instead of integer".format(idx))
                continue
            if not isinstance(s, int) or not isinstance(c, int):
                fr1_ok = False
                fr1_reasons.append("entry {} has non-integer scalar/cycle_count".format(idx))
                continue
            parsed_entries.append((s, c))

    record("FR1", fr1_ok, "; ".join(fr1_reasons) if fr1_reasons else "")

    # ---------------------------------------------------------------
    # FR2: coverage of Hamming weights + cross-check vs reference sim
    # ---------------------------------------------------------------
    fr2_ok = True
    fr2_reasons = []

    distinct_scalars = {}
    for s, c in parsed_entries:
        # last write wins if duplicate scalars given
        distinct_scalars[s & 0xFFFF] = c

    if len(distinct_scalars) < 4:
        fr2_ok = False
        fr2_reasons.append(
            "fewer than 4 distinct scalars reported ({})".format(len(distinct_scalars))
        )

    weights = {s: hamming_weight(s) for s in distinct_scalars}
    has_low = any(w <= 2 for w in weights.values())
    has_high = any(w >= 14 for w in weights.values())
    mid_count = sum(1 for w in weights.values() if 3 <= w <= 13)

    if not has_low:
        fr2_ok = False
        fr2_reasons.append("no reported scalar has Hamming weight <= 2")
    if not has_high:
        fr2_ok = False
        fr2_reasons.append("no reported scalar has Hamming weight >= 14")
    if mid_count < 2:
        fr2_ok = False
        fr2_reasons.append(
            "fewer than 2 reported scalars have intermediate Hamming weight (3-13), found {}".format(mid_count)
        )

    if ref_table is None:
        fr2_ok = False
        fr2_reasons.append(
            "reference simulation failed, cannot cross-check cycle counts: {}".format(sim_error)
        )
    else:
        overlap = [s for s in distinct_scalars if s in ref_table]
        if not overlap:
            fr2_ok = False
            fr2_reasons.append(
                "no submitted scalars overlap with the fixed reference scalar set; "
                "cannot cross-check cycle_count values against simulation"
            )
        else:
            TOLERANCE = 1
            mismatches = []
            for s in overlap:
                submitted_cc = distinct_scalars[s]
                ref_cc = ref_table[s]
                if abs(submitted_cc - ref_cc) > TOLERANCE:
                    mismatches.append(
                        "scalar {}: submitted={} ref_sim={}".format(s, submitted_cc, ref_cc)
                    )
            if mismatches:
                fr2_ok = False
                fr2_reasons.append(
                    "cycle_count mismatches vs reference simulation: " + "; ".join(mismatches)
                )

    record("FR2", fr2_ok, "; ".join(fr2_reasons) if fr2_reasons else "")

    # ---------------------------------------------------------------
    # FR3: preserves_correct_output boolean + substantive remediation_rtl_sketch
    # ---------------------------------------------------------------
    fr3_ok = True
    fr3_reasons = []

    pco = report.get("preserves_correct_output", None)
    if not isinstance(pco, bool):
        fr3_ok = False
        fr3_reasons.append("'preserves_correct_output' missing or not boolean")

    rtl_sketch = report.get("remediation_rtl_sketch", None)
    if not isinstance(rtl_sketch, str) or len(rtl_sketch.strip()) < 30:
        fr3_ok = False
        fr3_reasons.append("'remediation_rtl_sketch' missing or too short to be substantive")
    else:
        # Require it to reference some RTL-level concept (not style-specific,
        # just checking it's not a vague placeholder).
        rtl_keywords = [
            "add", "mux", "select", "register", "signal", "state",
            "bit", "always", "assign", "dummy", "discard", "commit",
        ]
        lower_sketch = rtl_sketch.lower()
        if not any(kw in lower_sketch for kw in rtl_keywords):
            fr3_ok = False
            fr3_reasons.append(
                "'remediation_rtl_sketch' does not appear to describe any RTL-level construct"
            )

    record("FR3", fr3_ok, "; ".join(fr3_reasons) if fr3_reasons else "")

    # ---------------------------------------------------------------
    # FR4: cycle_count_range min/max consistency
    # ---------------------------------------------------------------
    fr4_ok = True
    fr4_reasons = []

    ccr = report.get("cycle_count_range", None)
    if not isinstance(ccr, dict):
        fr4_ok = False
        fr4_reasons.append("'cycle_count_range' missing or not an object")
    else:
        rmin = ccr.get("min", None)
        rmax = ccr.get("max", None)
        if isinstance(rmin, bool) or isinstance(rmax, bool) or not isinstance(rmin, int) or not isinstance(rmax, int):
            fr4_ok = False
            fr4_reasons.append("'cycle_count_range.min'/'max' missing or not integers")
        elif not parsed_entries:
            fr4_ok = False
            fr4_reasons.append("cannot verify cycle_count_range: no valid cycle_counts_by_scalar entries")
        else:
            actual_min = min(c for _, c in parsed_entries)
            actual_max = max(c for _, c in parsed_entries)
            if rmin != actual_min or rmax != actual_max:
                fr4_ok = False
                fr4_reasons.append(
                    "cycle_count_range ({}..{}) does not match actual min/max of cycle_counts_by_scalar ({}..{})".format(
                        rmin, rmax, actual_min, actual_max
                    )
                )

    record("FR4", fr4_ok, "; ".join(fr4_reasons) if fr4_reasons else "")

    # ---------------------------------------------------------------
    # SR1: identifies ADD state / scalar_bit conditional as the leak source
    # ---------------------------------------------------------------
    sr1_ok = True
    sr1_reasons = []

    vsig = report.get("vulnerable_signal", "")
    vstates = report.get("vulnerable_states", "")
    tdd = report.get("timing_dependency_description", "")
    combined_text = " ".join([
        vsig if isinstance(vsig, str) else "",
        vstates if isinstance(vstates, str) else "",
        tdd if isinstance(tdd, str) else "",
    ]).lower()

    # Patterns that indicate the ADD-conditional path was correctly identified.
    add_patterns = [
        r"\badd\b",
        r"s_add",
        r"scalar_bit",
        r"cur_bit",
        r"scalar\[bit",
        r"conditional\s+add",
        r"bit\s*==\s*1",
        r"bit\s+is\s+(?:set|1|one)",
        r"skip(?:ped|s|ping)?\s+(?:the\s+)?add",
    ]
    mentions_add_concept = any(re.search(p, combined_text) for p in add_patterns)

    # Check it isn't ONLY talking about DOUBLE or a generic FSM without
    # any ADD-specific mention.
    generic_only_patterns = [
        r"\bdouble\b",
        r"s_double",
        r"\bfsm\b",
        r"state machine",
        r"controller",
    ]
    mentions_generic_only = any(re.search(p, combined_text) for p in generic_only_patterns)

    if not mentions_add_concept:
        sr1_ok = False
        if mentions_generic_only:
            sr1_reasons.append(
                "report references DOUBLE/generic FSM but never identifies the ADD state "
                "or the scalar_bit==1 conditional path as the leak source"
            )
        else:
            sr1_reasons.append(
                "report does not reference the ADD state or the scalar_bit conditional "
                "path anywhere in vulnerable_signal/vulnerable_states/timing_dependency_description"
            )

    record("SR1", sr1_ok, "; ".join(sr1_reasons) if sr1_reasons else "")

    # ---------------------------------------------------------------
    # SR2: Hamming-weight correlation with cycle_count, plus real variation
    #      in the independent reference simulation.
    # ---------------------------------------------------------------
    sr2_ok = True
    sr2_reasons = []

    if len(parsed_entries) < 4:
        sr2_ok = False
        sr2_reasons.append("fewer than 4 cycle_counts_by_scalar entries available to compute correlation")
    else:
        xs = [hamming_weight(s) for s, _ in parsed_entries]
        ys = [c for _, c in parsed_entries]
        if len(set(ys)) == 1:
            sr2_ok = False
            sr2_reasons.append(
                "submitted cycle_count values are constant across all scalars "
                "(no Hamming-weight dependence detected)"
            )
        else:
            corr = pearson_corr(xs, ys)
            if corr < 0.9:
                sr2_ok = False
                sr2_reasons.append(
                    "Pearson correlation between Hamming weight and submitted cycle_count "
                    "is {:.3f}, below required 0.9".format(corr)
                )

    if ref_table is None:
        sr2_ok = False
        sr2_reasons.append(
            "reference simulation failed, cannot confirm real Hamming-weight-dependent "
            "variation: {}".format(sim_error)
        )
    else:
        ref_cycles = list(ref_table.values())
        if len(set(ref_cycles)) <= 1:
            sr2_ok = False
            sr2_reasons.append(
                "independent reference simulation itself shows constant cycle counts "
                "across scalars of differing Hamming weight; leak cannot be substantiated"
            )
        else:
            ref_xs = [hamming_weight(s) for s in ref_table.keys()]
            ref_ys = [ref_table[s] for s in ref_table.keys()]
            ref_corr = pearson_corr(ref_xs, ref_ys)
            if ref_corr < 0.9:
                sr2_ok = False
                sr2_reasons.append(
                    "independent reference simulation shows Hamming-weight/cycle_count "
                    "correlation of {:.3f}, below 0.9 (leak not substantiated by the RTL "
                    "as analyzed)".format(ref_corr)
                )

    record("SR2", sr2_ok, "; ".join(sr2_reasons) if sr2_reasons else "")

    # ---------------------------------------------------------------
    # SR3: remediation must be always-execute-ADD-with-dummy/mux, not just
    #      random delay/jitter/noise/blinding.
    # ---------------------------------------------------------------
    sr3_ok = True
    sr3_reasons = []

    rdesc = report.get("remediation_description", "")
    rsketch = report.get("remediation_rtl_sketch", "")
    remediation_text = " ".join([
        rdesc if isinstance(rdesc, str) else "",
        rsketch if isinstance(rsketch, str) else "",
    ]).lower()

    always_add_patterns = [
        r"always\s+(?:execute|perform|run|do)\s+(?:the\s+)?add",
        r"unconditional(?:ly)?\s+(?:execute|perform|run)?\s*add",
        r"add\s+(?:is\s+)?(?:always|unconditionally)\s+(?:executed|performed)",
        r"add.*every\s+bit",
        r"add.*(?:each|every)\s+(?:cycle|iteration|bit\s*index)",
        r"dummy\s+(?:add|result|register|accumulator)",
        r"discard(?:ed)?\s+(?:add\s+)?result",
        r"scratch\s+(?:reg|register|accumulator)",
    ]
    mux_patterns = [
        r"\bmux\b",
        r"multiplex",
        r"select(?:or)?\s+(?:based\s+on|via|using)\s+(?:scalar_bit|the\s+bit|bit)",
        r"commit(?:ted|s)?\s+(?:the\s+)?(?:real\s+)?(?:add\s+)?result",
        r"choose\s+(?:between|which)\s+(?:result|accumulator)",
    ]

    has_always_add = any(re.search(p, remediation_text) for p in always_add_patterns)
    has_mux = any(re.search(p, remediation_text) for p in mux_patterns)

    inadequate_patterns = [
        r"random\s+delay",
        r"clock\s+jitter",
        r"\bjitter\b",
        r"random\s+noise",
        r"\bnoise\s+injection\b",
        r"blinding",
        r"masking",
    ]
    mentions_inadequate = any(re.search(p, remediation_text) for p in inadequate_patterns)

    if not (has_always_add and has_mux):
        sr3_ok = False
        if mentions_inadequate and not has_always_add:
            sr3_reasons.append(
                "remediation only describes random delay/jitter/noise/blinding/masking "
                "without describing an always-execute-ADD-with-dummy-result/mux fix"
            )
        else:
            sr3_reasons.append(
                "remediation does not clearly describe both (a) always executing ADD "
                "every bit into a dummy/discarded result when the bit is 0, and (b) a "
                "final mux/select mechanism"
            )

    record("SR3", sr3_ok, "; ".join(sr3_reasons) if sr3_reasons else "")

    # ---------------------------------------------------------------
    # SR4: preserves_correct_output == true AND remediation explains the
    #      mux/select mechanism tied to scalar_bit committing real vs dummy.
    # ---------------------------------------------------------------
    sr4_ok = True
    sr4_reasons = []

    if pco is not True:
        sr4_ok = False
        sr4_reasons.append("'preserves_correct_output' is not true")

    commit_patterns = [
        r"(?:commit|select|write|store).{0,60}(?:real|actual|true).{0,30}(?:add\s+)?result",
        r"scalar_bit\s*==?\s*1.{0,80}(?:commit|select|mux|real)",
        r"(?:mux|select).{0,80}scalar_bit",
        r"if\s+(?:the\s+)?bit\s+is\s+1.{0,80}(?:commit|update|real|actual)",
        r"otherwise.{0,60}dummy",
        r"else.{0,60}dumm",
    ]
    has_commit_explanation = any(re.search(p, remediation_text) for p in commit_patterns)

    if not has_commit_explanation:
        sr4_ok = False
        sr4_reasons.append(
            "remediation text does not clearly explain the mux/select mechanism that "
            "commits the real ADD result only when the scalar bit is 1 (vs. a dummy "
            "result otherwise), so correctness preservation is not substantiated"
        )

    record("SR4", sr4_ok, "; ".join(sr4_reasons) if sr4_reasons else "")

    # ---------------------------------------------------------------
    # Final verdict
    # ---------------------------------------------------------------
    all_pass = all(ok for _, ok, _ in results)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()