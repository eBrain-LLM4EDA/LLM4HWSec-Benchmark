#!/usr/bin/env python3
"""
evaluate.py -- Grader for rtl_trojan_detection_key_zeroize_hold_001

Grades submission/trojan_report.json against the hidden ground truth
regarding the zeroize/bus_busy masking Trojan in inputs/key_loader_ctrl.v.

Python stdlib only. Deterministic. Exits 0 iff all requirements PASS.
"""

import json
import os
import re
import sys

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]

RTL_PATH = "inputs/key_loader_ctrl.v"
SUBMISSION_PATH = "submission/trojan_report.json"

results = {}  # id -> (bool, reason)


def record(req_id, ok, reason=""):
    results[req_id] = (ok, reason)
    if ok:
        print("[TEST] PASS: %s" % req_id)
    else:
        print("[TEST] FAIL: %s: %s" % (req_id, reason))


def fail_all_setup(reason):
    for rid in REQUIREMENT_IDS:
        record(rid, False, reason)


# ---------------------------------------------------------------------
# Load inputs/key_loader_ctrl.v (used for SR4 dynamic localization check)
# ---------------------------------------------------------------------

if not os.path.isfile(RTL_PATH):
    print("[TEST] FAIL: SETUP: %s not found" % RTL_PATH)
    sys.exit(1)

with open(RTL_PATH, "r", encoding="utf-8") as f:
    rtl_lines = f.readlines()

# Locate the actual offending construct lines dynamically (not hardcoded
# values, just search patterns over the real file content).
zeroize_mask_line = None
zeroize_block_line = None
key_q_next_lines = []

for idx, line in enumerate(rtl_lines, start=1):
    low = line.lower()
    if "zeroize_mask" in low and zeroize_mask_line is None and ("assign" in low or "wire" in low):
        zeroize_mask_line = idx
    if "zeroize_block" in low and zeroize_block_line is None:
        zeroize_block_line = idx
    if "key_q_next" in low:
        key_q_next_lines.append(idx)

# Fallback: if zeroize_mask_line wasn't found via assign/wire keyword search,
# just find first occurrence of the token.
if zeroize_mask_line is None:
    for idx, line in enumerate(rtl_lines, start=1):
        if "zeroize_mask" in line.lower():
            zeroize_mask_line = idx
            break

# Build the "true construct" line range spanning zeroize_mask decl through
# the end of the zeroize_block always block (or key_q_next lines) as a
# reasonable localization target window.
candidate_true_lines = [l for l in [zeroize_mask_line, zeroize_block_line] if l is not None]
candidate_true_lines.extend(key_q_next_lines)
if candidate_true_lines:
    true_line_min = min(candidate_true_lines)
    true_line_max = max(candidate_true_lines)
else:
    # Should not happen given the ground-truth artifact, but guard anyway.
    true_line_min, true_line_max = 1, len(rtl_lines)

LOCALIZATION_TOKENS = [
    "zeroize_mask",
    "zeroize_block",
    "key_q_next",
    "always @(*)",
    "always @ (*)",
]

# ---------------------------------------------------------------------
# Load submission
# ---------------------------------------------------------------------

if not os.path.isfile(SUBMISSION_PATH):
    fail_all_setup("%s not found" % SUBMISSION_PATH)
    sys.exit(1)

with open(SUBMISSION_PATH, "r", encoding="utf-8") as f:
    raw_text = f.read()

try:
    report = json.loads(raw_text)
except Exception as e:
    fail_all_setup("submission/trojan_report.json is not valid JSON: %s" % e)
    sys.exit(1)

# ---------------------------------------------------------------------
# FR1: top-level structure
# ---------------------------------------------------------------------

fr1_ok = True
fr1_reason = ""

if not isinstance(report, dict):
    fr1_ok = False
    fr1_reason = "top-level JSON is not an object"
else:
    candidates = report.get("candidates", None)
    summary = report.get("summary", None)
    tool_version = report.get("tool_version_or_method", None)

    if not isinstance(candidates, list) or len(candidates) == 0:
        fr1_ok = False
        fr1_reason = "'candidates' missing, not a list, or empty"
    elif not isinstance(summary, str):
        fr1_ok = False
        fr1_reason = "'summary' missing or not a string"
    elif not isinstance(tool_version, str):
        fr1_ok = False
        fr1_reason = "'tool_version_or_method' missing or not a string"

