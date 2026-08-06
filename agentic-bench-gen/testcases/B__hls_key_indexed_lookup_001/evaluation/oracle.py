"""
evaluation/oracle.py

Pure-Python documentation helpers kept alongside the C++ harness for
maintainer convenience. Nothing in this module is used by evaluate.py to
compute PASS/FAIL verdicts, and nothing here hardcodes specific table byte
values as an oracle: the public interface pins only the table's name
(`table`), element type (`uint8_t`), and size (16 entries) -- not its
contents -- so the actual FR1/SR4 oracle used by evaluate.py is derived
live from the submission's OWN compiled table via
`harness_get_table_entry(idx)` (see evaluation/table_accessor.cpp and
evaluation/harness_main.cpp). This module exists purely so the reference
substitution formula and the canonical access-trace shape are documented
in one small, obviously-correct place that a maintainer can exercise
interactively (e.g. in a Python REPL) without needing to compile anything.

  - oracle(value, key, table): the reference substitution function
    table[(value ^ key) & 0x0F], evaluated in Python purely for
    documentation/consistency purposes. It is generic over `table` (any
    16-entry sequence of ints 0-255) so a maintainer can call it with
    whatever table contents a given submission actually ships, rather than
    a fixed constant baked into this file.

  - canonical_trace(): the fixed reference index sequence [0, 1, ..., 15]
    that a fully data-oblivious 16-read scan must produce on every call,
    used for documentation purposes alongside the trace-based SR1/SR2/SR3
    logic implemented in evaluate.py and evaluation/harness_main.cpp.

Nothing in this module reads, parses, or extracts values from
inputs/lookup_kernel.cpp, and it defines no fixed reference table
constant: the correct oracle for FR1/SR4 is intentionally NOT a Python-side
or harness-side hardcoded byte array, since the interface does not require
any particular hardened submission to keep specific table byte values --
only that `table` remain a 16-entry `uint8_t` array under that name.
"""


def oracle(value, key, table):
    """Reference behavior: table[(value ^ key) & 0x0F].

    value, key: ints in [0, 255].
    table: a sequence of 16 ints (0-255) representing the substitution
           table to index into. Callers must supply the actual table
           contents they wish to check against (e.g. a submission's own
           table, read however is convenient for the caller) -- this
           function intentionally has no default table, since no fixed
           byte values are pinned by the public interface.

    This function is provided for documentation/consistency purposes only;
    evaluate.py's FR1/SR4 verdicts are computed by the compiled C++
    harness, which derives its oracle live from the submission's own
    compiled `table` symbol via harness_get_table_entry(idx), not by
    calling into this module.
    """
    if table is None or len(table) != 16:
        raise ValueError("table must be a sequence of exactly 16 entries")
    idx = (int(value) ^ int(key)) & 0x0F
    return int(table[idx]) & 0xFF


def canonical_trace():
    """The fixed, data-oblivious access-index sequence a hardened kernel
    must produce on every single invocation: indices 0..15 in ascending
    order, each exactly once.
    """
    return list(range(16))