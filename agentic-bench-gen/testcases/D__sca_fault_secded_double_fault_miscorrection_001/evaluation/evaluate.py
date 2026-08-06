#!/usr/bin/env python3
"""
evaluate.py -- grader for sca_fault_secded_double_fault_miscorrection_001

Grades submission/vulnerability_report.json against ground truth derived
purely from simulating inputs/secded_codec.v with evaluation/oracle_tb.v
via iverilog/vvp. No fault outcomes are hardcoded here.
"""

import codecs
import json
import os
import re
import subprocess
import sys
import tempfile

REQ_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]

RESULTS = {}


def emit_pass(req_id):
    RESULTS[req_id] = ("PASS", "")
    print("[TEST] PASS: %s" % req_id)


def emit_fail(req_id, reason):
    RESULTS[req_id] = ("FAIL", reason)
    print("[TEST] FAIL: %s: %s" % (req_id, reason))


def fail_setup(reason):
    print("[TEST] FAIL: SETUP: %s" % reason)
    sys.exit(1)


INPUTS = {
    "codec": "inputs/secded_codec.v",
    "fault_model": "inputs/fault_model.json",
    "fault_tb": "inputs/fault_enum_tb.v",
    "brief": "inputs/design_brief.md",
}

ORACLE_TB = "evaluation/oracle_tb.v"
SUBMISSION_PATH = "submission/vulnerability_report.json"


def check_inputs_exist():
    for key, path in INPUTS.items():
        if not os.path.isfile(path):
            fail_setup("%s not found" % path)
    if not os.path.isfile(ORACLE_TB):
        fail_setup("%s not found (evaluation harness missing)" % ORACLE_TB)


def _extract_fenced_json_blocks(text):
    """Return a list of candidate JSON substrings extracted from fenced
    code blocks in a Markdown document, e.g. ```json ... ``` or ``` ... ```.
    Ordered by appearance in the document."""
    candidates = []
    fence_pattern = re.compile(r'```(?:json)?\s*(.*?)```', re.DOTALL | re.IGNORECASE)
    for m in fence_pattern.finditer(text):
        candidates.append(m.group(1))
    return candidates


def _extract_balanced_json(text, start_idx):
    """Given text and an index pointing at '{' or '[', return the balanced
    substring from start_idx to its matching close, honoring JSON string
    escaping, or None if unbalanced."""
    open_ch = text[start_idx]
    if open_ch == "{":
        close_ch = "}"
    elif open_ch == "[":
        close_ch = "]"
    else:
        return None

    depth = 0
    in_string = False
    escape = False
    i = start_idx
    n = len(text)
    while i < n:
        c = text[i]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
        else:
            if c == '"':
                in_string = True
            elif c == open_ch:
                depth += 1
            elif c == close_ch:
                depth -= 1
                if depth == 0:
                    return text[start_idx:i + 1]
        i += 1
    return None


def _candidate_looks_like_fault_list(parsed):
    """Return True if parsed JSON plausibly contains a fault list (a list
    directly, or a dict with a recognizable fault-list key)."""
    if isinstance(parsed, list) and len(parsed) > 0:
        return True
    if isinstance(parsed, dict):
        for key in ("faults", "fault_cases", "cases"):
            if key in parsed and isinstance(parsed[key], list) and len(parsed[key]) > 0:
                return True
    return False


