#!/usr/bin/env python3
"""
evaluate.py -- grades submission/vulnerability_report.json against the
functional and security requirements defined for task
sca_fixed_latency_enable_count_001.

This script:
  1. Loads inputs/traces.csv as the ground-truth reference. NOTE: the
     shipped inputs/traces.csv may contain narrative prose and/or a
     markdown code fence wrapping the actual CSV data (as produced by a
     derivation scratchpad). This loader tolerates that by locating the
     literal header line 'trial_id,secret_operand,cycle_index,mul_en,done'
     anywhere in the file and parsing from there, stopping at a closing
     fence or the end of file, so that well-formed embedded CSV data is
     still recovered.
  2. Loads submission/vulnerability_report.json (the answer file to grade).
  3. Runs one check per requirement (FR1-FR4, SR1-SR3), each emitting
     exactly one '[TEST] PASS: <id>' or '[TEST] FAIL: <id>: <reason>' line.
  4. Exits 0 if all requirements pass, non-zero otherwise.

Only Python stdlib is used. No network access. Deterministic.
"""

import csv
import io
import json
import os
import re
import sys

ALL_REQ_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3"]

INPUTS_DIR = "inputs"
TRACES_CSV = os.path.join(INPUTS_DIR, "traces.csv")
SUBMISSION_PATH = os.path.join("submission", "vulnerability_report.json")

REQUIRED_COLS = ["trial_id", "secret_operand", "cycle_index", "mul_en", "done"]


def emit_pass(req_id):
    print("[TEST] PASS: {}".format(req_id))


def emit_fail(req_id, reason):
    print("[TEST] FAIL: {}: {}".format(req_id, reason))


def popcount(n):
    return bin(n & 0xFF).count("1")


def _extract_csv_text(raw_text):
    """
    Given the raw contents of inputs/traces.csv (which may be a plain CSV,
    or may contain surrounding prose / a markdown code fence wrapping the
    actual CSV data), locate and return just the CSV text: a header line
    matching the required columns (in any order) followed by data rows,
    up to a closing fence marker or end of file.

    Raises ValueError if no such header line can be found.
    """
    lines = raw_text.splitlines()

    header_idx = None
    header_cols = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # Skip markdown fence marker lines themselves.
        if stripped.startswith("```"):
            continue
        candidate_cols = [c.strip() for c in stripped.split(",")]
        if set(candidate_cols) == set(REQUIRED_COLS) and len(candidate_cols) == len(
            REQUIRED_COLS
        ):
            header_idx = idx
            header_cols = candidate_cols
            break

    if header_idx is None:
        raise ValueError(
            "could not locate CSV header row containing exactly columns {}".format(
                sorted(REQUIRED_COLS)
            )
        )

    data_lines = [",".join(header_cols)]
    for line in lines[header_idx + 1 :]:
        stripped = line.strip()
        if stripped.startswith("```"):
            break
        if stripped == "":
            # Allow blank lines inside the data block (skip them), but stop
            # if we've already collected at least one data row and hit a
            # long run of prose afterward is not something we try to
            # detect here -- keep it simple and just skip blanks.
            continue
        data_lines.append(line)

    return "\n".join(data_lines) + "\n"


def load_traces(path):
    """
    Parse traces.csv (tolerating surrounding prose / markdown fencing)
    into a structure:
      trials: dict[trial_id] -> {
          'secret_operand_hex': str (normalized upper hex, e.g. '0x3F'),
          'secret_operand_int': int,
          'rows': list of (cycle_index, mul_en, done)
      }
    """
    with open(path, "r", newline="") as f:
        raw_text = f.read()

    csv_text = _extract_csv_text(raw_text)

    trials = {}
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        raise ValueError("traces.csv has no header row")
    missing_cols = set(REQUIRED_COLS) - set(
        c.strip() for c in reader.fieldnames
    )
    if missing_cols:
        raise ValueError(
            "traces.csv header missing required columns: {}".format(
                sorted(missing_cols)
            )
        )

    # Normalize fieldnames (strip whitespace) by re-mapping rows.
    fieldname_map = {fn: fn.strip() for fn in reader.fieldnames}

    row_count = 0
    for row in reader:
        norm_row = {fieldname_map[k]: v for k, v in row.items() if k in fieldname_map}

        trial_id = (norm_row.get("trial_id") or "").strip()
        if trial_id == "":
            continue
        sec_hex_raw = (norm_row.get("secret_operand") or "").strip()
        try:
            sec_int = int(sec_hex_raw, 16)
        except ValueError:
            raise ValueError(
                "malformed secret_operand hex in traces.csv: {}".format(sec_hex_raw)
            )
        sec_hex_norm = "0x{:02X}".format(sec_int)

        try:
            cycle_index = int((norm_row.get("cycle_index") or "").strip())
            mul_en = int((norm_row.get("mul_en") or "").strip())
            done = int((norm_row.get("done") or "").strip())
        except ValueError:
            raise ValueError("malformed integer field in traces.csv row: {}".format(row))

        if trial_id not in trials:
            trials[trial_id] = {
                "secret_operand_hex": sec_hex_norm,
                "secret_operand_int": sec_int,
                "rows": [],
            }
        trials[trial_id]["rows"].append((cycle_index, mul_en, done))
        row_count += 1

    if row_count == 0:
        raise ValueError("no data rows parsed from traces.csv")

    return trials


