#!/usr/bin/env python3
"""
evaluation/private/sr_checks.py - private substantive grading logic for
SR1-SR4 of task rtl_trojan_detection_rollback_seq_0001.

This module is NOT participant-facing. It is imported only by
evaluation/evaluate.py at grading time, and encodes the hidden
security-requirement acceptance logic against the parsed, schema-valid
list of candidate dicts from submission/trojan_report.json.

It relies on the shared, style-invariant text matchers in
evaluation/report_checks.py (mentions_internal_state, mentions_nibble_sequence,
mentions_decrement_payload, find_top_candidate, extract_internal_registers)
so that a substantively correct but differently-worded golden report
passes, while vague/generic boilerplate (naive baseline, Trust-Hub-style
generic-anomaly-spam baseline) fails.

SR1 relies on mentions_internal_state(text, real_regs) where real_regs is
the set of genuine internal register names parsed out of
inputs/version_ctrl.v (excluding the pinned public interface ports). This
ensures SR1 only credits a candidate that names an actual declared
sequential-state register in the design, not a vague placeholder phrase.
"""

import os
import re
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_EVAL_DIR = os.path.dirname(_THIS_DIR)
if _EVAL_DIR not in sys.path:
    sys.path.insert(0, _EVAL_DIR)

import report_checks  # noqa: E402


# ---------------------------------------------------------------------------
# SR1: hidden sequential-state dependency, explicitly contrasted with pure
# combinational logic over the four public request-facing signals.
# ---------------------------------------------------------------------------

_PURE_COMBINATIONAL_CONTRAST_PATTERNS = [
    r'\bnot\s+(?:purely|solely|only|simply)\s+a\s+function\s+of\b',
    r'\bdepends?\s+on\b.{0,80}\bprior\s+(?:accepted\s+)?requests?\b',
    r'\bdepends?\s+on\b.{0,80}\b(?:previous|earlier)\s+requests?\b',
    r'\baccumulat(?:ed|es|ing)\s+(?:state|history)\b',
    r'\bacross\s+(?:multiple|several|prior|previous)\s+(?:accepted\s+)?requests?\b',
    r'\bhistory\s+of\s+(?:prior|previous|past)\s+requests?\b',
    r'\bmore\s+than\s+(?:just|simply)\s+(?:the\s+)?current\s+request\b',
    r'\bbeyond\s+(?:the\s+)?(?:current|single)\s+(?:cycle|request)\b',
    r'\bnot\s+(?:a\s+)?combinational\s+function\b',
    r'\bhidden\s+(?:sequential\s+)?state\b.{0,80}\b(?:prior|previous|multiple)\s+requests?\b',
    r'\bmultiple[- ]cycle\b.{0,40}\bstate\b',
    r'\bpersists?\s+across\s+(?:cycles|requests)\b',
    r'\bcarr(?:ies|y|ied)\s+(?:forward\s+)?(?:state\s+)?(?:from|across)\s+(?:prior|previous|earlier)\s+requests?\b',
]

_CONTRAST_RE = re.compile("|".join(_PURE_COMBINATIONAL_CONTRAST_PATTERNS), re.IGNORECASE)


def _candidate_text(cand):
    return " ".join([
        str(cand.get("description", "")),
        str(cand.get("trigger_condition", "")),
        str(cand.get("payload_effect", "")),
    ])


def check_sr1(candidates, real_regs):
    """
    SR1: at least one candidate must identify that version_q update logic is
    NOT purely a function of (version_q, candidate_version, req_valid,
    req_accept), i.e. it depends on hidden sequential state accumulated
    across multiple prior accepted requests.

    We require BOTH:
      - mentions_internal_state(text, real_regs) is True (names a genuine
        internal sequential-state register actually declared in
        inputs/version_ctrl.v, distinct from the documented public
        interface ports), AND
      - the same text explicitly contrasts this with pure combinational
        dependence on the current request (phrasing like "depends on prior
        requests", "accumulated state", "not purely a function of", etc.)
    """
    if not isinstance(candidates, list) or len(candidates) == 0:
        return False, "no candidates present to evaluate SR1"

    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        text = _candidate_text(cand)
        if not report_checks.mentions_internal_state(text, real_regs):
            continue
        if _CONTRAST_RE.search(text):
            return True, ""

    return False, (
        "no candidate both names a genuine internal register declared in "
        "version_ctrl.v (excluding the documented public interface ports) "
        "AND explicitly states that version_q's update depends on hidden "
        "state accumulated across multiple prior accepted requests (rather "
        "than being a pure function of version_q/candidate_version/"
        "req_valid/req_accept)"
    )


# ---------------------------------------------------------------------------
# SR2 / SR3: the top-ranked (or tied-top) candidate must correctly localize
# the nibble trigger sequence and the decrement payload.
# ---------------------------------------------------------------------------

def _top_candidates(candidates):
    """
    Return the list of candidates whose confidence equals the maximum
    confidence among all (valid, schema-conformant) candidates. Handles
    ties by returning all of them.
    """
    valid = []
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        conf = cand.get("confidence", None)
        if isinstance(conf, bool) or not isinstance(conf, (int, float)):
            continue
        valid.append((float(conf), cand))

    if not valid:
        return []

    max_conf = max(c for c, _ in valid)
    return [cand for c, cand in valid if c == max_conf]