def load_fault_model():
    try:
        with open(INPUTS["fault_model"], "r") as f:
            raw_text = f.read()
    except Exception as e:
        fail_setup("failed to read inputs/fault_model.json: %s" % e)
        return None

    data = None
    parse_errors = []

    # Step 1: try the whole file as raw JSON first.
    try:
        parsed = json.loads(raw_text.strip())
        if _candidate_looks_like_fault_list(parsed):
            data = parsed
    except Exception as e:
        parse_errors.append("raw json.loads: %s" % e)

    # Step 2: if that failed (the shipped fault_model.json is a Markdown
    # document with prose followed by a fenced ```json ... ``` block
    # containing the actual payload), extract candidate JSON from fenced
    # code blocks and try each in order of appearance.
    if data is None:
        for candidate in _extract_fenced_json_blocks(raw_text):
            candidate_stripped = candidate.strip()
            if not candidate_stripped:
                continue
            try:
                parsed = json.loads(candidate_stripped)
            except Exception as e:
                parse_errors.append("fenced block json.loads: %s" % e)
                continue
            if _candidate_looks_like_fault_list(parsed):
                data = parsed
                break

    # Step 3: last-resort fallback -- scan for the first balanced top-level
    # JSON object/array anywhere in the text that plausibly contains a
    # fault list. This handles any other minor formatting variation
    # without depending on a specific document shape.
    if data is None:
        checked = 0
        for start_idx, ch in enumerate(raw_text):
            if ch not in "{[":
                continue
            substr = _extract_balanced_json(raw_text, start_idx)
            if substr is None:
                continue
            checked += 1
            try:
                parsed = json.loads(substr)
            except Exception as e:
                parse_errors.append("balanced-scan json.loads: %s" % e)
                continue
            if _candidate_looks_like_fault_list(parsed):
                data = parsed
                break
            if checked > 100:
                break

    if data is None:
        detail = parse_errors[0] if parse_errors else "no JSON payload found"
        fail_setup("failed to parse inputs/fault_model.json: %s" % detail)
        return None

    faults = None
    if isinstance(data, list):
        faults = data
    elif isinstance(data, dict):
        for key in ("faults", "fault_cases", "cases"):
            if key in data and isinstance(data[key], list):
                faults = data[key]
                break
    if faults is None:
        fail_setup("inputs/fault_model.json has no recognizable fault list")
        return None

    normalized = []
    for entry in faults:
        if not isinstance(entry, dict):
            continue
        fid = entry.get("fault_id")
        bpos = entry.get("bit_positions")
        if fid is None or bpos is None:
            continue
        try:
            positions = tuple(sorted(int(x) for x in bpos))
        except Exception:
            continue
        normalized.append({
            "fault_id": fid,
            "bit_positions": positions,
        })
    if len(normalized) == 0:
        fail_setup("inputs/fault_model.json parsed but contained no usable fault entries")
    return normalized