def compute_ground_truth(trials):
    """
    From parsed trials, compute:
      operand_enable_count: dict[normalized_hex] -> enable_count
          (sum of mul_en over cycle_index 1..8)
      operand_hamming_weight: dict[normalized_hex] -> popcount(int)
      operand_done_cycle_set: dict[normalized_hex] -> set of cycle_index
          where done == 1
      latency_constant_ok: bool -- True iff for every trial, done==1 occurs
          at exactly one cycle_index and that cycle_index == 8, and done==0
          everywhere else.
      distinct_operands: sorted list of normalized hex operand strings
          present in traces.csv
    """
    operand_enable_count = {}
    operand_hamming_weight = {}
    operand_done_cycle_set = {}
    latency_constant_ok = True

    for trial_id, info in trials.items():
        sec_hex = info["secret_operand_hex"]
        sec_int = info["secret_operand_int"]
        rows = info["rows"]

        enable_count = sum(
            1 for (cyc, mul_en, done) in rows if 1 <= cyc <= 8 and mul_en == 1
        )
        done_cycles = set(cyc for (cyc, mul_en, done) in rows if done == 1)

        if sec_hex not in operand_enable_count:
            operand_enable_count[sec_hex] = enable_count
            operand_hamming_weight[sec_hex] = popcount(sec_int)
            operand_done_cycle_set[sec_hex] = done_cycles

        # Verify constant latency ground truth from traces.csv itself.
        if len(done_cycles) != 1 or 8 not in done_cycles:
            latency_constant_ok = False

    distinct_operands = sorted(operand_enable_count.keys())
    return (
        operand_enable_count,
        operand_hamming_weight,
        operand_done_cycle_set,
        latency_constant_ok,
        distinct_operands,
    )


def normalize_hex(s):
    """Normalize a hex string like '0x3f', '3F', '0X3F' to '0x3F' form.
    Returns None if it cannot be parsed as a byte hex value."""
    if not isinstance(s, str):
        return None
    txt = s.strip()
    try:
        val = int(txt, 16)
    except ValueError:
        return None
    if val < 0 or val > 0xFF:
        return None
    return "0x{:02X}".format(val)


def check_fr1(report):
    """Structural validation of top-level fields and types."""
    if not isinstance(report, dict):
        return False, "report top-level JSON is not an object"

    if "summary" not in report or not isinstance(report["summary"], str):
        return False, "missing or non-string field 'summary'"

    if "timing_analysis" not in report or not isinstance(
        report["timing_analysis"], dict
    ):
        return False, "missing or non-object field 'timing_analysis'"

    ta = report["timing_analysis"]
    if "observed_latency_cycles" not in ta or not isinstance(
        ta["observed_latency_cycles"], int
    ) or isinstance(ta["observed_latency_cycles"], bool):
        return False, "timing_analysis missing/non-integer 'observed_latency_cycles'"

    if "latency_is_constant" not in ta or not isinstance(
        ta["latency_is_constant"], bool
    ):
        return False, "timing_analysis missing/non-boolean 'latency_is_constant'"

    if "activity_analysis" not in report or not isinstance(
        report["activity_analysis"], list
    ):
        return False, "missing or non-array field 'activity_analysis'"

    for idx, entry in enumerate(report["activity_analysis"]):
        if not isinstance(entry, dict):
            return False, "activity_analysis[{}] is not an object".format(idx)
        if "secret_operand" not in entry or not isinstance(
            entry["secret_operand"], str
        ):
            return False, "activity_analysis[{}] missing/non-string 'secret_operand'".format(
                idx
            )
        if "enable_count" not in entry or not isinstance(
            entry["enable_count"], int
        ) or isinstance(entry["enable_count"], bool):
            return False, "activity_analysis[{}] missing/non-integer 'enable_count'".format(
                idx
            )
        if "hamming_weight" not in entry or not isinstance(
            entry["hamming_weight"], int
        ) or isinstance(entry["hamming_weight"], bool):
            return False, "activity_analysis[{}] missing/non-integer 'hamming_weight'".format(
                idx
            )

    if "hardening_recommendations" not in report or not isinstance(
        report["hardening_recommendations"], list
    ):
        return False, "missing or non-array field 'hardening_recommendations'"

    return True, ""


