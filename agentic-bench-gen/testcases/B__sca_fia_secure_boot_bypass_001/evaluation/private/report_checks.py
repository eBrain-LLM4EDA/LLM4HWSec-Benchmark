"""
Private substantive-content helper for the secure-boot vulnerability
report grader.

This module defines the keyword vocabulary used to judge whether a
submitted report's free-text narrative fields ('reason',
'exploit_scenario', 'technique', 'rationale', ...) contain a substantive
account of a bypass/fault scenario (SR1/SR2) or a substantive hardening
technique proposal (SR3), rather than generic or unrelated text.

These keyword lists are intentionally broad so that any genuine
description of the underlying vulnerability/mitigation is accepted
regardless of exact phrasing or wording style; they are kept private
(not documented in the participant-facing README) so participants are
not tempted to game the grader by keyword-stuffing without producing a
substantive analysis.
"""


# Keywords indicating that a narrative describes forcing/skipping a
# security-critical decision (fault injection bypassing a check).
_BYPASS_KEYWORDS = [
    "force",
    "forcing",
    "forced",
    "bypass",
    "bypassing",
    "bypassed",
    "skip",
    "skipping",
    "skipped",
    "without a valid",
    "without valid",
    "without a genuine",
    "without ever",
    "glitch",
    "glitching",
    "single-bit fault",
    "single bit fault",
    "bit-flip",
    "bit flip",
    "stuck-at",
    "stuck at",
    "inject",
    "injection",
    "injected",
    "circumvent",
    "circumventing",
    "spoof",
]

# Keywords indicating a substantive redundancy/complementary-invariant
# hardening technique.
_HARDENING_KEYWORDS = [
    "tmr",
    "redundan",  # matches redundant / redundancy
    "dual-rail",
    "dual rail",
    "complementary",
    "checksum",
    "voting",
    "vote",
    "triple modular",
    "triple-modular",
]


def is_bypass_language(text):
    """Return True iff the given text (any case) contains at least one
    keyword/phrase indicating that a security-critical decision was
    forced, bypassed, or skipped via a fault."""
    if not isinstance(text, str) or not text:
        return False
    lowered = text.lower()
    return any(keyword in lowered for keyword in _BYPASS_KEYWORDS)


def is_hardening_technique(text):
    """Return True iff the given text (any case) contains at least one
    keyword/phrase indicating a substantive redundancy-based or
    complementary-invariant hardening technique."""
    if not isinstance(text, str) or not text:
        return False
    lowered = text.lower()
    return any(keyword in lowered for keyword in _HARDENING_KEYWORDS)


def find_node(critical_nodes, signal_name):
    """Return the first entry in critical_nodes (a list of dicts) whose
    'signal' field exactly matches signal_name, or -- failing that --
    contains signal_name as a substring. Returns None if no entry
    matches either condition. Matching is case-sensitive, consistent
    with the requirement that submitted identifiers be literal
    substrings of the RTL text."""
    if not isinstance(critical_nodes, list) or not signal_name:
        return None

    for entry in critical_nodes:
        if isinstance(entry, dict) and entry.get("signal") == signal_name:
            return entry

    for entry in critical_nodes:
        if isinstance(entry, dict):
            sig = entry.get("signal")
            if isinstance(sig, str) and signal_name in sig:
                return entry

    return None


def find_hardening(hardening_list, signal_name):
    """Return the first entry in hardening_list (a list of dicts) whose
    'target_signal' field exactly matches signal_name, or -- failing
    that -- contains signal_name as a substring. Returns None if no
    entry matches either condition. Matching is case-sensitive."""
    if not isinstance(hardening_list, list) or not signal_name:
        return None

    for entry in hardening_list:
        if isinstance(entry, dict) and entry.get("target_signal") == signal_name:
            return entry

    for entry in hardening_list:
        if isinstance(entry, dict):
            tgt = entry.get("target_signal")
            if isinstance(tgt, str) and signal_name in tgt:
                return entry

    return None