def run_oracle_simulation():
    """Compile and run the oracle testbench against inputs/secded_codec.v.
    Returns (ref_data_str, list_of_case_dicts) where each case dict has:
      bit_positions (tuple of ints, sorted), syndrome (int), ope (int),
      correctable (int), uncorrectable (int), correction_mask (str),
      data_out (str, 8-bit binary)
    Case order corresponds to enumeration order printed by oracle_tb.v.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        sim_path = os.path.join(tmpdir, "sim.vvp")
        compile_cmd = ["iverilog", "-g2012", "-o", sim_path, INPUTS["codec"], ORACLE_TB]
        try:
            proc = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=60)
        except Exception as e:
            fail_setup("iverilog invocation failed: %s" % e)
            return None, None
        if proc.returncode != 0:
            fail_setup("iverilog compile failed: %s" % (proc.stderr.strip()[:800]))
            return None, None

        run_cmd = ["vvp", sim_path]
        try:
            proc = subprocess.run(run_cmd, capture_output=True, text=True, timeout=60)
        except Exception as e:
            fail_setup("vvp invocation failed: %s" % e)
            return None, None
        if proc.returncode != 0:
            fail_setup("vvp run failed: %s" % (proc.stderr.strip()[:800] or proc.stdout.strip()[:800]))
            return None, None

        stdout = proc.stdout

    ref_match = re.search(r'REFDATA\s+([01]{8})', stdout)
    if not ref_match:
        fail_setup("oracle_tb.v output did not contain a REFDATA line")
        return None, None
    ref_data = ref_match.group(1)

    # POS field may contain a single int (single-bit faults) or a
    # comma-separated pair (two-bit faults); allow both by matching one or
    # more digit groups separated by commas, no surrounding whitespace.
    case_re = re.compile(
        r'FAULTID\s+(\S+)\s+POS\s+([0-9]+(?:,[0-9]+)*)\s+SYN\s+([01]{4})\s+OPE\s+([01])\s+'
        r'CORR\s+([01])\s+UNCORR\s+([01])\s+MASK\s+([01]{13})\s+DOUT\s+([01]{8})'
    )
    cases = []
    for m in case_re.finditer(stdout):
        fid, pos_str, syn, ope, corr, uncorr, mask, dout = m.groups()
        positions = tuple(sorted(int(p) for p in pos_str.split(",") if p != ""))
        cases.append({
            "fault_id": fid,
            "bit_positions": positions,
            "syndrome": int(syn, 2),
            "ope": int(ope),
            "correctable": int(corr),
            "uncorrectable": int(uncorr),
            "correction_mask": mask,
            "data_out": dout,
        })

    if len(cases) == 0:
        fail_setup("oracle_tb.v produced no parseable FAULTID lines")
        return None, None

    return ref_data, cases


def build_oracle_map(fault_model_entries, oracle_cases):
    """Cross-reference oracle simulation cases with fault_model.json entries
    by bit_positions (primary key; both sides are normalized to sorted
    tuples of ints so ordering/whitespace differences cannot cause a
    mismatch), falling back to fault_id if needed.
    Returns dict: fault_id (from fault_model.json) -> oracle case dict.
    """
    by_positions = {}
    for c in oracle_cases:
        key = tuple(sorted(int(x) for x in c["bit_positions"]))
        by_positions.setdefault(key, c)

    by_fault_id_oracle = {}
    for c in oracle_cases:
        by_fault_id_oracle.setdefault(c["fault_id"], c)

    oracle_map = {}
    unresolved = []
    for entry in fault_model_entries:
        fid = entry["fault_id"]
        bpos = tuple(sorted(int(x) for x in entry["bit_positions"]))
        case = by_positions.get(bpos)
        if case is None:
            case = by_fault_id_oracle.get(fid)
        if case is None:
            unresolved.append(fid)
            continue
        oracle_map[fid] = case

    if unresolved:
        fail_setup(
            "could not resolve oracle simulation results for %d fault_model.json entries "
            "(examples: %s)" % (len(unresolved), unresolved[:5])
        )
        return None

    return oracle_map


def load_submission():
    """Load submission/vulnerability_report.json.

    Returns one of:
      - ("MISSING", reason)      -> caller must fail_setup and exit.
      - ("PARSE_ERROR", reason)  -> caller must FAIL:FR1 (not SETUP/crash).
      - parsed JSON value (dict/list/etc.) on success.
    """
    if not os.path.isfile(SUBMISSION_PATH):
        return ("MISSING", "%s not found" % SUBMISSION_PATH)
    try:
        # utf-8-sig transparently strips a leading BOM if present, and
        # behaves identically to plain utf-8 decoding when no BOM exists.
        with open(SUBMISSION_PATH, "r", encoding="utf-8-sig") as f:
            raw_text = f.read()
    except Exception as e:
        return ("MISSING", "failed to read %s: %s" % (SUBMISSION_PATH, e))

    try:
        data = json.loads(raw_text)
    except Exception as e:
        return ("PARSE_ERROR", str(e))
    return data


ALLOWED_CLASSIFICATIONS = {"no_error", "corrected", "detected_uncorrectable"}
REQUIRED_OBS_KEYS = {"syndrome", "overall_parity_error", "correctable",
                     "uncorrectable", "correction_mask", "data_out"}


def normalize_bits(value, width):
    """Normalize a value (str or int) representing a bit vector into a
    canonical binary string of the given width. Returns None if not
    interpretable."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        v = value
        if v < 0:
            return None
        s = bin(v)[2:]
        if len(s) > width:
            return None
        return s.zfill(width)
    if isinstance(value, str):
        s = value.strip()
        if s.lower().startswith("0x"):
            try:
                v = int(s, 16)
            except ValueError:
                return None
            s2 = bin(v)[2:]
            if len(s2) > width:
                return None
            return s2.zfill(width)
        if s.lower().startswith("0b"):
            s = s[2:]
        if re.fullmatch(r'[01]+', s):
            if len(s) > width:
                return None
            return s.zfill(width)
        if re.fullmatch(r'\d+', s):
            try:
                v = int(s)
            except ValueError:
                return None
            s2 = bin(v)[2:]
            if len(s2) > width:
                return None
            return s2.zfill(width)
    return None


def normalize_bit_scalar(value):
    """Normalize a single-bit field (0/1, '0'/'1', True/False) into an int
    0 or 1, or None if invalid."""
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        if value in (0, 1):
            return value
        return None
    if isinstance(value, str):
        s = value.strip()
        if s in ("0", "1"):
            return int(s)
    return None