def check_fr2(report, latency_constant_ok):
    ta = report.get("timing_analysis", {})
    observed = ta.get("observed_latency_cycles")
    is_const = ta.get("latency_is_constant")

    if not latency_constant_ok:
        # Ground truth itself would be inconsistent; this should not happen
        # with a well-formed traces.csv, but guard anyway.
        return False, "ground truth traces.csv does not exhibit constant 8-cycle latency"

    if observed != 8:
        return False, "reported observed_latency_cycles={} but ground truth is 8".format(
            observed
        )

    if is_const is not True:
        return False, "reported latency_is_constant={} but ground truth is true".format(
            is_const
        )

    return True, ""


def check_fr3_and_sr1(report, operand_enable_count, operand_hamming_weight, distinct_operands):
    """
    Returns two (bool, str) tuples: (fr3_result, sr1_result)
    FR3: coverage (>=16 distinct operands present in traces.csv) and exact
         enable_count match against traces.csv ground truth.
    SR1: hamming_weight correctness AND enable_count == hamming_weight for
         every analyzed entry.
    """
    activity = report.get("activity_analysis", [])
    if not isinstance(activity, list):
        return (False, "activity_analysis is not a list"), (
            False,
            "activity_analysis is not a list",
        )

    valid_operand_set = set(distinct_operands)

    # Deduplicate by normalized secret_operand hex string, keep first entry.
    dedup = {}
    for entry in activity:
        if not isinstance(entry, dict):
            continue
        raw = entry.get("secret_operand")
        norm = normalize_hex(raw) if isinstance(raw, str) else None
        if norm is None:
            continue
        if norm not in dedup:
            dedup[norm] = entry

    distinct_count = len(dedup)
    if distinct_count < 16:
        fr3_res = (
            False,
            "activity_analysis covers only {} distinct valid secret_operand values (need >=16)".format(
                distinct_count
            ),
        )
    else:
        fr3_res = None  # tentatively pass; may still fail below on mismatch

    fr3_fail_reason = None
    sr1_fail_reason = None

    for norm_hex, entry in dedup.items():
        if norm_hex not in valid_operand_set:
            fr3_fail_reason = (
                "activity_analysis references secret_operand {} not present in traces.csv".format(
                    norm_hex
                )
            )
            continue

        expected_enable_count = operand_enable_count[norm_hex]
        expected_hamming = operand_hamming_weight[norm_hex]

        reported_enable_count = entry.get("enable_count")
        reported_hamming = entry.get("hamming_weight")

        if reported_enable_count != expected_enable_count:
            if fr3_fail_reason is None:
                fr3_fail_reason = (
                    "operand {}: reported enable_count={} but traces.csv shows {}".format(
                        norm_hex, reported_enable_count, expected_enable_count
                    )
                )

        # SR1: hamming_weight must be correctly computed from operand bits,
        # AND enable_count must equal that hamming weight (the leakage
        # relationship). We check against the true popcount of the operand
        # (expected_hamming), not merely internal self-consistency, so a
        # report can't fabricate a wrong hamming_weight to match a wrong
        # enable_count.
        if reported_hamming != expected_hamming:
            if sr1_fail_reason is None:
                sr1_fail_reason = (
                    "operand {}: reported hamming_weight={} but popcount is {}".format(
                        norm_hex, reported_hamming, expected_hamming
                    )
                )
        elif reported_enable_count != expected_hamming:
            if sr1_fail_reason is None:
                sr1_fail_reason = (
                    "operand {}: enable_count={} does not equal hamming_weight={} (leakage relationship not identified)".format(
                        norm_hex, reported_enable_count, expected_hamming
                    )
                )

    if fr3_res is None:
        if fr3_fail_reason is not None:
            fr3_res = (False, fr3_fail_reason)
        else:
            fr3_res = (True, "")

    if sr1_fail_reason is not None:
        sr1_res = (False, sr1_fail_reason)
    else:
        if distinct_count == 0:
            sr1_res = (False, "no valid activity_analysis entries to verify")
        else:
            sr1_res = (True, "")

    return fr3_res, sr1_res


