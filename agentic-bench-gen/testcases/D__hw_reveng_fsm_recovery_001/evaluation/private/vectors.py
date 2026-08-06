"""
evaluation/private/vectors.py

Deterministic stimulus generators for the FSM-recovery grading harness.
Output format: each line is "rst in" (two integers, space-separated),
matching the column order read by tb_compare.v's $fscanf(fh, "%d %d", rst, in).
The first tuple in every sequence is always (1, 0): one synchronous
reset cycle, per the design brief's reset semantics.

Only Python's stdlib `random` module is used, with fixed seeds, so results
are fully reproducible across runs and across machines.
"""

import random

RANDOM_SEEDS = [101, 202, 303, 404, 505]
RANDOM_LEN = 64  # minimum post-reset cycle count required by FR4


def random_sequences():
    """Return a list of 5 sequences, each a list of (rst, in) tuples.

    Each sequence starts with one reset cycle (1, 0) followed by >=64
    cycles of (0, bit) with bit drawn from a seeded PRNG.
    """
    sequences = []
    for seed in RANDOM_SEEDS:
        rng = random.Random(seed)
        seq = [(1, 0)]
        for _ in range(RANDOM_LEN):
            bit = rng.randint(0, 1)
            seq.append((0, bit))
        sequences.append(seq)
    return sequences


def _bits_from_string(bitstr):
    return [int(c) for c in bitstr]


def adversarial_sequences():
    """Return a list of >=2 hand-built adversarial sequences targeting the
    '1011' pattern-detection boundary conditions.

    (a) reset, then '10110111011' -- back-to-back overlapping near-matches
        of the '1011' pattern, stressing non-overlapping detection logic.
    (b) reset, then '1011' bits with a synchronous reset pulse injected
        mid-stream (right after a partial '10' prefix has been seen
        again), then resumes with '1011' -- stresses reset-mid-pattern
        recovery to the initial state.
    """
    sequences = []

    # (a) overlapping near-matches back to back: 1 0 1 1 0 1 1 1 0 1 1
    seq_a = [(1, 0)]
    for bit in _bits_from_string("10110111011"):
        seq_a.append((0, bit))
    sequences.append(seq_a)

    # (b) '1011' once, then a partial '10' prefix, then a mid-stream reset
    # pulse, then '1011' resumes -- exercises synchronous reset recovery
    # right in the middle of tracking a partial pattern.
    seq_b = [(1, 0)]
    for bit in _bits_from_string("1011"):
        seq_b.append((0, bit))
    # Start a new partial match: "10"
    for bit in _bits_from_string("10"):
        seq_b.append((0, bit))
    # Mid-stream synchronous reset pulse (one cycle), interrupting the
    # partial "10" prefix before it can complete to "1011".
    seq_b.append((1, 0))
    # Resume normal operation and complete a fresh, unambiguous match.
    for bit in _bits_from_string("1011"):
        seq_b.append((0, bit))
    # Add a few more trailing cycles including another full match to be
    # thorough about post-reset recovery correctness.
    for bit in _bits_from_string("001011"):
        seq_b.append((0, bit))
    sequences.append(seq_b)

    return sequences


def write_vectors(path, seq):
    """Write a sequence of (rst, in) tuples to `path`, one "rst in" pair
    per line, matching the column convention consumed by tb_compare.v.
    """
    with open(path, "w", encoding="utf-8") as f:
        for rst, in_bit in seq:
            f.write("%d %d\n" % (rst, in_bit))