record("FR1", fr1_ok, fr1_reason)

if not fr1_ok:
    # Cannot meaningfully evaluate the rest without valid structure.
    for rid in ["FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]:
        record(rid, False, "skipped due to FR1 failure: %s" % fr1_reason)
    sys.exit(1)

candidates = report["candidates"]
summary = report["summary"]

# ---------------------------------------------------------------------
# FR2: each candidate has required fields with correct types
# ---------------------------------------------------------------------

fr2_ok = True
fr2_reason = ""

REQUIRED_CAND_FIELDS = {
    "signal_or_net": str,
    "location_hint": str,
    "trigger_condition": str,
    "confidence": (int, float),
}

for i, cand in enumerate(candidates):
    if not isinstance(cand, dict):
        fr2_ok = False
        fr2_reason = "candidate[%d] is not an object" % i
        break
    for field, expected_type in REQUIRED_CAND_FIELDS.items():
        if field not in cand:
            fr2_ok = False
            fr2_reason = "candidate[%d] missing field '%s'" % (i, field)
            break
        val = cand[field]
        if field == "confidence":
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                fr2_ok = False
                fr2_reason = "candidate[%d].confidence is not a number" % i
                break
            if not (0.0 <= float(val) <= 1.0):
                fr2_ok = False
                fr2_reason = "candidate[%d].confidence=%r out of [0,1]" % (i, val)
                break
        else:
            if not isinstance(val, str):
                fr2_ok = False
                fr2_reason = "candidate[%d].%s is not a string" % (i, field)
                break
    if not fr2_ok:
        break

record("FR2", fr2_ok, fr2_reason)

if not fr2_ok:
    for rid in ["FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]:
        record(rid, False, "skipped due to FR2 failure: %s" % fr2_reason)
    sys.exit(1)

# ---------------------------------------------------------------------
# Helper keyword sets
# ---------------------------------------------------------------------

BUS_BUSY_TERMS = [
    "bus_busy",
    "bus busy",
    "bus-busy",
    "busy",
    "bus transaction in progress",
    "bus transaction is in progress",
    "transaction in flight",
    "in-flight transaction",
    "transaction in progress",
]

MASK_GATE_TERMS = [
    "mask",
    "gate",
    "gated",
    "gating",
    "and with",
    "anded",
    "combinational",
    "&",
    "suppress",
    "suppresses",
    "inhibit",
    "inhibits",
    "block",
    "blocks",
    "blocked",
]

SELF_HOLD_TERMS = [
    "key_q",
    "self",
    "retain",
    "retains",
    "retained",
    "hold",
    "holds",
    "holding",
    "previous value",
    "own value",
    "own current value",
    "unchanged",
    "stale",
]

WRONG_ROOT_CAUSE_TERMS = [
    "reset synchronizer",
    "synchronizer",
    "clock domain crossing",
    "cdc",
    "metastability",
    "power-on",
    "power on reset",
    "glitch on rst_n",
    "rst_n glitch",
    "reset resynchronization",
    "reset-domain",
    "reset domain crossing",
]

# Terms indicating a different (wrong) faulty data source than key_q self-hold
WRONG_DATA_SOURCE_TERMS = [
    "bus_data is loaded",
    "loads bus_data",
    "loaded from bus_data instead",
    "bus_data instead of key_q",
]

ZERO_VALUE_TERMS = [
    "32'b0",
    "32'h0",
    "32'd0",
    "all zero",
    "all-zero",
    "all zeros",
    "should be 0",
    "should equal 0",
    "should be zero",
    "should clear to zero",
    "becomes 0",
    "become 0",
    "cleared to 0",
    "zeroed",
    "value of 0",
    "equal to zero",
]

# Explicit non-zero constant patterns that would indicate a corrupted/wrong
# expected-value claim (e.g. all-ones, arbitrary nonzero hex/decimal literal).
NONZERO_CONST_PATTERNS = [
    re.compile(r"32'h[fF]{8}\b"),          # 32'hFFFFFFFF
    re.compile(r"32'b1{32}\b"),             # 32'b11111111...1 (32 ones)
    re.compile(r"\ball[- ]?ones\b"),
    re.compile(r"\b0xffffffff\b", re.IGNORECASE),
    re.compile(r"32'd[1-9]\d*\b"),          # 32'd<nonzero decimal>
    re.compile(r"32'h[0-9a-fA-F]*[1-9a-fA-F][0-9a-fA-F]*\b"),  # any nonzero hex literal e.g. 32'hDEAD
]


def text_of(cand):
    parts = [
        str(cand.get("signal_or_net", "")),
        str(cand.get("location_hint", "")),
        str(cand.get("trigger_condition", "")),
    ]
    return " ".join(parts).lower()


def contains_any(text, terms):
    return any(t in text for t in terms)


def trigger_text_of(cand):
    return str(cand.get("trigger_condition", "")).lower()


def mentions_zeroize(text):
    return "zeroize" in text


def mentions_bus_busy_concept(text):
    return contains_any(text, BUS_BUSY_TERMS)


def is_conjunctive_zeroize_busbusy(cand):
    """SR1-style check: trigger_condition must reference BOTH zeroize and
    a bus_busy/transaction-in-progress concept, not just one alone."""
    trig = trigger_text_of(cand)
    if not mentions_zeroize(trig):
        return False
    if not mentions_bus_busy_concept(trig):
        return False
    return True


# ---------------------------------------------------------------------
# Summary sentence splitting + scoping helpers (for FR4 / SR2 rewrite)
#
# We scope a candidate's "own text" to: its own JSON fields
# (signal_or_net + location_hint + trigger_condition) PLUS any sentence
# in the free-text 'summary' field that references that candidate's
# location_hint token or signal_or_net token. This prevents a claim made
# about a *different* candidate elsewhere in the summary from leaking
# into the top candidate's scoped evaluation text (and vice versa).
# ---------------------------------------------------------------------

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def split_sentences(text):
    if not text:
        return []
    parts = _SENTENCE_SPLIT_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def candidate_reference_tokens(cand):
    """Build a small set of lowercase substrings that would identify
    sentences in the summary as being 'about' this candidate."""
    tokens = set()
    loc = str(cand.get("location_hint", "")).strip().lower()
    sig = str(cand.get("signal_or_net", "")).strip().lower()
    if loc:
        tokens.add(loc)
        # Also add individual meaningful words (len>=4) from location_hint
        for word in re.findall(r"[a-z0-9_]{4,}", loc):
            tokens.add(word)
    if sig:
        tokens.add(sig)
        for word in re.findall(r"[a-z0-9_]{4,}", sig):
            tokens.add(word)
    return tokens


def scoped_text_for_candidate(cand, summary_text):
    """Return the lowercase text scope for this candidate: its own three
    text fields, plus any summary sentence referencing one of its
    reference tokens (location_hint/signal_or_net or significant
    substrings thereof)."""
    own = text_of(cand)
    tokens = candidate_reference_tokens(cand)
    matched_sentences = []
    if tokens:
        for sent in split_sentences(summary_text):
            sent_low = sent.lower()
            for tok in tokens:
                if tok and tok in sent_low:
                    matched_sentences.append(sent_low)
                    break
    return own + " " + " ".join(matched_sentences)


def scoped_expected_value_state(scoped_text):
    """Return one of: 'zero', 'nonzero', 'absent' describing the
    expected-value claim found within scoped_text."""
    has_zero_claim = contains_any(scoped_text, ZERO_VALUE_TERMS)
    has_nonzero_claim = any(p.search(scoped_text) for p in NONZERO_CONST_PATTERNS)
    # A zero literal like 32'b0 might accidentally match a nonzero hex
    # pattern that is overly broad; the generic nonzero hex pattern
    # explicitly requires at least one nonzero hex digit, so 32'h0 will
    # not match it. Still, prefer explicit disambiguation: if a zero
    # term is present and it's the *only* explicit constant mentioned,
    # treat as zero even if a coincidental broad match occurs elsewhere
    # referencing a different candidate's constant (already excluded by
    # scoping).
    if has_nonzero_claim and not has_zero_claim:
        return "nonzero"
    if has_nonzero_claim and has_zero_claim:
        # Both zero and nonzero literals appear in scope -- ambiguous /
        # contradictory claim for this candidate; treat conservatively
        # as not a clean zero claim.
        return "ambiguous"
    if has_zero_claim:
        return "zero"
    return "absent"


def describes_mask_gate_and_self_hold(scoped_text):
    """SR2-style check: scoped text must describe combinational
    masking/gating of zeroize feeding key_q next-state, AND describe
    key_q retaining/holding its own value in the faulty branch, and must
    NOT attribute the cause to an unrelated mechanism."""
    has_gate = contains_any(scoped_text, MASK_GATE_TERMS)
    has_zeroize = "zeroize" in scoped_text
    has_busbusy_ref = contains_any(scoped_text, BUS_BUSY_TERMS)
    has_self_hold = contains_any(scoped_text, SELF_HOLD_TERMS) and (
        "key_q" in scoped_text or "key register" in scoped_text or "key" in scoped_text
    )
    has_wrong_cause = contains_any(scoped_text, WRONG_ROOT_CAUSE_TERMS)
    has_wrong_source = contains_any(scoped_text, WRONG_DATA_SOURCE_TERMS)
    if has_wrong_cause or has_wrong_source:
        return False
    return has_gate and has_zeroize and has_busbusy_ref and has_self_hold


# ---------------------------------------------------------------------
# FR3: at least one candidate's trigger_condition mentions conjunction
# of zeroize-asserted term AND bus_busy/transaction-in-progress term
# ---------------------------------------------------------------------

fr3_ok = False
fr3_candidates_idx = []
for i, cand in enumerate(candidates):
    if is_conjunctive_zeroize_busbusy(cand):
        fr3_ok = True
        fr3_candidates_idx.append(i)

record(
    "FR3",
    fr3_ok,
    "" if fr3_ok else "no candidate's trigger_condition mentions both zeroize AND bus_busy/transaction-in-progress",
)

# ---------------------------------------------------------------------
# Determine top-confidence candidate (sorted by confidence desc, stable
# on original array order for ties)
# ---------------------------------------------------------------------

def conf_of(cand):
    try:
        return float(cand.get("confidence", 0.0))
    except Exception:
        return 0.0

sorted_candidates = sorted(
    enumerate(candidates), key=lambda pair: conf_of(pair[1]), reverse=True
)
top_idx, top_cand = sorted_candidates[0]
top_scoped_text = scoped_text_for_candidate(top_cand, summary)

# ---------------------------------------------------------------------
# FR4 (rewritten): the top-confidence candidate's OWN scoped expected-
# value claim must explicitly be zero; FAIL if it states a different
# explicit constant, or if no expected-value claim is present at all.
# ---------------------------------------------------------------------

fr4_state = scoped_expected_value_state(top_scoped_text)
fr4_ok = (fr4_state == "zero")
if fr4_ok:
    fr4_reason = ""
elif fr4_state == "nonzero":
    fr4_reason = "top-confidence candidate's scoped text states a non-zero expected value for key_q under the trigger (expected 32'b0)"
elif fr4_state == "ambiguous":
    fr4_reason = "top-confidence candidate's scoped text contains conflicting zero/non-zero expected-value claims"
else:
    fr4_reason = "top-confidence candidate's own text/summary does not state that key_q should equal 0/32'b0 under the identified trigger"

record("FR4", fr4_ok, fr4_reason)

# ---------------------------------------------------------------------
# SR1: some qualifying candidate (top-or-any) must have a genuinely
# conjunctive trigger_condition (zeroize AND bus_busy), not either alone,
# and not a generic single-signal claim.
# ---------------------------------------------------------------------

sr1_ok = False
sr1_reason = ""
if not fr3_candidates_idx:
    sr1_reason = "no candidate expresses the zeroize AND bus_busy conjunction (baseline-style generic 'zeroize asserted' claims fail this)"
else:
    sr1_ok = True
    for i in fr3_candidates_idx:
        trig = trigger_text_of(candidates[i])
        if not (mentions_zeroize(trig) and mentions_bus_busy_concept(trig)):
            sr1_ok = False
            sr1_reason = "candidate[%d] trigger_condition does not truly conjoin zeroize and bus_busy" % i
            break

record("SR1", sr1_ok, sr1_reason)

# ---------------------------------------------------------------------
# SR2 (rewritten): evaluate root-cause correctness using ONLY the
# top-confidence candidate's scoped text (its own fields + summary
# sentences that reference it). Does not consider other candidates'
# text at all, so unrelated masking vocabulary elsewhere in the report
# cannot rescue a top candidate whose own root-cause narrative is wrong.
# ---------------------------------------------------------------------

sr2_ok = describes_mask_gate_and_self_hold(top_scoped_text)
if sr2_ok:
    sr2_reason = ""
else:
    has_wrong_cause = contains_any(top_scoped_text, WRONG_ROOT_CAUSE_TERMS)
    has_wrong_source = contains_any(top_scoped_text, WRONG_DATA_SOURCE_TERMS)
    if has_wrong_cause:
        sr2_reason = "top-confidence candidate's own root-cause narrative attributes the defect to an unrelated mechanism (e.g. reset synchronization/CDC/metastability) rather than zeroize-gating"
    elif has_wrong_source:
        sr2_reason = "top-confidence candidate's own narrative describes the faulty branch selecting a different data source (e.g. bus_data) rather than key_q self-hold"
    else:
        sr2_reason = "top-confidence candidate's own text does not describe combinational zeroize masking/gating by a bus_busy-derived term plus key_q self-hold as root cause"

record("SR2", sr2_ok, sr2_reason)

# ---------------------------------------------------------------------
# SR3: highest-confidence candidate (numeric) must satisfy SR1's
# conjunction requirement AND SR2's scoped root-cause requirement,
# with confidence >= 0.6.
# ---------------------------------------------------------------------

top_conf = conf_of(top_cand)
top_satisfies_sr1 = top_idx in fr3_candidates_idx
top_is_qualifying = top_satisfies_sr1 and sr2_ok

sr3_ok = top_is_qualifying and (top_conf >= 0.6)
sr3_reason = ""
if not top_is_qualifying:
    sr3_reason = "highest-confidence candidate (index %d) is not the zeroize/bus_busy root-cause candidate" % top_idx
elif top_conf < 0.6:
    sr3_reason = "highest-confidence candidate's confidence %.3f is below 0.6 threshold" % top_conf

record("SR3", sr3_ok, sr3_reason)

# ---------------------------------------------------------------------
# SR4: location_hint of a qualifying candidate must fuzzy-match the
# actual zeroize_mask/zeroize_block construct in inputs/key_loader_ctrl.v,
# either via substring token match or overlapping line range.
# ---------------------------------------------------------------------

def parse_line_range(text):
    """Extract candidate (min,max) line numbers mentioned in text, if any."""
    nums = [int(n) for n in re.findall(r"\b(\d{1,4})\b", text)]
    if not nums:
        return None
    return (min(nums), max(nums))


def location_matches(cand):
    loc = str(cand.get("location_hint", ""))
    loc_low = loc.lower()
    for tok in LOCALIZATION_TOKENS:
        if tok in loc_low:
            return True
    rng = parse_line_range(loc)
    if rng is not None:
        lo, hi = rng
        tol = 3
        if not (hi < (true_line_min - tol) or lo > (true_line_max + tol)):
            return True
    return False


sr2_qualifying_idx = [
    i for i, c in enumerate(candidates)
    if describes_mask_gate_and_self_hold(scoped_text_for_candidate(c, summary))
]

sr4_candidates_idx = [
    i for i in (set(fr3_candidates_idx) & set(sr2_qualifying_idx))
    if location_matches(candidates[i])
]

if not sr4_candidates_idx:
    for i in set(fr3_candidates_idx) | set(sr2_qualifying_idx):
        if location_matches(candidates[i]):
            sr4_candidates_idx.append(i)

sr4_ok = len(sr4_candidates_idx) > 0
record(
    "SR4",
    sr4_ok,
    "" if sr4_ok else "no qualifying candidate's location_hint matches the actual zeroize_mask/zeroize_block construct (token or line-range match)",
)

# ---------------------------------------------------------------------
# Final verdict
# ---------------------------------------------------------------------

all_pass = all(ok for ok, _ in results.values())
sys.exit(0 if all_pass else 1)