def check_fr4(report):
    recs = report.get("hardening_recommendations", [])
    if not isinstance(recs, list):
        return False, "hardening_recommendations is not a list"

    non_empty = [
        r for r in recs if isinstance(r, str) and len(r.strip()) > 0
    ]
    if len(non_empty) < 2:
        return False, "hardening_recommendations has only {} non-empty string entries (need >=2)".format(
            len(non_empty)
        )

    # Ensure no blank/whitespace-only entries exist among declared entries.
    for idx, r in enumerate(recs):
        if not isinstance(r, str) or len(r.strip()) == 0:
            return False, "hardening_recommendations[{}] is empty or not a string".format(
                idx
            )

    return True, ""


def check_sr2(report):
    """
    SR2: report must explicitly recognize that constant latency alone does
    NOT prevent side-channel leakage.

    We scan 'summary' and the stringified 'timing_analysis' text
    case-insensitively for co-occurrence, within the combined text, of:
      - a constant-latency term (constant, fixed, invariant... + latency/timing/cycles)
      - a negation term (not, does not, doesn't, no, never, insufficient,
        cannot, fails to, isn't) applied to prevention/elimination of
        leakage (prevent, eliminate, hide, mitigate, stop) OR an explicit
        statement that leakage/vulnerability exists despite constant timing.
      - some mention of leakage/vulnerability/side-channel concept.
    """
    text_fields = []
    summary = report.get("summary")
    if isinstance(summary, str):
        text_fields.append(summary)

    ta = report.get("timing_analysis")
    if isinstance(ta, dict):
        # Stringify any extra free-text fields the report author may have
        # added inside timing_analysis (beyond the required numeric/bool
        # fields), since SR2 detection is permitted to look there too.
        for v in ta.values():
            if isinstance(v, str):
                text_fields.append(v)

    combined = " ".join(text_fields).lower()

    if not combined.strip():
        return False, "no summary/timing_analysis text to evaluate for SR2"

    constant_terms = ["constant", "fixed", "invariant", "does not vary", "same every"]
    negation_prevent_terms = [
        "does not prevent",
        "doesn't prevent",
        "does not eliminate",
        "doesn't eliminate",
        "does not stop",
        "doesn't stop",
        "does not hide",
        "doesn't hide",
        "does not mitigate",
        "doesn't mitigate",
        "not sufficient",
        "insufficient",
        "not enough",
        "cannot prevent",
        "can't prevent",
        "fails to prevent",
        "still leak",
        "still vulnerable",
        "does not protect",
        "doesn't protect",
        "no protection against",
    ]

    has_constant_term = any(t in combined for t in constant_terms)
    has_negation_prevent = any(t in combined for t in negation_prevent_terms)

    # Also require some mention of leakage/vulnerability/side-channel
    # concept in the combined text, so we don't accept an unrelated negation.
    leakage_terms = [
        "leak",
        "vulnerab",
        "side-channel",
        "side channel",
        "exposed",
        "reveal",
    ]
    has_leakage_term = any(t in combined for t in leakage_terms)

    if has_constant_term and has_negation_prevent and has_leakage_term:
        return True, ""

    return False, (
        "no explicit statement found linking constant/fixed latency to "
        "insufficiency of protection against leakage"
    )


def check_sr3(report):
    """
    SR3: at least one hardening recommendation must target activity
    equalization (switching activity, dummy operations, unconditional
    enable, constant Hamming weight, masking) rather than only
    timing/delay-only countermeasures.
    """
    recs = report.get("hardening_recommendations", [])
    if not isinstance(recs, list) or not recs:
        return False, "hardening_recommendations is empty or missing"

    equalization_keywords = [
        "dummy operation",
        "dummy cycle",
        "dummy op",
        "always assert",
        "always-on",
        "always on",
        "unconditional",
        "unconditionally assert",
        "constant hamming",
        "constant-weight",
        "constant weight",
        "fixed hamming weight",
        "balanced switching",
        "equalize",
        "equalise",
        "equal switching",
        "uniform switching",
        "uniform activity",
        "masked accumulation",
        "masking",
        "mask the accumulat",
        "data-independent",
        "data independent",
        "every cycle regardless",
        "toggle every cycle",
        "constant activity",
        "activity equalization",
        "activity equalisation",
    ]

    timing_only_keywords = [
        "random delay",
        "randomize the done",
        "randomize done",
        "randomise done",
        "extra wait cycle",
        "additional wait cycle",
        "jitter",
        "delay after done",
        "insert delay",
        "add delay",
        "wait state",
        "no-op wait",
        "noop wait",
        "randomized latency",
        "randomised latency",
        "vary the latency",
        "variable latency",
    ]

    found_equalization = False
    for rec in recs:
        if not isinstance(rec, str):
            continue
        low = rec.lower()
        if any(kw in low for kw in equalization_keywords):
            found_equalization = True
            break

    if found_equalization:
        return True, ""

    # Determine if all recommendations are purely timing-only, to give a
    # more specific failure reason.
    any_timing_only = False
    for rec in recs:
        if not isinstance(rec, str):
            continue
        low = rec.lower()
        if any(kw in low for kw in timing_only_keywords):
            any_timing_only = True
            break

    if any_timing_only:
        return False, (
            "hardening_recommendations only propose timing/delay-based "
            "countermeasures (e.g. random delay, extra wait cycles) which "
            "do not address enable_count/switching-activity leakage"
        )

    return False, (
        "no hardening_recommendations entry addresses switching-activity "
        "equalization (e.g. dummy operations, unconditional enable, "
        "constant-weight encoding, masked accumulation)"
    )


