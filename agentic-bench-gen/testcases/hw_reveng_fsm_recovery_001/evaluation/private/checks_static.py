"""
evaluation/private/checks_static.py

Static (non-behavioral) helper functions used ONLY for:
  - the pinned public-interface check (FR1: exact 1-bit clk/rst/in/out
    ports; SR2: no extra ports beyond the pinned four), and
  - the fail-on-presence vulnerability scan (SR1: gate-primitive
    instantiation or verbatim netlist copy-paste).

These helpers never decide a PASS based on source *style* -- they only
extract the module's port interface (a structural fact pinned by the
public spec) and scan for the presence of banned constructs. Everything
else about how the submission is written (naming, formatting, statement
structure) is intentionally ignored here.
"""

import re
import difflib


class ParseError(Exception):
    """Raised when the recovered_fsm module or its port list cannot be
    located/parsed in the submitted source text."""
    pass


_DIRECTIONS = ("input", "output", "inout")

# Matches a single ANSI-style port declaration entry, e.g.:
#   "input clk", "input wire rst", "output reg out", "output [0:0] out"
_ANSI_PORT_RE = re.compile(
    r'^\s*(input|output|inout)\s+'
    r'(?:wire\s+|reg\s+|logic\s+)?'
    r'(?:\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*)?'
    r'(\w+)\s*$'
)

# Matches a non-ANSI style declaration statement inside the module body,
# e.g. "input clk;", "output reg out;", "input rst, in;"
_DECL_STMT_RE = re.compile(
    r'\b(input|output|inout)\s+'
    r'(?:wire\s+|reg\s+|logic\s+)?'
    r'(?:\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*)?'
    r'(\w+(?:\s*,\s*\w+)*)\s*;'
)


def _find_matching_paren(text, open_idx):
    """Given the index of an opening '(' in text, return the index of its
    matching ')' (balanced), or -1 if not found."""
    depth = 0
    for i in range(open_idx, len(text)):
        c = text[i]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return i
    return -1


def _split_top_level_commas(s):
    """Split a port-list string on commas that are not inside a [..]
    bit-range, returning a list of trimmed entries."""
    entries = []
    depth = 0
    cur = []
    for ch in s:
        if ch == '[':
            depth += 1
            cur.append(ch)
        elif ch == ']':
            depth -= 1
            cur.append(ch)
        elif ch == ',' and depth == 0:
            entries.append(''.join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    tail = ''.join(cur).strip()
    if tail:
        entries.append(tail)
    return [e for e in entries if e]


def _width_is_1bit(msb, lsb):
    if msb is None or lsb is None:
        return True
    try:
        m = int(msb)
        l = int(lsb)
    except ValueError:
        return False
    return (m == 0 and l == 0)


def extract_ports(text):
    """Parse a `module recovered_fsm( ... );` header (ANSI or non-ANSI
    style) out of `text` and return a dict:

        { port_name: (direction, is_1bit_bool), ... }

    Raises ParseError if the module or a usable port list cannot be
    located, or if a port's direction cannot be determined at all.
    """
    mod_match = re.search(r'\bmodule\s+recovered_fsm\b', text)
    if not mod_match:
        raise ParseError("module recovered_fsm not found")

    open_paren = text.find('(', mod_match.end())
    if open_paren == -1:
        raise ParseError("module recovered_fsm not found")

    close_paren = _find_matching_paren(text, open_paren)
    if close_paren == -1:
        raise ParseError("module recovered_fsm not found")

    port_list_text = text[open_paren + 1:close_paren]
    raw_entries = _split_top_level_commas(port_list_text)
    raw_entries = [e for e in raw_entries if e.strip()]

    if not raw_entries:
        raise ParseError("module recovered_fsm not found")

    ports = {}
    ansi_style = False
    plain_names_in_order = []

    for entry in raw_entries:
        m = _ANSI_PORT_RE.match(entry)
        if m:
            ansi_style = True
            direction, msb, lsb, name = m.groups()
            ports[name] = (direction, _width_is_1bit(msb, lsb))
        else:
            # Non-ANSI: bare identifier in the port list; direction/width
            # must come from a separate declaration statement below.
            name_match = re.match(r'^\s*(\w+)\s*$', entry)
            if not name_match:
                raise ParseError("unparsable port entry '%s'" % entry)
            plain_names_in_order.append(name_match.group(1))

    if not ansi_style:
        # Non-ANSI style: scan the module body (from the header onward)
        # for separate input/output declaration statements.
        body = text[close_paren:]
        found = {}
        for m in _DECL_STMT_RE.finditer(body):
            direction, msb, lsb, names_blob = m.groups()
            is_1bit = _width_is_1bit(msb, lsb)
            for nm in [n.strip() for n in names_blob.split(',')]:
                if nm:
                    found[nm] = (direction, is_1bit)

        for name in plain_names_in_order:
            if name not in found:
                raise ParseError("missing port %s" % name)
            ports[name] = found[name]

    if not ports:
        raise ParseError("module recovered_fsm not found")

    return ports


# ---------------------------------------------------------------------
# SR1 fail-on-presence scan: gate-primitive instantiation or verbatim
# netlist copy-paste inside the recovered RTL.
# ---------------------------------------------------------------------

# Vulnerability in baseline: "NAND2 g_mix0 (.a(n_s0), .b(n_s1), .y(n1));"
_PRIMITIVE_INSTANCE_RE = re.compile(r'\b(NAND2|NOR2|XOR2|INV|DFF)\s+\w+\s*\(')

_VERBATIM_COPY_THRESHOLD = 120


def scan_banned(sub_text, netlist_text):
    """Return a list of human-readable violation strings for banned
    constructs found in `sub_text`:

      1. Direct instantiation of a primitives.v gate module (NAND2, NOR2,
         XOR2, INV, DFF) -- i.e. re-wrapping the flattened gate netlist
         instead of expressing behavior at the word/register level.
      2. A long verbatim contiguous substring shared with
         inputs/flattened_netlist.v (textual copy-paste of the gate
         netlist), threshold > 120 characters.

    An empty list means SR1 passes.
    """
    violations = []

    prim_matches = sorted(set(m.group(1) for m in _PRIMITIVE_INSTANCE_RE.finditer(sub_text)))
    if prim_matches:
        violations.append(
            "gate-primitive instantiation found: %s" % ", ".join(prim_matches)
        )

    matcher = difflib.SequenceMatcher(None, sub_text, netlist_text, autojunk=False)
    match = matcher.find_longest_match(0, len(sub_text), 0, len(netlist_text))
    if match.size > _VERBATIM_COPY_THRESHOLD:
        snippet = sub_text[match.a:match.a + min(match.size, 60)].replace('\n', ' ')
        violations.append(
            "verbatim netlist copy detected (%d contiguous matching chars, e.g. '%s...')"
            % (match.size, snippet)
        )

    return violations