def validate_fr1(submission):
    """Returns (ok, reason, fault_cases_list_or_None, summary_obj_or_None)"""
    if isinstance(submission, tuple) and submission and submission[0] == "PARSE_ERROR":
        return False, "submission is not valid JSON: %s" % submission[1], None, None

    if not isinstance(submission, dict):
        return False, "top-level submission is not a JSON object", None, None

    if "fault_cases" not in submission or "summary" not in submission:
        return False, "missing required top-level key(s) 'fault_cases' and/or 'summary'", None, None

    fault_cases = submission["fault_cases"]
    summary = submission["summary"]

    if not isinstance(fault_cases, list):
        return False, "'fault_cases' is not an array", None, None
    if not isinstance(summary, dict):
        return False, "'summary' is not an object", None, None

    for idx, case in enumerate(fault_cases):
        if not isinstance(case, dict):
            return False, "fault_cases[%d] is not an object" % idx, None, None
        for key in ("fault_id", "bit_positions", "classification", "observed_outputs"):
            if key not in case:
                return False, "fault_cases[%d] missing key '%s'" % (idx, key), None, None
        if not isinstance(case["fault_id"], str):
            return False, "fault_cases[%d].fault_id is not a string" % idx, None, None
        if not isinstance(case["bit_positions"], list):
            return False, "fault_cases[%d].bit_positions is not an array" % idx, None, None
        for bp in case["bit_positions"]:
            if not isinstance(bp, int):
                return False, "fault_cases[%d].bit_positions contains non-int element" % idx, None, None
        if case["classification"] not in ALLOWED_CLASSIFICATIONS:
            return False, ("fault_cases[%d].classification '%s' not in allowed enum" %
                            (idx, case["classification"])), None, None
        obs = case["observed_outputs"]
        if not isinstance(obs, dict):
            return False, "fault_cases[%d].observed_outputs is not an object" % idx, None, None
        missing_obs = REQUIRED_OBS_KEYS - set(obs.keys())
        if missing_obs:
            return False, ("fault_cases[%d].observed_outputs missing key(s): %s" %
                            (idx, sorted(missing_obs))), None, None

    return True, "", fault_cases, summary


def check_fr2(fault_cases, fault_model_entries):
    model_ids = set(e["fault_id"] for e in fault_model_entries)
    sub_ids_list = [c["fault_id"] for c in fault_cases]
    sub_ids_set = set(sub_ids_list)

    if len(sub_ids_list) != len(sub_ids_set):
        dupes = sorted(set(x for x in sub_ids_list if sub_ids_list.count(x) > 1))
        emit_fail("FR2", "duplicate fault_id entries found: %s" % dupes[:5])
        return False

    missing = model_ids - sub_ids_set
    extra = sub_ids_set - model_ids
    if missing or extra:
        emit_fail("FR2", "fault_id set mismatch vs fault_model.json (missing=%d, extra=%d); examples missing=%s extra=%s" %
                   (len(missing), len(extra), sorted(missing)[:5], sorted(extra)[:5]))
        return False

    emit_pass("FR2")
    return True


def check_fr3(fault_cases, oracle_map, ref_data, fault_model_entries):
    single_bit_ids = set(e["fault_id"] for e in fault_model_entries if len(e["bit_positions"]) == 1)
    if len(single_bit_ids) == 0:
        emit_fail("FR3", "could not determine single-bit fault_id set from fault_model.json")
        return False

    by_id = {c["fault_id"]: c for c in fault_cases}
    bad = []
    for fid in single_bit_ids:
        case = by_id.get(fid)
        if case is None:
            bad.append("%s: missing from submission" % fid)
            continue
        if case["classification"] != "corrected":
            bad.append("%s: classification='%s' (expected 'corrected')" % (fid, case["classification"]))
            continue
        dout_norm = normalize_bits(case["observed_outputs"].get("data_out"), 8)
        if dout_norm is None:
            bad.append("%s: data_out not well-formed 8-bit value" % fid)
            continue
        if dout_norm != ref_data:
            bad.append("%s: data_out=%s != reference_data=%s" % (fid, dout_norm, ref_data))

    if bad:
        emit_fail("FR3", "single-bit fault case violations (showing up to 5 of %d): %s" %
                   (len(bad), bad[:5]))
        return False

    emit_pass("FR3")
    return True