def main():
    results = {}  # req_id -> (bool, reason)

    # --- Load ground truth from inputs/traces.csv ---
    if not os.path.isfile(TRACES_CSV):
        for rid in ALL_REQ_IDS:
            emit_fail(rid, "SETUP: {} not found".format(TRACES_CSV))
        sys.exit(1)

    try:
        trials = load_traces(TRACES_CSV)
        (
            operand_enable_count,
            operand_hamming_weight,
            operand_done_cycle_set,
            latency_constant_ok,
            distinct_operands,
        ) = compute_ground_truth(trials)
    except Exception as e:
        for rid in ALL_REQ_IDS:
            emit_fail(rid, "SETUP: failed to parse {}: {}".format(TRACES_CSV, e))
        sys.exit(1)

    # --- Load submission ---
    if not os.path.isfile(SUBMISSION_PATH):
        for rid in ALL_REQ_IDS:
            emit_fail(rid, "SETUP: {} not found".format(SUBMISSION_PATH))
        sys.exit(1)

    try:
        with open(SUBMISSION_PATH, "r") as f:
            raw_text = f.read()
    except Exception as e:
        for rid in ALL_REQ_IDS:
            emit_fail(rid, "SETUP: failed to read {}: {}".format(SUBMISSION_PATH, e))
        sys.exit(1)

    try:
        report = json.loads(raw_text)
    except Exception as e:
        reason = "invalid JSON in {}: {}".format(SUBMISSION_PATH, e)
        for rid in ALL_REQ_IDS:
            emit_fail(rid, reason)
        sys.exit(1)

    # --- FR1: structural validation ---
    fr1_ok, fr1_reason = check_fr1(report)
    results["FR1"] = (fr1_ok, fr1_reason)

    if not fr1_ok:
        # Cascade fail remaining requirements since structural validity is
        # a prerequisite for meaningfully checking them.
        cascade_reason = "cannot evaluate: FR1 failed ({})".format(fr1_reason)
        for rid in ["FR2", "FR3", "FR4", "SR1", "SR2", "SR3"]:
            results[rid] = (False, cascade_reason)
    else:
        # --- FR2: constant latency check ---
        fr2_ok, fr2_reason = check_fr2(report, latency_constant_ok)
        results["FR2"] = (fr2_ok, fr2_reason)

        # --- FR3 & SR1: activity_analysis coverage/accuracy + leakage id ---
        fr3_res, sr1_res = check_fr3_and_sr1(
            report, operand_enable_count, operand_hamming_weight, distinct_operands
        )
        results["FR3"] = fr3_res
        results["SR1"] = sr1_res

        # --- FR4: hardening_recommendations structural check ---
        fr4_ok, fr4_reason = check_fr4(report)
        results["FR4"] = (fr4_ok, fr4_reason)

        # --- SR2: explicit acknowledgement constant latency != secure ---
        sr2_ok, sr2_reason = check_sr2(report)
        results["SR2"] = (sr2_ok, sr2_reason)

        # --- SR3: activity-equalization recommendation present ---
        sr3_ok, sr3_reason = check_sr3(report)
        results["SR3"] = (sr3_ok, sr3_reason)

    # --- Emit results in canonical order ---
    all_ok = True
    for rid in ALL_REQ_IDS:
        ok, reason = results[rid]
        if ok:
            emit_pass(rid)
        else:
            emit_fail(rid, reason)
            all_ok = False

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()