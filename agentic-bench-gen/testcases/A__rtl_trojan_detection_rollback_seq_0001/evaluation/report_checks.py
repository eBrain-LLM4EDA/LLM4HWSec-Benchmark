#!/usr/bin/env python3
"""
report_checks.py - shared, style-invariant text/structure matchers used by
evaluate.py (and by evaluation/private/sr_checks.py) to grade the substance
of a submitted trojan_report.json.

These helpers deliberately accept a wide variety of phrasings so that a
correct-but-differently-worded golden report passes, while vague/generic
boilerplate (as produced by the naive/Trust-Hub-style baselines) fails.
"""

import re


def find_top_candidate(candidates):
    """
    Given a list of candidate dicts (already schema-validated by FR2), return
    the candidate with the maximum 'confidence' value. Ties are broken by
    first occurrence (i.e. the first candidate achieving the max value wins).

    Returns None if candidates is empty or not a list.
    """
    if not isinstance(candidates, list) or len(candidates) == 0:
        return None

    best = None
    best_conf = None
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        conf = cand.get("confidence", None)
        if not isinstance(conf, (int, float)) or isinstance(conf, bool):
            continue
        conf = float(conf)
        if best is None or conf > best_conf:
            best = cand
            best_conf = conf
    return best


# ---------------------------------------------------------------------------
# Real internal register extraction (used by FR3 / SR1)
# ---------------------------------------------------------------------------

# The documented, pinned public interface signals for version_ctrl. Even
# though version_q is declared `output reg [7:0] version_q`, it is a
# documented interface port, not a hidden internal state variable, so it
# must be excluded from the "real internal registers" set used to satisfy
# FR3/SR1.
PUBLIC_PORT_NAMES = {
    "clk",
    "rst_n",
    "req_valid",
    "candidate_version",
    "req_accept",
    "version_q",
    "update_ack",
}

# Matches Verilog reg declarations, e.g.:
#   reg [1:0] seq_state_q;
#   reg       ack_d;
#   output reg [7:0] version_q,
# Captures the (possibly comma-separated) identifier list that follows the
# optional range.
_REG_DECL_RE = re.compile(
    r'\breg\s*(?:\[\s*[^\]]+\]\s*)?'      # 'reg' plus optional [msb:lsb]
    r'((?:\w+\s*(?:,\s*)?)+)',            # one or more identifiers, comma-sep
    re.IGNORECASE,
)

# A single trailing identifier token, allowing an optional array/range
# suffix like `foo [3:0]` (rare, but be tolerant) and stripping punctuation.
_IDENT_TOKEN_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def extract_internal_registers(verilog_text):
    """
    Parse `verilog_text` (the contents of inputs/version_ctrl.v) and return a
    set of lowercase identifier names for every `reg` declared in the file,
    EXCLUDING the pinned public interface ports (PUBLIC_PORT_NAMES).

    This is intentionally simple/regex-based (not a full Verilog parser) but
    is sufficient to recover genuine internal sequential-state register
    names (e.g. seq_state_q, ack_d) from the design, which is what FR3/SR1
    require a submitted report to actually name -- as opposed to generic
    placeholder phrases like "internal_state" or "some internal logic"
    that do not correspond to any real declared signal.
    """
    if not isinstance(verilog_text, str):
        return set()

    found = set()

    for decl_match in _REG_DECL_RE.finditer(verilog_text):
        ident_blob = decl_match.group(1)
        if not ident_blob:
            continue
        # Split on commas to handle `reg a, b, c;`-style declarations.
        for raw_tok in ident_blob.split(','):
            tok = raw_tok.strip()
            # Strip a trailing semicolon or other stray punctuation that may
            # have been swept up (defensive; the regex mostly avoids this).
            tok = tok.rstrip(';').strip()
            if not tok:
                continue
            if not _IDENT_TOKEN_RE.match(tok):
                continue
            lower_tok = tok.lower()
            if lower_tok in PUBLIC_PORT_NAMES:
                continue
            found.add(lower_tok)

    return found


def mentions_internal_state(text, real_regs):
    """
    True if `text` contains a whole-word (case-insensitive) occurrence of any
    identifier in `real_regs` -- i.e. a genuine internal sequential-state
    register actually declared in inputs/version_ctrl.v, distinct from the
    documented public interface ports.

    Generic placeholder phrasing such as "internal_state", "some internal
    logic", "hidden progression", or "ack_flop" does NOT satisfy this check
    unless it happens to exactly match a real declared register name (it
    won't, since those are not real signals in the design), which is the
    fix for the previously-vague keyword-based matcher.

    `real_regs` must be a set/iterable of lowercase identifier strings, as
    produced by extract_internal_registers().
    """
    if not isinstance(text, str) or not text.strip():
        return False

    if not real_regs:
        return False

    for reg_name in real_regs:
        if not reg_name:
            continue
        pattern = r'(?<![A-Za-z0-9_])' + re.escape(reg_name) + r'(?![A-Za-z0-9_])'
        if re.search(pattern, text, re.IGNORECASE):
            return True

    return False


# ---------------------------------------------------------------------------
# SR2 helper: ordered nibble-trigger sequence 0x3 -> 0xC -> 0x5
# ---------------------------------------------------------------------------

# Build alternation patterns that recognize a given nibble value in many
# equivalent textual representations: hex forms (0x3, 4'h3, h3), bare
# decimal, or decimal spelled with word boundaries. We require the token to
# appear as a distinct lexical unit (not embedded inside a longer number) by
# using word boundaries / negative lookarounds against surrounding hex
# digits.

