import re

# ---------------------------------------------------------------------------
# evaluation/private/ground_truth.py
#
# PRIVATE ground-truth constants and matching helpers for the bus_arbiter.v
# denial-of-service FSM trojan task. This module is imported by
# evaluation/evaluate.py and must never be shipped/exposed to participants.
#
# Ground truth (see hidden_spec in the task definition, not visible to
# participants): bus_arbiter.v implements a documented 5-state round-robin
# arbiter (IDLE, GRANT0, GRANT1, GRANT2, GRANT3) plus one additional,
# undocumented FSM state (encoded 3'b101 in the reference RTL, conceptually
# named "LOCKED" in the threat narrative, and literally spelled "STATE5" in
# the shipped baseline RTL's case statement). That extra state is reachable
# only from GRANT2 when req == 4'b1011 while busy is asserted, and once
# entered it never grants the bus again for any req pattern short of a full
# asynchronous reset (rst_n de-asserted).
#
# A correct participant submission may use ANY reasonable name for that
# hidden state (e.g. "LOCKED", "STATE5", "TRAP_STATE", "lock state",
# "hidden state 5", referencing the 3'b101 encoding, etc.) as long as it is
# clearly distinct from the five legitimate/documented states. The matching
# helpers below are therefore intentionally tolerant of naming style while
# still requiring a concrete tie to the hidden state (by name or by its
# distinguishing encoding), and are NOT satisfied by mere presence of the
# digit "5" or the substring "101" in unrelated prose.
# ---------------------------------------------------------------------------

# Confidence threshold: a correct candidate must carry confidence >= this
# value to count as a full detection (per hidden_spec acceptance_criteria).
CONFIDENCE_THRESHOLD = 0.5

# Raw token list retained for documentation / auditability purposes; the
# actual matching is done via HIDDEN_STATE_PATTERN below, which anchors
# these tokens to state-naming context so bare numerals don't over-match.
HIDDEN_STATE_TOKENS = ["state5", "101", "5"]

# Legitimate, documented state names in bus_arbiter.v.
LEGIT_STATE_NAMES = ["idle", "grant0", "grant1", "grant2", "grant3"]

# The state from which the hidden transition originates.
ORIGIN_STATE_TOKEN = "grant2"

# Literal RTL/arbiter signal names.
SIGNAL_NAMES = ["req", "gnt", "busy", "rst_n"]

# Fragment matching concrete bit-selectors / literal tokens (used to rule
# out vague, placeholder-only descriptions). Kept here for auditability;
# evaluate.py's FR4 check uses an equivalent inline fragment.
CONCRETE_CONDITION_TOKENS = r"(4'b|0b|0x|\[\s*\d+\s*\]|==)"

# ---------------------------------------------------------------------------
# Hidden-state matching pattern.
#
# Accepts (case-insensitively):
#   - "state5" / "state_5" / "state 5"
#   - the reference RTL's own literal encoding forms: 3'b101, 0b101
#   - the conceptual ground-truth name "locked" / "lock state"
#   - "fifth state" / "5th state" as a descriptive equivalent
#
# Vulnerability/ground-truth anchor (reference RTL, inputs/bus_arbiter.v):
#   localparam [2:0] STATE5  = 3'b101;
# ---------------------------------------------------------------------------
HIDDEN_STATE_PATTERN = re.compile(
    r"(state\s*_?5\b|3'b101\b|0b101\b|\blocked\b|\block\s*state\b|"
    r"\bfifth\s+state\b|\b5th\s+state\b)",
    re.IGNORECASE,
)

# Pattern matching a legitimate, documented state name.
LEGIT_STATE_PATTERN = re.compile(
    r"\b(idle|grant\s*0|grant0|grant\s*1|grant1|grant\s*2|grant2|grant\s*3|grant3)\b",
    re.IGNORECASE,
)

# Pattern matching the originating state (GRANT2) for the hidden trigger.
ORIGIN_STATE_PATTERN = re.compile(r"\bgrant\s*2\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Trigger bit-pattern matching.
#
# Ground truth: req == 4'b1011 (masters 0, 1, 3 requesting simultaneously
# while master 2 -- currently granted -- has deasserted its own request bit)
# is the literal triggering value. Match binary/hex/verilog-literal forms
# only; deliberately exclude the bare decimal "11" to avoid false positives
# from unrelated numeric mentions.
#
# Vulnerability/ground-truth anchor (reference RTL, inputs/bus_arbiter.v):
#   if (busy && (gnt == 4'b0100) && (req == 4'b1011))
#       next_state = STATE5;
# ---------------------------------------------------------------------------
TRIGGER_BIT_PATTERNS = re.compile(
    r"(4'b1011\b|0b1011\b|0x0?b\b|\b1011\b)",
    re.IGNORECASE,
)


def text_of(candidate):
    """Lowercased concatenation of a candidate's four textual fields."""
    if not isinstance(candidate, dict):
        return ""
    fields = ["state_name", "trigger_condition", "rationale", "impact"]
    parts = []
    for f in fields:
        val = candidate.get(f, "")
        if isinstance(val, str):
            parts.append(val)
        elif val is not None:
            parts.append(str(val))
    return " ".join(parts).lower()


def matches_hidden_state(candidate):
    """True iff the candidate's text ties itself to the hidden sink state
    (by name, e.g. 'LOCKED'/'STATE5', or by its distinguishing 3'b101 /
    0b101 encoding), as opposed to only naming a legitimate state."""
    text = text_of(candidate)
    return bool(HIDDEN_STATE_PATTERN.search(text))


def is_legit_state_only(candidate):
    """True iff the candidate's text names a legitimate documented state
    (IDLE/GRANT0-3) and contains no reference to the hidden sink state at
    all. Used to reject false-positive candidates that merely re-label a
    legitimate state as the supposed malicious sink."""
    text = text_of(candidate)
    if matches_hidden_state(candidate):
        return False
    return bool(LEGIT_STATE_PATTERN.search(text))


def matches_trigger(candidate):
    """True iff the candidate's text correctly ties the trigger to the
    GRANT2-origin state together with the literal req=4'b1011 bit pattern
    (in binary/hex/verilog-literal form). Vague descriptions (e.g. 'random
    request pattern') without a concrete bit-pattern token do not satisfy
    this, nor does citing the bit pattern without the GRANT2 origin."""
    text = text_of(candidate)
    return bool(ORIGIN_STATE_PATTERN.search(text)) and bool(TRIGGER_BIT_PATTERNS.search(text))