def check_fr4(fault_cases, summary, total_expected):
    for key in ("num_no_error", "num_corrected", "num_detected_uncorrectable"):
        if key not in summary:
            emit_fail("FR4", "summary missing key '%s'" % key)
            return False
        if not isinstance(summary[key], int) or isinstance(summary[key], bool):
            emit_fail("FR4", "summary.%s is not an integer" % key)
            return False

    n_no_error = summary["num_no_error"]
    n_corrected = summary["num_corrected"]
    n_uncorrectable = summary["num_detected_uncorrectable"]
    total = n_no_error + n_corrected + n_uncorrectable

    if total != total_expected:
        emit_fail("FR4", "summary counts sum to %d, expected %d" % (total, total_expected))
        return False

    actual_no_error = sum(1 for c in fault_cases if c["classification"] == "no_error")
    actual_corrected = sum(1 for c in fault_cases if c["classification"] == "corrected")
    actual_uncorrectable = sum(1 for c in fault_cases if c["classification"] == "detected_uncorrectable")

    mismatches = []
    if actual_no_error != n_no_error:
        mismatches.append("num_no_error: summary=%d actual=%d" % (n_no_error, actual_no_error))
    if actual_corrected != n_corrected:
        mismatches.append("num_corrected: summary=%d actual=%d" % (n_corrected, actual_corrected))
    if actual_uncorrectable != n_uncorrectable:
        mismatches.append("num_detected_uncorrectable: summary=%d actual=%d" % (n_uncorrectable, actual_uncorrectable))

    if mismatches:
        emit_fail("FR4", "summary counts do not match actual classification tally: %s" % mismatches)
        return False

    emit_pass("FR4")
    return True


def collect_report_strings(submission):
    """Recursively collect all string values from the submission JSON for
    substantive text checks (SR1/SR4)."""
    strings = []

    def walk(obj):
        if isinstance(obj, str):
            strings.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(submission)
    return " \n ".join(strings).lower()


def check_sr1(all_text):
    # Substantive phrase matching for: correctable decision uses syndrome!=0
    # alone, without gating on overall_parity_error (i.e., missing
    # double-error-detection gate). Paraphrase-tolerant: require mention of
    # overall_parity_error (or synonymous term) AND a phrase indicating it is
    # not checked/consulted/gated/used in the correctable decision, OR an
    # explicit statement of the correct required gating condition being
    # absent.
    parity_terms = [
        "overall_parity_error", "overall parity", "extended parity",
        "overall parity bit", "extended parity bit",
    ]
    missing_terms = [
        "not check", "not consult", "not used", "not gated", "not gate",
        "does not check", "doesn't check", "never check", "never checks",
        "never consult", "ignor", "without check", "without consult",
        "without gating", "missing", "fails to check", "fail to check",
        "not incorporated", "not factored", "not taken into account",
        "not considered", "isn't checked", "is not checked",
    ]
    syndrome_only_terms = [
        "syndrome != 0", "syndrome!=0", "syndrome is nonzero",
        "syndrome != 0000", "syndrome nonzero", "nonzero syndrome",
        "syndrome alone", "solely on syndrome", "syndrome only",
        "based only on", "based solely on", "driven solely",
        "driven only", "relies only on syndrome", "relies solely on syndrome",
    ]

    has_parity_mention = any(term in all_text for term in parity_terms)
    has_missing_phrase = any(term in all_text for term in missing_terms)
    has_syndrome_only_phrase = any(term in all_text for term in syndrome_only_terms)

    # Accept if: parity term mentioned AND (missing-phrase nearby OR
    # syndrome-only phrasing present), giving room for many paraphrases
    # while still requiring the substantive claim.
    if has_parity_mention and (has_missing_phrase or has_syndrome_only_phrase):
        emit_pass("SR1")
        return True

    # Also accept a strong direct statement even without explicit
    # "overall_parity_error" term, e.g. "double-error detection is missing"
    dbl_error_terms = [
        "double-error detection", "double error detection",
        "double-bit error detection", "double bit error detection",
        "detect double", "two-bit error detection",
    ]
    has_dbl_error_mention = any(term in all_text for term in dbl_error_terms)
    if has_dbl_error_mention and has_missing_phrase:
        emit_pass("SR1")
        return True

    emit_fail("SR1", "report does not substantively state that the decoder's "
                      "correctable/uncorrectable decision omits checking "
                      "overall_parity_error (missing double-error-detection gating)")
    return False


