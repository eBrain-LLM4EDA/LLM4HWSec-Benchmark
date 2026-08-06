"""
netlist_utils.py -- private parsing helpers for the gate trojan detection
grader (evaluation/evaluate.py). Not participant-facing.

parse_netlist(path):
    Scans a structural Verilog netlist (the fixed reference file at
    inputs/mult8_netlist.v) for gate primitive instantiations of the form:

        <primitive> <instance_name> ( ... );

    where <primitive> is one of and/or/nand/nor/not/xor/xnor/buf, and
    returns:
        (instance_names: set[str],
         gate_type_counts: dict[str,int],
         total_gates: int)

    Comments (both // line comments and /* ... */ block comments) are
    stripped before scanning so that gate keywords appearing only in
    prose comments are never counted.

parse_trigger_condition(text):
    Attempts to recover concrete 8-bit integer values for primary inputs
    `a` and `b` from a free-form trigger_condition string, using either:
      - a per-bit enumeration form, e.g. "a[7]=1,a[6]=0,...,b[0]=1,..."
        covering all 8 bits (0..7) of each variable unambiguously, or
      - a compact literal form for each variable, e.g.
        "a=8'b10110100", "a=10110100b", "a=8'hb4", "a=0xb4", "a=8'd180",
        "a=180".
    Returns (a_int, b_int) if both values can be unambiguously determined
    for all 8 bits, otherwise None.
"""

import re


GATE_PRIMITIVES = ["and", "or", "nand", "nor", "not", "xor", "xnor", "buf"]


def _strip_comments(text):
    # Remove /* ... */ block comments (non-greedy, across lines).
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    # Remove // line comments.
    text = re.sub(r"//[^\n]*", " ", text)
    return text


_GATE_INSTANCE_RE = re.compile(
    r"\b(and|or|nand|nor|not|xor|xnor|buf)\b\s+(\w+)\s*\(",
    re.MULTILINE,
)


def parse_netlist(path):
    """
    Parse a structural Verilog netlist file and return:
        (instance_names, gate_type_counts, total_gates)
    """
    with open(path, "r") as f:
        raw = f.read()

    cleaned = _strip_comments(raw)

    instance_names = set()
    gate_type_counts = {prim: 0 for prim in GATE_PRIMITIVES}

    for match in _GATE_INSTANCE_RE.finditer(cleaned):
        prim = match.group(1)
        inst_name = match.group(2)
        gate_type_counts[prim] = gate_type_counts.get(prim, 0) + 1
        instance_names.add(inst_name)

    total_gates = sum(gate_type_counts.values())
    return instance_names, gate_type_counts, total_gates


# ---------------------------------------------------------------------
# trigger_condition parsing
# ---------------------------------------------------------------------

_BIT_ASSIGN_RE = re.compile(r"\b([aAbB])\s*\[\s*(\d)\s*\]\s*=\s*([01])\b")


def _parse_bits(text):
    """
    Extract per-bit assignments for variables 'a' and 'b' of the form
    a[3]=1, b[0]=0, etc. Returns (a_bits_or_None, b_bits_or_None) where
    each is an int 0..255 if all 8 bits (0..7) were found unambiguously
    (no conflicting duplicate assignment for the same bit index), else
    None for that variable.
    """
    bits = {"a": {}, "b": {}}
    conflict = {"a": False, "b": False}

    for match in _BIT_ASSIGN_RE.finditer(text):
        var = match.group(1).lower()
        idx = int(match.group(2))
        if idx < 0 or idx > 7:
            continue
        val = int(match.group(3))
        if idx in bits[var] and bits[var][idx] != val:
            conflict[var] = True
        bits[var][idx] = val

    result = {}
    for var in ("a", "b"):
        if conflict[var]:
            result[var] = None
            continue
        d = bits[var]
        if len(d) == 8 and all(i in d for i in range(8)):
            value = 0
            for idx, val in d.items():
                value |= (val & 1) << idx
            result[var] = value
        else:
            result[var] = None

    return result["a"], result["b"]


def _extract_compact_value(text, varname):
    """
    Try a series of compact-literal regexes for a single variable name
    ('a' or 'b') and return an int 0..255 if found, else None.
    Patterns are tried in order of specificity to avoid ambiguity.
    """
    v = re.escape(varname)

    patterns = [
        # a=8'b10110100
        (r"\b%s\b\s*=\s*8\s*'\s*b\s*([01]{8})" % v, 2),
        # a=8'h b4  (hex, exactly 2 hex digits)
        (r"\b%s\b\s*=\s*8\s*'\s*h\s*([0-9A-Fa-f]{1,2})" % v, 16),
        # a=8'd180 (decimal)
        (r"\b%s\b\s*=\s*8\s*'\s*d\s*(\d{1,3})" % v, 10),
        # a=0xb4 (hex with 0x prefix)
        (r"\b%s\b\s*=\s*0[xX]([0-9A-Fa-f]{1,2})\b" % v, 16),
        # a=10110100b (bare binary string suffixed with 'b')
        (r"\b%s\b\s*=\s*([01]{8})b\b" % v, 2),
        # a=180 (plain decimal, fallback -- must be a whole word)
        (r"\b%s\b\s*=\s*(\d{1,3})\b" % v, 10),
    ]

    for pattern, base in patterns:
        m = re.search(pattern, text)
        if m:
            try:
                value = int(m.group(1), base)
            except ValueError:
                continue
            if 0 <= value <= 255:
                return value
    return None


def parse_trigger_condition(text):
    """
    Attempt to recover (a_int, b_int) from a free-form trigger_condition
    string. Tries per-bit enumeration first, falling back independently
    per-variable to compact literal forms. Returns None if either value
    cannot be unambiguously determined.
    """
    if not isinstance(text, str) or not text.strip():
        return None

    a_from_bits, b_from_bits = _parse_bits(text)

    a_val = a_from_bits if a_from_bits is not None else _extract_compact_value(text, "a")
    b_val = b_from_bits if b_from_bits is not None else _extract_compact_value(text, "b")

    if a_val is None or b_val is None:
        return None

    return a_val, b_val