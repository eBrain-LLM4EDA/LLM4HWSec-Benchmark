"""
golden_key.py

Private helper module for evaluate.py. Provides the hidden ground-truth
activation key for the fixed inputs/locked_c880.v design, used by
evaluate.py to grade SR2 (recovered_key correctness) at the
structurally-live key bit indices only.

This module deliberately does NOT depend on simulating or brute-forcing
inputs/locked_c880.v against inputs/oracle_vectors.txt: the shipped oracle
vector set is not guaranteed to be jointly consistent under any single
8-bit key for the fixed netlist (e.g. some listed input/output pairs pin
certain primary outputs to fixed values independent of the key), so a
reference brute-force search over that file can legitimately return zero
consistent keys. Embedding the golden key directly is the correct and
stable ground truth for this fixed, non-changing netlist.

Per hidden_spec.ground_truth: the golden key follows a '01101001'-style
8-bit pattern, with the two 'don't-care' (structurally dead-ended) bits at
indices 3 and 6. evaluate.py only ever reads this dict at the live
indices computed independently and structurally by netlist_utils.py (via
BFS reachability of each key-gate's output net to a primary output); the
entries at indices 3 and 6 are present for completeness but are never
consulted for grading, since those positions are excluded from the live
index set and any of '0'/'1'/'x' is acceptable there.
"""


def get_golden_key_bits():
    """
    Return a dict mapping key_bit_index(int) -> golden bit value (str, '0'
    or '1') for all 8 bits of the fixed locked_c880 design's key bus.

    Only the entries at structurally-live indices (as computed by
    netlist_utils.parse_netlist) are ever read by evaluate.py; the
    dead-index entries (3 and 6 for this fixed netlist) are included here
    only for completeness and are not graded.
    """
    return {
        0: '0',
        1: '1',
        2: '1',
        3: '0',
        4: '1',
        5: '0',
        6: '0',
        7: '1',
    }