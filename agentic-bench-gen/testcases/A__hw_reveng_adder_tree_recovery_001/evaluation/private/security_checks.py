#!/usr/bin/env python3
"""
security_checks.py - Private fail-on-presence structural gates (SR1, SR2)

These helpers perform pure static text/regex analysis of the submitted
Verilog source. They are used ONLY as fail-on-presence gates that flag
disguised non-recovery or timing-obfuscation constructs; they never serve
as the sole basis for a PASS verdict on functional requirements.

Not referenced by any participant-facing documentation.
"""

import re
import difflib

# ---------------------------------------------------------------------------
# SR1: non-recovery structural gate
# ---------------------------------------------------------------------------

# Vulnerability in baseline: "FA1 u1_0  (.a(a[0]),  .b(b[0]),  .cin(1'b0), .sum(n2[0]),  .cout(n3));"
_GATE_INSTANCE_RE = re.compile(
    r'\b(?:FA1|AND2|OR2|XOR2|NOT1|AND3|OR3)\s+\w+\s*\('
)

# Vulnerability in baseline: file-level dependency on the primitive/gate
# library or the flattened netlist itself via an `include directive.
_INCLUDE_RE = re.compile(
    r'`include\s*"[^"]*(?:primitive_cells|flattened_netlist)\.v[^"]*"'
)

_WHITESPACE_RE = re.compile(r'\s+')

SIMILARITY_THRESHOLD = 0.80
GATE_INSTANCE_COUNT_THRESHOLD = 3


def _collapse_whitespace(text):
    return _WHITESPACE_RE.sub(' ', text).strip()


def check_sr1(submission_text, reference_netlist_text):
    """
    Returns (ok: bool, reason: str).

    FAILs if the submission:
      (a) bulk-instantiates primitive gate cells (>=3 instances), or
      (b) `includes primitive_cells.v or flattened_netlist.v, or
      (c) is near-identical (whitespace-collapsed similarity > 0.80) to the
          reference flattened netlist.
    """
    # (a) bulk gate-instance heuristic
    gate_matches = _GATE_INSTANCE_RE.findall(submission_text)
    if len(gate_matches) >= GATE_INSTANCE_COUNT_THRESHOLD:
        return (
            False,
            "submission bulk-instantiates %d primitive gate cell(s) "
            "(FA1/AND2/OR2/XOR2/NOT1/AND3/OR3); expected word-level RTL, "
            "not a rewiring of the primitive gate library" % len(gate_matches),
        )

    # (b) forbidden include of project input files
    include_match = _INCLUDE_RE.search(submission_text)
    if include_match:
        return (
            False,
            "submission `includes a project input file (%s); the "
            "submission must be self-contained and must not textually "
            "wrap primitive_cells.v or flattened_netlist.v"
            % include_match.group(0).strip(),
        )

    # (c) near-identical copy heuristic
    collapsed_submission = _collapse_whitespace(submission_text)
    collapsed_reference = _collapse_whitespace(reference_netlist_text)
    if collapsed_submission and collapsed_reference:
        ratio = difflib.SequenceMatcher(
            None, collapsed_submission, collapsed_reference
        ).ratio()
        if ratio > SIMILARITY_THRESHOLD:
            return (
                False,
                "submission text is near-identical to inputs/flattened_netlist.v "
                "(similarity ratio %.3f > %.2f); a copy of the flattened "
                "netlist does not demonstrate word-level recovery"
                % (ratio, SIMILARITY_THRESHOLD),
            )

    return (True, "")


# ---------------------------------------------------------------------------
# SR2: timing side-channel / delay-construct gate
# ---------------------------------------------------------------------------

# Vulnerability construct (informational): explicit delay-control statements
# such as "#5 ..." or "#(delay_expr) ..." that could mirror internal
# carry-chain timing from the original netlist.
_DELAY_RE = re.compile(r'#\s*(\d+|\([^)]*\))')


def check_sr2(submission_text):
    """
    Returns (ok: bool, reason: str).

    FAILs if a non-`timescale line contains an explicit delay-control
    construct (e.g. "#5" or "#(expr)").
    """
    for lineno, line in enumerate(submission_text.splitlines(), start=1):
        if '`timescale' in line:
            continue
        m = _DELAY_RE.search(line)
        if m:
            return (
                False,
                "explicit delay-control construct '%s' found on line %d; "
                "the recovered design must be purely combinational with no "
                "timing-dependent delay statements"
                % (m.group(0).strip(), lineno),
            )

    return (True, "")