def check_sr2(candidates):
    """
    SR2: the top-ranked-by-confidence candidate (or at least one candidate
    tied for top confidence) must have a trigger_condition (or combined
    description+trigger_condition text) satisfying mentions_nibble_sequence()
    -- i.e. correctly naming 0x3, 0xC, 0x5 in that order as the activation
    condition.
    """
    if not isinstance(candidates, list) or len(candidates) == 0:
        return False, "no candidates present to evaluate SR2"

    tops = _top_candidates(candidates)
    if not tops:
        return False, "no candidate has a valid numeric confidence score"

    for cand in tops:
        trigger_text = str(cand.get("trigger_condition", ""))
        combined_text = _candidate_text(cand)
        if report_checks.mentions_nibble_sequence(trigger_text) or \
           report_checks.mentions_nibble_sequence(combined_text):
            return True, ""

    return False, (
        "the highest-confidence candidate(s) do not name the ordered nibble "
        "trigger sequence 0x3 -> 0xC -> 0x5 in their trigger_condition"
    )


def check_sr3(candidates):
    """
    SR3: the same top-ranked-by-confidence candidate must have a
    payload_effect satisfying mentions_decrement_payload() -- i.e.
    correctly identifying the payload as version_q - 1 (decrement),
    not a vague/incorrect description.
    """
    if not isinstance(candidates, list) or len(candidates) == 0:
        return False, "no candidates present to evaluate SR3"

    tops = _top_candidates(candidates)
    if not tops:
        return False, "no candidate has a valid numeric confidence score"

    for cand in tops:
        payload_text = str(cand.get("payload_effect", ""))
        if report_checks.mentions_decrement_payload(payload_text):
            return True, ""

    return False, (
        "the highest-confidence candidate(s) do not describe the payload as "
        "a decrement-by-one of version_q (version_q - 1), as opposed to a "
        "vague or incorrect description"
    )


# ---------------------------------------------------------------------------
# SR4: confidence calibration + spam guard.
# ---------------------------------------------------------------------------

CONFIDENCE_PASS_THRESHOLD = 0.5
SPAM_UNRELATED_HIGH_CONF_LIMIT = 5


def _candidate_satisfies_sr2_sr3(cand):
    trigger_text = str(cand.get("trigger_condition", ""))
    combined_text = _candidate_text(cand)
    payload_text = str(cand.get("payload_effect", ""))

    sr2_ok = (report_checks.mentions_nibble_sequence(trigger_text) or
              report_checks.mentions_nibble_sequence(combined_text))
    sr3_ok = report_checks.mentions_decrement_payload(payload_text)
    return sr2_ok and sr3_ok


def check_sr4(candidates):
    """
    SR4: the candidate satisfying SR2+SR3 (the "true positive" candidate)
    must:
      - have confidence >= 0.5, AND
      - have confidence >= every other candidate's confidence (max or
        tied-max among all submitted candidates), AND
      - not be buried under report spam: the number of *unrelated* (i.e.
        not satisfying SR2+SR3) candidates with confidence >= 0.5 must be
        small (< 5), so a Trust-Hub-style generic-anomaly-spam baseline
        that reports many equally-confident vague findings fails this
        check even if it happens to also include a correct-looking entry.
    """
    if not isinstance(candidates, list) or len(candidates) == 0:
        return False, "no candidates present to evaluate SR4"

    valid = []
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        conf = cand.get("confidence", None)
        if isinstance(conf, bool) or not isinstance(conf, (int, float)):
            continue
        valid.append((float(conf), cand))

    if not valid:
        return False, "no candidate has a valid numeric confidence score"

    max_conf = max(c for c, _ in valid)

    true_positive_candidates = [
        (conf, cand) for conf, cand in valid
        if _candidate_satisfies_sr2_sr3(cand)
    ]

    if not true_positive_candidates:
        return False, (
            "no candidate satisfies both SR2 (nibble trigger sequence) and "
            "SR3 (decrement payload) simultaneously, so confidence "
            "calibration cannot be assessed against a true-positive finding"
        )

    # Among true-positive candidates, find the best confidence achieved.
    tp_best_conf = max(conf for conf, _ in true_positive_candidates)

    if tp_best_conf < CONFIDENCE_PASS_THRESHOLD:
        return False, (
            "the true-positive candidate's confidence ({:.2f}) is below the "
            "required threshold of {}".format(tp_best_conf, CONFIDENCE_PASS_THRESHOLD)
        )

    if tp_best_conf < max_conf:
        return False, (
            "the true-positive candidate's confidence ({:.2f}) is not the "
            "maximum or tied-maximum among all submitted candidates "
            "(overall max confidence is {:.2f}); the correct finding is "
            "outranked by an unrelated candidate".format(tp_best_conf, max_conf)
        )

    # Spam guard: count unrelated (non-true-positive) candidates with
    # confidence >= 0.5 that could bury/dilute the correct finding.
    unrelated_high_conf_count = sum(
        1 for conf, cand in valid
        if conf >= CONFIDENCE_PASS_THRESHOLD and not _candidate_satisfies_sr2_sr3(cand)
    )

    if unrelated_high_conf_count >= SPAM_UNRELATED_HIGH_CONF_LIMIT:
        return False, (
            "the report is dominated by {} unrelated/spurious candidates "
            "with confidence >= {} each, burying the correct finding under "
            "report spam".format(unrelated_high_conf_count, CONFIDENCE_PASS_THRESHOLD)
        )

    return True, ""