def _nibble_alternatives(hexdigit, decimal_val):
    """
    hexdigit: single lowercase hex character, e.g. '3', 'c', '5'
    decimal_val: the decimal equivalent, e.g. 3, 12, 5
    """
    hd_upper = hexdigit.upper()
    alts = [
        r"0x0?{0}\b".format(hexdigit),
        r"0x0?{0}\b".format(hd_upper),
        r"4'h0?{0}\b".format(hexdigit),
        r"4'h0?{0}\b".format(hd_upper),
        r"4'b[01]{{4}}".format(),  # placeholder unused directly; binary handled separately
        r"(?<![0-9A-Za-z_])h0?{0}\b".format(hexdigit),
        r"(?<![0-9A-Za-z_])h0?{0}\b".format(hd_upper),
        r"(?<![0-9A-Za-z_.\-]){0}\b(?!['\"]?\s*(?:st|nd|rd|th))".format(decimal_val),
        r"nibble\s+(?:value\s+)?(?:of\s+)?['\"]?0?{0}['\"]?".format(hexdigit),
        r"nibble\s+(?:value\s+)?(?:of\s+)?['\"]?0?{0}['\"]?".format(hd_upper),
    ]
    return r"(?:{})".format("|".join(alts))


_NIB_3_RE = re.compile(_nibble_alternatives("3", 3), re.IGNORECASE)
_NIB_C_RE = re.compile(_nibble_alternatives("c", 12), re.IGNORECASE)
_NIB_5_RE = re.compile(_nibble_alternatives("5", 5), re.IGNORECASE)

# Words implying an ordered/sequential relationship between mentioned values.
_SEQUENCE_CONTEXT_RE = re.compile(
    r'\b(?:sequence|order|then|followed by|in\s+order|step|consecutive|'
    r'first.*second.*third|s0.*s1.*s2|three\s+(?:consecutive|successive)\s+'
    r'requests?)\b',
    re.IGNORECASE,
)


def mentions_nibble_sequence(text):
    """
    True if `text` mentions all three trigger nibble values (0x3, 0xC, 0x5)
    with 0x3 appearing before 0xC, which appears before 0x5 (matching the
    ground-truth activation order S0->S1->S2->S3), AND the text carries some
    sequential/ordering context word (to avoid accidentally matching three
    unrelated numbers that happen to appear in numeric order for other
    reasons, e.g. an address range).
    """
    if not isinstance(text, str) or not text.strip():
        return False

    m3 = _NIB_3_RE.search(text)
    if not m3:
        return False

    # Search for 'c' nibble only after the position of the '3' match to
    # enforce ordering.
    mc = _NIB_C_RE.search(text, m3.end())
    if not mc:
        return False

    m5 = _NIB_5_RE.search(text, mc.end())
    if not m5:
        return False

    if not _SEQUENCE_CONTEXT_RE.search(text):
        return False

    return True


# ---------------------------------------------------------------------------
# SR3 / FR4 helper: decrement payload on version_q
# ---------------------------------------------------------------------------

_DECREMENT_PATTERNS = [
    r'version_q\s*-\s*1\b',
    r'version_q\s*-\s*8\'d1\b',
    r'version_q\s*<=\s*version_q\s*-\s*1\b',
    r'\bdecrement(?:s|ed|ing)?\b.{0,40}\bversion\b',
    r'\bversion\b.{0,40}\bdecrement(?:s|ed|ing)?\b',
    r'\bsubtract(?:s|ed|ing|ion)?\s+(?:1|one)\b.{0,40}\bversion\b',
    r'\bversion\b.{0,40}\bsubtract(?:s|ed|ing|ion)?\s+(?:1|one)\b',
    r'\bminus\s+(?:1|one)\b.{0,40}\bversion\b',
    r'\bversion\b.{0,40}\bminus\s+(?:1|one)\b',
    r'\bdecrement(?:s|ed|ing)?\s+by\s+(?:1|one)\b',
    r'\breduc(?:e|es|ed|ing)\s+(?:the\s+)?version(?:_q)?\s+by\s+(?:1|one)\b',
    r'\brolls?\s+back\s+(?:the\s+)?version(?:_q)?\s+by\s+(?:1|one)\b',
    r'version(?:_q)?\s+(?:is\s+)?(?:decremented|reduced|lowered)\s+by\s+(?:1|one)\b',
    r'version(?:_q)?\s*-=\s*1\b',
]

_DECREMENT_RE = re.compile("|".join(_DECREMENT_PATTERNS), re.IGNORECASE)

# Vague/incorrect phrasings that must NOT count as satisfying the decrement
# requirement even if they loosely co-occur with the word "version".
_VAGUE_PATTERNS = [
    r'\bincorrect\s+update\b',
    r'\bwrong\s+value\b',
    r'\breset\s+to\s+zero\b',
    r'\bjump(?:s|ed|ing)?\s+to\s+(?:a\s+)?fixed\s+value\b',
    r'\bset\s+to\s+(?:0|zero)\b',
    r'\bunexpected\s+value\b',
    r'\bnon[- ]monotonic\s+update\b(?!.{0,60}(?:decrement|subtract|minus\s+(?:1|one)))',
]

_VAGUE_RE = re.compile("|".join(_VAGUE_PATTERNS), re.IGNORECASE)


def mentions_decrement_payload(text):
    """
    True if `text` explicitly describes the payload as decrementing the
    version register by one (version_q - 1 or equivalent phrasing), as
    opposed to vague/incorrect descriptions such as "incorrect update",
    "reset to zero", or "jump to a fixed value".

    A report can still pass even if it also uses some generic language,
    as long as the concrete decrement-by-one semantics are present
    somewhere in the text.
    """
    if not isinstance(text, str) or not text.strip():
        return False

    if _DECREMENT_RE.search(text):
        return True

    return False