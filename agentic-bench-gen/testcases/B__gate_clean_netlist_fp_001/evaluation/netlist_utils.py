#!/usr/bin/env python3
"""
netlist_utils.py - Stdlib-only helper functions shared by evaluate.py.

Provides:
  - identifier_present(name, netlist_text): verbatim/whole-word token check
    against the reference gate-level netlist text.
  - significant_identifiers(netlist_text): set of "real" netlist-derived
    identifier tokens (length >= 4, not a Verilog keyword) usable to check
    that a rationale actually references the netlist rather than being
    generic boilerplate.
  - tokenize(text): lowercase word-tokenizer used to compare rationale text
    against significant_identifiers.
  - CATEGORY_KEYWORDS: keyword lists (lowercase substrings) for the three
    documented benign-rare-signal categories in this task's design brief,
    used to check that a rationale substantively grounds its verdict.
  - CONNECTIVE_PHRASES: lowercase substrings signaling an explanatory /
    justificatory clause, used together with CATEGORY_KEYWORDS to
    distinguish a bare name-drop from an actual explanation.
  - category_grounded_count(rationale): counts how many of the 3
    CATEGORY_KEYWORDS categories are grounded by both a category keyword
    and a nearby connective phrase.
"""

import re

_IDENT_RE = re.compile(r'\b[A-Za-z_][A-Za-z0-9_]*\b')

# Common Verilog/SystemVerilog keywords and generic structural tokens that
# should NOT count as "significant" evidence that a rationale actually
# inspected the netlist (they appear in virtually every netlist regardless
# of content).
_KEYWORD_STOPLIST = {
    "module", "endmodule", "input", "output", "inout", "wire", "reg",
    "assign", "always", "posedge", "negedge", "begin", "end", "if", "else",
    "case", "endcase", "default", "parameter", "localparam", "function",
    "endfunction", "task", "endtask", "generate", "endgenerate", "for",
    "while", "initial", "logic", "integer", "genvar", "clk", "rst_n",
    "true", "false", "null", "none", "this", "that", "with", "from",
    "into", "when", "then", "than", "have", "will", "should", "would",
    "could", "does", "each", "some", "such", "only", "also", "very",
    "more", "most", "over", "under", "here", "there", "which", "these",
    "those", "being", "been", "were", "they", "them", "what", "where",
    "while", "about", "after", "before", "again", "other", "signal",
    "signals", "value", "values", "design", "block", "logic",
}


def identifier_present(name, netlist_text):
    """Return True iff `name` appears as a whole-word (word-boundary)
    token verbatim in `netlist_text`. This is used to verify that any
    net/instance name a submission lists in suspect_nodes actually exists
    in the reference gate_netlist.v, regardless of where it is declared
    (port, wire declaration, or module instance name)."""
    if not isinstance(name, str) or len(name) == 0:
        return False
    try:
        pattern = re.compile(r'\b' + re.escape(name) + r'\b')
    except re.error:
        return False
    return bool(pattern.search(netlist_text))


def significant_identifiers(netlist_text):
    """Extract the set of lowercase identifier tokens from netlist_text
    that are at least 4 characters long and are not common Verilog
    keywords / generic structural words. This gives a style-invariant way
    to check that a submitted rationale references genuine netlist content
    (e.g. rst_sync1, init_cnt, sat_cmp_ge_max, U_INITDONE_FF) rather than
    making an unsupported blanket statement."""
    tokens = _IDENT_RE.findall(netlist_text)
    result = set()
    for tok in tokens:
        lower_tok = tok.lower()
        if len(lower_tok) < 4:
            continue
        if lower_tok in _KEYWORD_STOPLIST:
            continue
        # Skip pure-numeric-looking bit-width leftovers, just in case.
        if lower_tok.isdigit():
            continue
        result.add(lower_tok)
    return result


