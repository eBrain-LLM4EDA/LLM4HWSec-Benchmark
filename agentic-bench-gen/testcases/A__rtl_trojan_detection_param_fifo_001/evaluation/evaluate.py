#!/usr/bin/env python3
"""
evaluate.py -- grades submission/trojan_report.json against the hidden
ground truth for the param_fifo WIDTH=24 trojan-detection task.

Python stdlib only. Reads inputs/ for reference and (optionally) for a
non-gating cross-simulation sanity check via iverilog/vvp. All PASS/FAIL
verdicts are computed against the submitted report.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

RESULTS = []  # list of (req_id, passed(bool), reason(str))


def record(req_id, passed, reason=""):
    RESULTS.append((req_id, passed, reason))
    if passed:
        print("[TEST] PASS: {}".format(req_id))
    else:
        print("[TEST] FAIL: {}: {}".format(req_id, reason))


def fail_all(req_ids, reason):
    for rid in req_ids:
        record(rid, False, reason)


ALL_REQ_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]


def main():
    # ---- Load required input artifacts (reference only) ----
    input_files = ["inputs/param_fifo.v", "inputs/fifo_spec.md", "inputs/testbench_default.v"]
    for f in input_files:
        if not os.path.isfile(f):
            print("[TEST] FAIL: SETUP: {} not found".format(f))
            sys.exit(1)

    submission_path = "submission/trojan_report.json"
    if not os.path.isfile(submission_path):
        print("[TEST] FAIL: SETUP: {} not found".format(submission_path))
        sys.exit(1)

    with open(submission_path, "r", encoding="utf-8", errors="replace") as fh:
        raw_text = fh.read()

    try:
        report = json.loads(raw_text)
    except Exception as e:
        record("FR1", False, "submission/trojan_report.json is not valid JSON: {}".format(e))
        fail_all(["FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"],
                  "cannot evaluate: report failed to parse as JSON")
        finalize()
        return

    # ---- FR1: schema validity ----
    fr1_ok, fr1_reason, findings = check_fr1(report)
    record("FR1", fr1_ok, fr1_reason)

    if not fr1_ok:
        # Downstream requirements cannot be meaningfully evaluated.
        fail_all(["FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"],
                  "cannot evaluate: schema (FR1) failed")
        finalize()
        return

    if not findings:
        fail_all(["FR2", "FR3", "FR4"], "findings array is empty")
        fail_all(["SR1", "SR2", "SR3", "SR4"], "findings array is empty")
        finalize()
        return

    # ---- FR2/FR3/FR4: at least one finding satisfies each ----
    fr2_idx = [i for i, f in enumerate(findings) if finding_matches_fr2(f)]
    record("FR2", len(fr2_idx) > 0,
           "no finding names a specific non-default WIDTH (e.g. 24) distinct from "
           "'all widths'/'default' claims")

    fr3_idx = [i for i, f in enumerate(findings) if finding_matches_fr3(f)]
    record("FR3", len(fr3_idx) > 0,
           "no finding's payload_effect describes a concrete functional consequence "
           "(full/empty flag misbehavior or overwrite of unread data)")

    fr4_idx = [i for i, f in enumerate(findings) if finding_matches_fr4(f)]
    record("FR4", len(fr4_idx) > 0,
           "no finding's trigger_condition references a specific pointer/occupancy "
           "state/pattern without also claiming the flaw is unconditional/on every write")

    # ---- SR1: WIDTH=24 correctly scoped (extracted affected width set == {24}) ----
    sr1_idx = [i for i, f in enumerate(findings) if finding_matches_sr1(f)]
    record("SR1", len(sr1_idx) > 0,
           "no finding's set of asserted-affected widths equals exactly {24}; either "
           "no width was named as affected, or a different width (e.g. 16 or 8) was "
           "asserted as affected rather than merely mentioned in an excluded/negated context")

    # ---- SR2: trigger condition combines pointer-pattern + near-full + write coincidence
    # (conjunctively, in the same finding, with no broadened/vague substitute phrasing)
    sr2_idx = [i for i, f in enumerate(findings) if finding_matches_sr2(f)]
    record("SR2", len(sr2_idx) > 0,
           "no finding's trigger_condition conjunctively combines a specific rare "
           "pointer-bit-pattern/occupancy-signature, a write-enable/write-attempt "
           "coincidence, and a specific near-full/at-capacity (DEPTH-1) boundary "
           "condition without substituting a broadened/vague phrase")

    # ---- SR3: payload effect = flag suppression AND overwrite/corruption ----
    sr3_idx = [i for i, f in enumerate(findings) if finding_matches_sr3(f)]
    record("SR3", len(sr3_idx) > 0,
           "no finding's payload_effect describes BOTH full-flag suppression/incorrect "
           "deassertion AND a resulting overwrite/corruption of unread data")

    # ---- SR4: qualifying finding (SR1 & SR2 & SR3) must be at/near top confidence ----
    qualifying = sorted(set(sr1_idx) & set(sr2_idx) & set(sr3_idx))
    if not qualifying:
        record("SR4", False,
               "no single finding simultaneously satisfies SR1+SR2+SR3, so ranking "
               "cannot be assessed as non-buried")
    else:
        try:
            all_conf = [safe_float(f.get("confidence", 0)) for f in findings]
            max_conf = max(all_conf)
            qual_conf = [safe_float(findings[i].get("confidence", 0)) for i in qualifying]
            best_qual_conf = max(qual_conf)
            if best_qual_conf >= max_conf - 1e-9:
                record("SR4", True)
            else:
                record("SR4", False,
                       "the qualifying WIDTH=24 finding (confidence={}) is ranked below "
                       "an unrelated finding (max confidence={}), i.e. buried".format(
                           best_qual_conf, max_conf))
        except Exception as e:
            record("SR4", False, "error comparing confidence scores: {}".format(e))

    # ---- Optional, non-gating cross-simulation sanity check ----
    try:
        run_optional_cross_sim()
    except Exception:
        # Never let this affect verdicts.
        pass

    finalize()


def safe_float(v):
    try:
        return float(v)
    except Exception:
        return 0.0


def check_fr1(report):
    findings = None
    if not isinstance(report, dict):
        return False, "top-level JSON value is not an object", None

    if "summary" not in report:
        return False, "missing required top-level field 'summary'", None
    if not isinstance(report["summary"], str) or len(report["summary"].strip()) == 0:
        return False, "'summary' must be a non-empty string", None

    if "findings" not in report:
        return False, "missing required top-level field 'findings'", None
    if not isinstance(report["findings"], list):
        return False, "'findings' must be an array", None

    findings = report["findings"]

    for idx, f in enumerate(findings):
        if not isinstance(f, dict):
            return False, "findings[{}] is not an object".format(idx), None

        for field in ("trigger_condition", "payload_effect", "rationale"):
            if field not in f:
                return False, "findings[{}] missing required field '{}'".format(idx, field), None
            if not isinstance(f[field], str) or len(f[field].strip()) == 0:
                return False, "findings[{}].{} must be a non-empty string".format(idx, field), None

        if "confidence" not in f:
            return False, "findings[{}] missing required field 'confidence'".format(idx), None
        conf = f["confidence"]
        if isinstance(conf, bool) or not isinstance(conf, (int, float)):
            return False, "findings[{}].confidence must be a number".format(idx), None
        if conf < 0.0 or conf > 1.0:
            return False, "findings[{}].confidence out of range [0,1]: {}".format(idx, conf), None

        if "affected_parameters" in f and f["affected_parameters"] is not None:
            if not isinstance(f["affected_parameters"], str):
                return False, "findings[{}].affected_parameters must be a string".format(idx), None

    return True, "", findings


def text_of(f, *fields):
    parts = []
    for field in fields:
        v = f.get(field, "")
        if isinstance(v, str):
            parts.append(v)
    return " ".join(parts).lower()


WIDTH24_PATTERNS = [
    r"\bwidth\s*(?:==|=|is|of)?\s*24\b",
    r"\b24[\s-]*bit\b",
    r"\bwidth24\b",
    r"\bwidth\s*\(\s*24\s*\)",
    r"\b24-bit\s*(?:bus|width|profile|configuration|instantiation)",
]

UNIFORM_CLAIM_PATTERNS = [
    r"\ball\s+widths?\b",
    r"\bevery\s+width\b",
    r"\buniformly\b",
    r"\bregardless\s+of\s+width\b",
    r"\bany\s+width\b",
    r"\bindependent\s+of\s+width\b",
]

DEFAULT_ONLY_PATTERNS = [
    r"\bdefault\s+width\b(?!.*24)",
    r"\bonly\s+(?:the\s+)?default\b",
]

OTHER_WIDTH_CLAIM_PATTERNS = [
    r"\bwidth\s*(?:==|=|is)?\s*8\b(?!\d)",
    r"\bwidth\s*(?:==|=|is)?\s*16\b(?!\d)",
    r"\b8[\s-]*bit\b",
    r"\b16[\s-]*bit\b",
]


def any_match(patterns, text):
    return any(re.search(p, text) for p in patterns)


def finding_matches_fr2(f):
    text = text_of(f, "affected_parameters", "trigger_condition")
    if not any_match(WIDTH24_PATTERNS, text):
        return False
    # FR2 is looser than SR1: we only require that 24 is explicitly named.
    return True


def finding_matches_fr3(f):
    text = text_of(f, "payload_effect")
    concrete_terms = [
        r"\bfull\b.{0,40}\b(?:incorrect|deassert|suppress|glitch|clear|drop)",
        r"\b(?:deassert|suppress|clear)(?:s|ed|ion)?\b.{0,30}\bfull\b",
        r"\bovel?rwrit(?:e|ten|ing)\b",
        r"\bcorrupt(?:ion|ed|s)?\b",
        r"\bunread\s+data\b",
        r"\bdata\s+(?:loss|corruption|integrity)\b",
        r"\bstale\s+data\b",
        r"\bincorrect\s+(?:value|timing)\s+of\s+(?:the\s+)?(?:full|empty)\b",
    ]
    if not any_match(concrete_terms, text):
        return False
    return True


# ---- FR4: specific pointer/occupancy condition tokens vs. unconditional claims ----

FR4_SPECIFIC_TERMS = [
    r"\b(?:write\s*)?pointer\b",
    r"\bwr_ptr\b",
    r"\b(?:occupancy|count)\b",
    r"3'b\s*101\b",
    r"\b101\b",
    r"\bnear[\s-]*full\b",
    r"\balmost[\s-]*full\b",
    r"\bdepth\s*-\s*1\b",
    r"\bcount\s*==?\s*depth",
    r"\bbit\s*pattern\b",
    r"\bpointer\s*(?:alignment|offset|pattern)\b",
]

# Vulnerability-adjacent mutant text: "the flaw occurs on every write, regardless of
# pointer state or occupancy, unconditionally whenever wr_en is asserted" -- these
# phrases must be checked in the SAME finding's trigger_condition/rationale text as
# where the specific tokens appear, and if present at all, that finding fails FR4
# even if specific tokens also appear elsewhere in the same finding.
FR4_UNCONDITIONAL_PATTERNS = [
    r"\bevery\s+write\b",
    r"\bunconditionally\b",
    r"\bon\s+any\s+write\b",
    r"\ball\s+writes\b",
    r"\bregardless\s+of\b",
    r"\bwhenever\s+wr_en\s+is\s+asserted\b",
    r"\bno\s+matter\s+(?:the|what)\s+(?:pointer|occupancy|state)\b",
]


def finding_matches_fr4(f):
    text = text_of(f, "trigger_condition", "rationale")
    if not any_match(FR4_SPECIFIC_TERMS, text):
        return False
    # Reject if an unconditional-claim phrase co-occurs anywhere in this finding's
    # trigger_condition/rationale text, even alongside specific tokens.
    if any_match(FR4_UNCONDITIONAL_PATTERNS, text):
        return False
    return True


# ---- SR1: permissive width extraction with negation/exclusion-cue handling ----

# Captures a number immediately adjacent to a width-indicating token, e.g.
# "WIDTH == 24", "WIDTH=16", "24-bit", "16 bit", "width of 24". We record the
# match span so we can inspect a surrounding window of text for negation cues.
WIDTH_NUM_PATTERNS = [
    r"\bwidth\s*(?:==|=|is|of|:)?\s*(\d{1,3})\b",
    r"\b(\d{1,3})[\s-]*bit\b",
]

# Cue phrases indicating the nearby width number is being named as UNAFFECTED /
# excluded / spec-compliant, not as an affected/anomalous width. Checked within
# a bounded window of characters around the numeric token (on either side),
# since natural phrasing may place the cue before or after the number
# (e.g. "not present for WIDTH=8" or "WIDTH=16 is unaffected").
NEGATION_CUE_PATTERNS = [
    r"not\s+present",
    r"not\s+active",
    r"not\s+affected",
    r"inactive",
    r"other\s+than",
    r"unlike",
    r"not\s+for\b",
    r"excluding",
    r"absent\s+for",
    r"not\s+the\s+default",
    r"unaffected",
    r"compliant",
    r"spec-compliant",
    r"spec\s+compliant",
    r"honest",
    r"default\b",
    r"\bor\s+16\b",
    r"\bor\s+8\b",
    r"\bnor\s+16\b",
    r"\bnor\s+8\b",
    r"correct(?:ly)?\b",
    r"standard\b",
    r"normal\b",
    r"legal\s+width",
    r"any\s+other\s+(?:legal\s+)?width",
]

# Window (in characters) scanned on each side of a numeric-width match to look
# for negation cues. Generous enough to cover realistic parenthetical/negated
# clause phrasing without spilling into unrelated sentences.
NEGATION_WINDOW = 60


def _extract_width_tokens_with_spans(text):
    """Return list of (width_int, match_start, match_end) for every width-like
    numeric token found in text."""
    tokens = []
    for p in WIDTH_NUM_PATTERNS:
        for m in re.finditer(p, text):
            try:
                w = int(m.group(1))
            except Exception:
                continue
            tokens.append((w, m.start(), m.end()))
    return tokens


def _is_negated_context(text, start, end):
    """Check whether a negation/exclusion cue phrase appears within a bounded
    window of characters surrounding the numeric-width token span."""
    lo = max(0, start - NEGATION_WINDOW)
    hi = min(len(text), end + NEGATION_WINDOW)
    window = text[lo:hi]
    for cue in NEGATION_CUE_PATTERNS:
        if re.search(cue, window):
            return True
    return False


def extract_affected_widths(text):
    """Extract the set of width values asserted as AFFECTED (i.e. not sitting
    within a negation/exclusion cue window). A width mentioned only in an
    excluded/negated context (e.g. 'not present for WIDTH=8/16') does not
    count as affected, even though its numeral appears in the text."""
    affected = set()
    for (w, start, end) in _extract_width_tokens_with_spans(text):
        if not _is_negated_context(text, start, end):
            affected.add(w)
    return affected


def finding_matches_sr1(f):
    """Extract the numeric width value(s) explicitly asserted as affected from
    affected_parameters/trigger_condition text, treating widths named only
    within a negation/exclusion cue window (e.g. 'not present for WIDTH=8 or
    16', 'inactive for WIDTH=16', 'unlike WIDTH=8') as excluded rather than
    affected. Require the resulting affected-width set to equal exactly {24}.
    A width asserted as affected outside of any negation context (e.g. a
    finding that genuinely claims WIDTH=16 is also affected) still causes
    rejection."""
    text = text_of(f, "affected_parameters", "trigger_condition")
    widths = extract_affected_widths(text)
    if widths != {24}:
        return False

    # Cross-check: the finding must not, elsewhere (payload_effect/rationale),
    # assert uniform/all-width applicability that would contradict the
    # width-specific claim.
    full_text = text_of(f, "affected_parameters", "trigger_condition", "payload_effect", "rationale")
    if any_match(UNIFORM_CLAIM_PATTERNS, full_text):
        return False

    return True


# ---- SR2: conjunctive pointer-pattern + write-attempt + near-full boundary ----

POINTER_PATTERN_TERMS = [
    r"\b(?:write\s*)?pointer\b.{0,40}(?:pattern|bit|low\s*bit)",
    r"\bwr_ptr\[?2:0\]?\s*==?\s*3?'?b?\s*101\b",
    r"\b3'b\s*101\b",
    r"\blow\s*3?\s*bits?\b.{0,30}101",
    r"\bpointer\s*(?:low\s*bits?|alignment|offset)\b",
    r"\bbit\s*pattern\b",
    r"\boccupancy\s*(?:pattern|signature)\b",
    r"\brare\s+(?:pointer|occupancy)\b",
]

NEARFULL_TERMS = [
    r"\bnear[\s-]*full\b",
    r"\balmost[\s-]*full\b",
    r"\bcount\s*==?\s*depth\s*-\s*1\b",
    r"\bone\s+(?:slot|entry|word)\s+(?:away\s+from|before)\s+full\b",
    r"\bone\s+less\s+than\s+(?:depth|full)\b",
    r"\bdepth\s*-\s*1\b",
    r"\bat\s+capacity\b",
]

WRITE_COINCIDENCE_TERMS = [
    r"\bwr_en\b",
    r"\bwrite\s*enable\b",
    r"\bwrite\s+(?:is\s+)?(?:attempted|asserted|occurring|coincident|simultaneous)\b",
    r"\bwhile\s+writing\b",
    r"\bsimultaneous(?:ly)?\s+with\s+(?:a\s+)?write\b",
    r"\bwrite\s+attempt\b",
]

# Vulnerability-adjacent mutant text: "the trojan fires under conditions of high
# occupancy and any write" / "more than half full" / "near full in general" /
# "high fill level" -- these broadened/generalized phrases must NOT satisfy the
# specific-pattern requirement, even though they superficially resemble the
# near-full or pointer-pattern concept. If present, they override/disqualify a
# match for the conjunctive check.
SR2_BROADENED_DENYLIST = [
    r"\bhigh\s+occupancy\b",
    r"\bmore\s+than\s+half\s+full\b",
    r"\bnear[\s-]*full\s+in\s+general\b",
    r"\bhigh\s+fill\s+level\b",
    r"\bmostly\s+full\b",
    r"\bgenerally\s+(?:near|almost)\s+full\b",
    r"\bany\s+write\b",
    r"\bany\s+occupancy\b",
]


def finding_matches_sr2(f):
    text = text_of(f, "trigger_condition")

    # A denylisted broadened phrase disqualifies this finding for SR2, since it
    # indicates the specific rare pattern/boundary condition has been swapped
    # out for a vague generalized claim, regardless of what else is present.
    if any_match(SR2_BROADENED_DENYLIST, text):
        return False

    has_pointer = any_match(POINTER_PATTERN_TERMS, text)
    has_nearfull = any_match(NEARFULL_TERMS, text)
    has_write = any_match(WRITE_COINCIDENCE_TERMS, text)
    return has_pointer and has_nearfull and has_write


FULL_SUPPRESSION_TERMS = [
    r"\bfull\b.{0,40}\b(?:deassert|suppress|clear|drop|incorrect(?:ly)?\s+(?:low|0|deasserted))",
    r"\b(?:deassert|suppress|clear)(?:s|ed|ion)?\b.{0,30}\bfull\b",
    r"\bfull\s+flag\b.{0,40}(?:wrong|incorrect|glitch|false|erroneous)",
    r"\bfalsely\s+(?:reports?|indicates?|shows?)\s+(?:not\s+)?full\b",
    r"\bfull\s*=\s*0\b.{0,20}(?:actual|really|truth)",
]

OVERWRITE_CONSEQUENCE_TERMS = [
    r"\bovel?rwrit(?:e|ten|ing)\b",
    r"\bunread\s+(?:data|entry|word)\b",
    r"\bdata\s+(?:corruption|loss)\b",
    r"\bcorrupt(?:ion|ed|s)?\b",
    r"\blos(?:e|s|t)\s+(?:the\s+)?(?:oldest|unread)\s*(?:data|word|entry)\b",
    r"\bextra\s+word\b.{0,30}(?:push|write|overwrit)",
    r"\bwraparound\s+collision\b",
]


def finding_matches_sr3(f):
    text = text_of(f, "payload_effect", "rationale")
    has_suppression = any_match(FULL_SUPPRESSION_TERMS, text)
    has_overwrite = any_match(OVERWRITE_CONSEQUENCE_TERMS, text)
    if not (has_suppression and has_overwrite):
        return False
    return True


def run_optional_cross_sim():
    """Best-effort, non-gating cross-simulation sanity check using iverilog/vvp.
    Any failure here is silently ignored and does not affect verdicts."""
    tb_path = "evaluation/tb_trigger_check.v"
    dut_path = "inputs/param_fifo.v"
    if not os.path.isfile(tb_path) or not os.path.isfile(dut_path):
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        sim_out = os.path.join(tmpdir, "sim.vvp")
        try:
            compile_proc = subprocess.run(
                ["iverilog", "-g2012", "-o", sim_out, dut_path, tb_path],
                capture_output=True, timeout=30, text=True
            )
            if compile_proc.returncode != 0:
                print("[INFO] cross-sim compile failed (non-gating): {}".format(
                    compile_proc.stderr.strip()[:200]))
                return
            run_proc = subprocess.run(
                ["vvp", sim_out],
                capture_output=True, timeout=30, text=True
            )
            out = run_proc.stdout
            if "PROBE:FULL_GLITCH=1" in out:
                print("[INFO] cross-sim confirms full-flag glitch/overwrite behavior at WIDTH=24 (non-gating)")
            elif "PROBE:FULL_GLITCH=0" in out:
                print("[INFO] cross-sim did not observe glitch under driven sequence (non-gating)")
            else:
                print("[INFO] cross-sim produced no PROBE output (non-gating)")
        except Exception as e:
            print("[INFO] cross-sim skipped due to error (non-gating): {}".format(e))


def finalize():
    failed = [rid for rid, ok, _ in RESULTS if not ok]
    missing = [rid for rid in ALL_REQ_IDS if rid not in [r for r, _, _ in RESULTS]]
    for rid in missing:
        record(rid, False, "requirement was not evaluated")

    if failed or missing:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()