def check_sr2(submission, oracle_map, fault_model_entries):
    two_bit_ids = [e["fault_id"] for e in fault_model_entries if len(e["bit_positions"]) == 2]
    ground_truth_vuln = set(
        fid for fid in two_bit_ids
        if oracle_map[fid]["syndrome"] != 0 and oracle_map[fid]["ope"] == 1
    )

    submitted_vuln = submission.get("vulnerable_fault_ids")
    if not isinstance(submitted_vuln, list):
        emit_fail("SR2", "'vulnerable_fault_ids' missing or not an array")
        return False, ground_truth_vuln

    submitted_set = set(x for x in submitted_vuln if isinstance(x, str))

    sym_diff = ground_truth_vuln.symmetric_difference(submitted_set)
    if len(sym_diff) > 2:
        missing = ground_truth_vuln - submitted_set
        extra = submitted_set - ground_truth_vuln
        emit_fail("SR2", "vulnerable_fault_ids symmetric difference with ground truth = %d (>2); "
                         "missing examples=%s extra examples=%s" %
                  (len(sym_diff), sorted(missing)[:5], sorted(extra)[:5]))
        return False, ground_truth_vuln

    emit_pass("SR2")
    return True, ground_truth_vuln


def check_sr3(fault_cases, oracle_map, ref_data, ground_truth_vuln):
    if len(ground_truth_vuln) == 0:
        # A genuinely empty ground-truth miscorrection set would mean this
        # RTL/reference codeword combination has no security-relevant
        # miscorrection cases at all. In that (unexpected but logically
        # possible) situation there is nothing for the submission to get
        # right or wrong about per-case corrupted data_out, so we do not
        # penalize the submission for an oracle property outside its
        # control.
        emit_pass("SR3")
        return True

    by_id = {c["fault_id"]: c for c in fault_cases}

    satisfied = 0
    failures_examples = []
    for fid in ground_truth_vuln:
        case = by_id.get(fid)
        if case is None:
            failures_examples.append("%s: missing from submission" % fid)
            continue
        if case["classification"] != "corrected":
            failures_examples.append("%s: classification='%s' (expected 'corrected')" %
                                      (fid, case["classification"]))
            continue
        dout_norm = normalize_bits(case["observed_outputs"].get("data_out"), 8)
        if dout_norm is None:
            failures_examples.append("%s: data_out not well-formed" % fid)
            continue
        if dout_norm == ref_data:
            failures_examples.append("%s: data_out=%s equals reference_data (expected a differing, corrupted value)" %
                                      (fid, dout_norm))
            continue
        satisfied += 1

    fraction = satisfied / float(len(ground_truth_vuln))
    if fraction < 0.90:
        emit_fail("SR3", "only %.1f%% (%d/%d) of ground-truth miscorrection cases correctly reported as "
                         "'corrected' with a differing (corrupted) data_out; examples: %s" %
                  (fraction * 100.0, satisfied, len(ground_truth_vuln), failures_examples[:5]))
        return False

    emit_pass("SR3")
    return True


