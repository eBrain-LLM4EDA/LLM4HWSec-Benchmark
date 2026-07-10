"""
evaluation/private/ground_truth_analysis.py

Hidden (participant-invisible) structural-analysis helpers used by
evaluation/evaluate.py to grade the SR1/SR4 security requirements against
the fixed inputs/aes_core.v and inputs/design_brief.md reference files.

This module performs purely structural pattern matching over the RTL text:
  - it locates registers that are incremented unconditionally every clock
    cycle inside the reset-else branch of a clocked always block (the
    "free-running rare-trigger counter" pattern), and
  - it locates continuous-assignment (`assign`) expressions that compare
    such a register against a wide (>=12-bit) rare constant, optionally ANDed
    with a second condition (the "rare-state comparator / trojan-enable"
    pattern).

No literal trojan signal name (e.g. a specific counter or enable-wire
identifier) is hardcoded anywhere in this file; the detection relies only
on the *shape* of the constructs, so it remains valid even if the RTL's
identifiers were renamed.
"""

import re

# ---------------------------------------------------------------------------
# Shared identifier / port helpers (mirrors the copies in evaluate.py so this
# module is self-contained and independently testable).
# ---------------------------------------------------------------------------

_VERILOG_KEYWORDS = {
    "module", "input", "output", "reg", "wire", "always", "begin", "end",
    "if", "else", "posedge", "negedge", "assign", "integer", "initial",
    "endmodule", "parameter", "localparam", "function", "endfunction",
    "for", "case", "endcase",
}


def verilog_identifiers(text):
    """Return the set of non-keyword identifier tokens appearing in text."""
    tokens = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", text))
    return tokens - _VERILOG_KEYWORDS


def output_ports(text):
    """Extract declared output port names from a Verilog module body."""
    return set(re.findall(
        r"output\s+(?:reg\s+)?(?:\[\d+:\d+\]\s+)?(\w+)", text
    ))


# ---------------------------------------------------------------------------
# Structural detection of the hidden rare-trigger counter + comparator.
# ---------------------------------------------------------------------------

_ALWAYS_SPLIT_RE = re.compile(r"\balways\b")

# Matches the *contents* of an "else begin ... end" region, non-greedily so
# it captures the nearest properly-closed inner block rather than spanning
# unrelated later code. Word-boundaries on "end" avoid false stops inside
# "endmodule"/"endcase"/"endfunction".
_ELSE_BEGIN_RE = re.compile(r"else\s*begin\s*(.*?)\s*\bend\b", re.DOTALL)

# A single statement of the form: `<reg> <= <reg> + <literal>;`
# with nothing else in the branch -- i.e. an unconditional per-cycle
# increment with no guarding condition.
_UNCONDITIONAL_INCREMENT_RE = re.compile(
    r"^(\w+)\s*<=\s*\1\s*\+\s*(?:\d+\s*'\s*[hHdDbBoO]?\s*[0-9A-Fa-f]+|\d+)\s*;?$"
)

# `assign <target> = <rhs>;` continuous assignments.
_ASSIGN_RE = re.compile(r"\bassign\s+(\w+)\s*=\s*([^;]+);", re.DOTALL)

# `<reg> == <width>'h<hexdigits>` comparisons (case-insensitive base letter).
_HEX_COMPARE_RE_TEMPLATE = r"\b{reg}\s*==\s*(\d+)\s*'\s*[hH]\s*([0-9A-Fa-f]+)"

# Fallback: `<reg> == <decimal>` with a "wide" (>=4-digit, i.e. >=1000)
# decimal constant and no explicit base literal.
_DEC_COMPARE_RE_TEMPLATE = r"\b{reg}\s*==\s*(\d{{4,}})\b"


def _split_always_blocks(text):
    """Split text into chunks starting at each 'always' keyword occurrence."""
    indices = [m.start() for m in _ALWAYS_SPLIT_RE.finditer(text)]
    blocks = []
    for i, idx in enumerate(indices):
        end = indices[i + 1] if i + 1 < len(indices) else len(text)
        blocks.append(text[idx:end])
    return blocks


def _is_clocked_block(block_text):
    """Heuristic: block is a clocked sequential process (posedge/negedge)."""
    return bool(re.search(r"\b(?:posedge|negedge)\b", block_text))


def _find_unconditional_counters(text):
    """
    Return the set of register names that are incremented every cycle with
    no guarding condition inside a clocked always block's reset-else branch
    (or any bare else-begin branch consisting solely of that statement).
    """
    counters = set()
    for block in _split_always_blocks(text):
        if not _is_clocked_block(block):
            continue
        for captured in _ELSE_BEGIN_RE.findall(block):
            lines = [ln.strip() for ln in captured.splitlines() if ln.strip()]
            if len(lines) != 1:
                continue
            m = _UNCONDITIONAL_INCREMENT_RE.match(lines[0])
            if m:
                counters.add(m.group(1))
    return counters


def _find_comparators(text, counter_regs):
    """
    Return (enable_signals, constants): the set of assign-target wire names
    whose RHS compares a counter register against a wide (>=12-bit) rare
    constant, and the set of integer constant values discovered.
    """
    enable_signals = set()
    constants = set()

    for target, rhs in _ASSIGN_RE.findall(text):
        for reg in counter_regs:
            hex_re = re.compile(_HEX_COMPARE_RE_TEMPLATE.format(reg=re.escape(reg)))
            for width_str, hexdigits in hex_re.findall(rhs):
                try:
                    width = int(width_str)
                except ValueError:
                    width = 0
                wide_enough = width >= 12 or len(hexdigits) >= 3
                if wide_enough:
                    enable_signals.add(target)
                    try:
                        constants.add(int(hexdigits, 16))
                    except ValueError:
                        pass

            dec_re = re.compile(_DEC_COMPARE_RE_TEMPLATE.format(reg=re.escape(reg)))
            for dec_val in dec_re.findall(rhs):
                enable_signals.add(target)
                try:
                    constants.add(int(dec_val))
                except ValueError:
                    pass

    return enable_signals, constants


def candidate_trigger_signals(text):
    """
    Structural SR1 heuristic.

    Returns (trigger_signals, trigger_constants):
      - trigger_signals: union of {free-running counter register name(s),
        comparator/enable wire name(s)} identified structurally.
      - trigger_constants: set of integer rare-constant values discovered
        in the comparator expressions.

    A report's finding is considered to correctly name the trojan trigger
    if its signal_name is a member of trigger_signals and its
    activation_condition text references one of trigger_constants.
    """
    counters = _find_unconditional_counters(text)
    enable_signals, constants = _find_comparators(text, counters)
    trigger_signals = set(counters) | set(enable_signals)
    return trigger_signals, constants


# ---------------------------------------------------------------------------
# Documented/legitimate signal extraction (for SR4 false-positive counting).
# ---------------------------------------------------------------------------

_BACKTICK_IDENT_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)`")


def documented_signals(brief_text):
    """
    Return the set of identifiers backtick-quoted in design_brief.md,
    representing the legitimate/documented control & datapath signals of
    the design (e.g. clk, rst_n, in_data, key, start, out_data, done,
    state_reg, key_reg, round_cnt, busy, rcon).
    """
    return set(_BACKTICK_IDENT_RE.findall(brief_text))