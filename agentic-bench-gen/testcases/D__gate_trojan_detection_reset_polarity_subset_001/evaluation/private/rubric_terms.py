#!/usr/bin/env python3
"""
evaluation/private/rubric_terms.py

Private rubric-term lists and matcher used by evaluate.py to grade SR3:
anomaly_description must substantively characterize the defect as an
inverted/complemented reset polarity, not merely mention "reset" in some
generic/unrelated way.

The matcher requires at least one RESET_TERMS token AND at least one
POLARITY_TERMS token to both appear, and additionally requires they be
"close" to each other (same sentence) when the text contains multiple
sentences -- falling back to whole-string co-occurrence when sentence
splitting doesn't help (e.g. a single-sentence description, or terms that
are simply not separated by sentence punctuation at all).
"""

import re

# Tokens indicating the description is talking about the reset mechanism.
RESET_TERMS = [
    "reset",
    "rstn",
    "rst_n",
    "rst",
    "reset net",
    "reset signal",
    "reset path",
    "reset pin",
    "reset polarity",
]

# Tokens indicating the description is talking about an inversion /
# polarity-complement mechanism.
POLARITY_TERMS = [
    "invert",
    "inverted",
    "inverting",
    "inverter",
    "inversion",
    "complement",
    "complemented",
    "complementary",
    "polarity",
    "active-high",
    "active high",
    "active-low",
    "active low",
    "flipped",
    "flip",
    "negated",
    "negation",
    "opposite polarity",
    "not(rstn)",
    "logically inverted",
]

_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?;\n])\s+')


def _contains_any(text_lower, terms):
    return [t for t in terms if t in text_lower]


def has_inversion_claim(text):
    """
    Return True if `text` substantively claims an inverted/complemented
    reset polarity defect: i.e. it contains at least one reset-related
    term AND at least one polarity/inversion-related term, and those
    terms are reasonably co-located (same sentence) when the text can be
    split into multiple sentences. If sentence splitting yields only a
    single segment (or no segment contains both kinds of term while the
    whole string does), fall back to whole-string co-occurrence.
    """
    if not text:
        return False

    text_lower = text.lower()

    reset_hits = _contains_any(text_lower, RESET_TERMS)
    polarity_hits = _contains_any(text_lower, POLARITY_TERMS)

    if not reset_hits or not polarity_hits:
        return False

    # Try sentence-level co-location first for a stronger signal.
    sentences = _SENTENCE_SPLIT_RE.split(text_lower)
    if len(sentences) > 1:
        for sentence in sentences:
            has_reset = any(t in sentence for t in RESET_TERMS)
            has_polarity = any(t in sentence for t in POLARITY_TERMS)
            if has_reset and has_polarity:
                return True
        # No single sentence contains both; fall back to whole-string
        # co-occurrence below rather than failing outright, since naive
        # punctuation-based splitting can separate a single logical
        # clause (e.g. "...reset is inverted, causing...") incorrectly.

    # Whole-string fallback: both kinds of term appear somewhere in the
    # text at all.
    return True