def check_sr4(submission, fault_cases, oracle_map, fault_model_entries, all_text):
    two_bit_ids = [e["fault_id"] for e in fault_model_entries if len(e["bit_positions"]) == 2]
    ground_truth_escape = set(fid for fid in two_bit_ids if oracle_map[fid]["syndrome"] == 0)

    # Distinct textual mention of the zero-syndrome escape class, separate
    # from the miscorrection/corrected-class discussion.
    escape_terms = [
        "zero-syndrome", "zero syndrome", "syndrome == 0", "syndrome==0",
        "syndrome equal to zero", "syndrome of zero", "syndrome is zero",
    ]
    escape_context_terms = [
        "escape", "undetected", "no_error", "no-error", "passes through",
        "pass through", "silently deliver", "silent corruption",
        "goes undetected", "not detected", "slip", "bypass",
    ]

    has_escape_mention = any(term in all_text for term in escape_terms)
    has_escape_context = any(term in all_text for term in escape_context_terms)
    has_distinct_textual_finding = has_escape_mention and has_escape_context

    if len(ground_truth_escape) == 0:
        # The oracle's true zero-syndrome two-bit escape set is empty for
        # this pinned RTL/reference codeword. There is no per-case
        # classification behavior to check; instead we require the report
        # to explicitly and correctly state this outcome (that no such
        # escape cases exist) as its distinct SR4 finding, so the report
        # cannot simply omit discussion of this class entirely.
        empty_claim_terms = [
            "no zero-syndrome two-bit", "no zero syndrome two-bit",
            "no two-bit fault", "none of the two-bit",
            "there are no", "does not exist", "do not exist",
            "empty set", "no cases", "zero cases", "no such cases",
            "no fault cases", "no two-bit faults produce",
        ]
        has_empty_claim = has_escape_mention and any(term in all_text for term in empty_claim_terms)

        if has_empty_claim or (has_escape_mention and "no" in all_text and has_escape_context is False and
                                any(term in all_text for term in ["none", "no cases", "zero cases"])):
            emit_pass("SR4")
            return True

        emit_fail("SR4", "ground-truth zero-syndrome two-bit escape set is empty for this reference codeword, "
                         "but the report does not explicitly and correctly state this outcome (that no such "
                         "escape cases exist) as a distinct SR4 finding")
        return False

    by_id = {c["fault_id"]: c for c in fault_cases}
    satisfied = 0
    failures_examples = []
    for fid in ground_truth_escape:
        case = by_id.get(fid)
        if case is None:
            failures_examples.append("%s: missing from submission" % fid)
            continue
        if case["classification"] == "no_error":
            satisfied += 1
        else:
            failures_examples.append("%s: classification='%s' (expected 'no_error')" %
                                      (fid, case["classification"]))

    fraction = satisfied / float(len(ground_truth_escape))
    if fraction < 0.90:
        emit_fail("SR4", "only %.1f%% (%d/%d) of ground-truth zero-syndrome escape cases classified 'no_error'; "
                         "examples: %s" % (fraction * 100.0, satisfied, len(ground_truth_escape), failures_examples[:5]))
        return False

    if not has_distinct_textual_finding:
        emit_fail("SR4", "ground-truth escape-class classification matched, but report lacks an explicit "
                         "distinct textual finding identifying the zero-syndrome two-bit escape class as a "
                         "separate undetected-corruption risk")
        return False

    emit_pass("SR4")
    return True


def main():
    check_inputs_exist()

    fault_model_entries = load_fault_model()

    ref_data, oracle_cases = run_oracle_simulation()
    oracle_map = build_oracle_map(fault_model_entries, oracle_cases)

    total_expected = len(fault_model_entries)

    submission = load_submission()

    if isinstance(submission, tuple) and submission and submission[0] == "MISSING":
        fail_setup(submission[1])
        return

    fr1_ok, fr1_reason, fault_cases, summary = validate_fr1(submission)
    if not fr1_ok:
        emit_fail("FR1", fr1_reason)
        # Downstream requirements cannot be meaningfully evaluated without a
        # valid structure; fail them all with a clear dependency reason.
        for rid in ("FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"):
            emit_fail(rid, "skipped due to FR1 failure: %s" % fr1_reason)
        sys.exit(1)

    emit_pass("FR1")

    fr2_ok = check_fr2(fault_cases, fault_model_entries)
    fr3_ok = check_fr3(fault_cases, oracle_map, ref_data, fault_model_entries)
    fr4_ok = check_fr4(fault_cases, summary, total_expected)

    all_text = collect_report_strings(submission)

    sr1_ok = check_sr1(all_text)
    sr2_ok, ground_truth_vuln = check_sr2(submission, oracle_map, fault_model_entries)
    sr3_ok = check_sr3(fault_cases, oracle_map, ref_data, ground_truth_vuln)
    sr4_ok = check_sr4(submission, fault_cases, oracle_map, fault_model_entries, all_text)

    all_ok = all([fr2_ok, fr3_ok, fr4_ok, sr1_ok, sr2_ok, sr3_ok, sr4_ok])

    if all_ok:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()