def tokenize(text):
    """Lowercase word-tokenizer for free-form rationale text, using the
    same identifier regex as significant_identifiers so tokens can be
    compared directly against that set."""
    if not isinstance(text, str):
        return []
    return [tok.lower() for tok in _IDENT_RE.findall(text)]


# Keyword lists (lowercase substrings) for the three documented
# benign-rare-signal categories described in design_brief.md. SR3 checks
# that a submitted rationale substantively grounds its verdict in at
# least two of these three categories via case-insensitive substring
# matching against rationale.lower().
CATEGORY_KEYWORDS = {
    "reset_sync": [
        "rst_sync",
        "reset synchron",
        "async reset",
        "asynchronous reset",
        "release-synchronizer",
        "release synchronizer",
        "reset tree",
        "2-flop",
        "two-flop",
        "metastability",
    ],
    "init_counter": [
        "init_cnt",
        "init_done",
        "init counter",
        "power-on",
        "power on",
        "one-shot",
        "one shot",
        "settling window",
        "post-reset window",
        "initialization sequenc",
        "init sequence",
    ],
    "saturation": [
        "sat_cmp",
        "saturation",
        "saturating",
        "overflow",
        "clamp",
        "acc_carry7",
        "overflow_flag",
        "near-maximum",
        "near maximum",
    ],
}

# Substrings signaling an explanatory/justificatory clause. A rationale
# that merely names a rare-activity identifier or category keyword is not
# enough for SR3 - it must also connect that identifier to a reason why
# the rare activity is functionally benign, evidenced by one of these
# connective phrases appearing near the keyword occurrence.
CONNECTIVE_PHRASES = [
    "because",
    "since",
    "is expected",
    "are expected",
    "expected and",
    "is documented",
    "documented in",
    "by design",
    "functionally justified",
    "is benign",
    "are benign",
    "not evidence of",
    "not a trojan",
    "not a hidden",
    "not a disguised",
    "not a dormant",
    "is the normal",
    "is standard",
    "standard idiom",
    "standard datapath",
    "is not suspicious",
    "not suspicious",
    "not evidence",
    "is intentional",
    "intended one-shot",
    "intended behavior",
    "the point of",
    "the entire point",
    "the purpose of",
    "serves to",
    "this is why",
    "which is why",
    "that is why",
    "so that",
    "so it",
    "which explains",
    "explains why",
    "justified by",
    "is a normal",
    "normal signature",
    "primary, well-defined use case",
    "not a back door",
    "not a backdoor",
]

# Bounded character window (in each direction) used to decide whether a
# connective phrase is "near" a category keyword occurrence in the
# rationale text.
_PROXIMITY_WINDOW = 150


def category_grounded_count(rationale):
    """Return the number of CATEGORY_KEYWORDS categories (out of 3) for
    which the rationale contains BOTH a category keyword AND a
    CONNECTIVE_PHRASES match within +/- _PROXIMITY_WINDOW characters of
    that keyword occurrence (case-insensitive substring search on
    rationale.lower()).

    This distinguishes a bare list of net/category names (which would
    only satisfy FR4/naming) from a substantive explanation of why each
    named rare signal is functionally benign, as required by SR3.
    """
    if not isinstance(rationale, str) or len(rationale.strip()) == 0:
        return 0

    text_lower = rationale.lower()
    text_len = len(text_lower)

    grounded = 0
    for _category, keywords in CATEGORY_KEYWORDS.items():
        category_grounded = False
        for kw in keywords:
            if category_grounded:
                break
            start_idx = 0
            while True:
                pos = text_lower.find(kw, start_idx)
                if pos == -1:
                    break
                window_start = max(0, pos - _PROXIMITY_WINDOW)
                window_end = min(text_len, pos + len(kw) + _PROXIMITY_WINDOW)
                window_text = text_lower[window_start:window_end]

                if any(conn in window_text for conn in CONNECTIVE_PHRASES):
                    category_grounded = True
                    break

                start_idx = pos + len(kw)
        if category_grounded:
            grounded += 1

    return grounded