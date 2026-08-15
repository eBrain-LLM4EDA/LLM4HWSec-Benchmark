#!/usr/bin/env python3
"""
evaluation/private/harness_support.py

Private helper module imported by evaluation/evaluate.py. Provides
deterministic (fixed-seed, no wall-clock dependence) test-vector
generation and small parsing utilities shared across FR1-FR4/SR1-SR4
checks. Not referenced from any participant-facing documentation.

Nothing in this module inspects or depends on the submission's source
text; it only produces inputs that are driven through the compiled
harness binary, and the numeric knobs (vector counts, tolerances) used
to decide PASS/FAIL for the timing-based check.
"""

import random

# ---------------------------------------------------------------------------
# Fixed seed -- deterministic across runs, independent of wall clock.
# ---------------------------------------------------------------------------
_SEED = 0xC0FFEE_1234
_rng = random.Random(_SEED)


def _rand_bytes16():
    return bytes(_rng.randrange(0, 256) for _ in range(16))


# ---------------------------------------------------------------------------
# FR1: known-answer vector
# plaintext = bytes 0..15, key = 0xFF repeated 16 times.
# ---------------------------------------------------------------------------
FR1_PLAINTEXT = bytes(range(16))
FR1_KEY = bytes([0xFF] * 16)


# ---------------------------------------------------------------------------
# FR2 / FR3 / SR3: random pairs + edge-case keys
# ---------------------------------------------------------------------------
_RANDOM_PAIRS_MIN = 100


def random_pairs(count=120):
    """Deterministically generate `count` (plaintext, key) byte-pairs.
    count must be >= 100 to satisfy FR2's "at least 100" requirement."""
    if count < _RANDOM_PAIRS_MIN:
        count = _RANDOM_PAIRS_MIN
    pairs = []
    for _ in range(count):
        pt = _rand_bytes16()
        key = _rand_bytes16()
        pairs.append((pt, key))
    return pairs


def edge_case_pairs():
    """Edge-case (plaintext, key) pairs: all-zero key, all-0xFF key,
    alternating 0x55/0xAA keys, combined with a couple of representative
    plaintexts (all-zero and the FR1 known-answer plaintext)."""
    plaintexts = [
        bytes([0x00] * 16),
        FR1_PLAINTEXT,
        bytes([0xAA] * 16),
    ]
    keys = [
        bytes([0x00] * 16),
        bytes([0xFF] * 16),
        bytes([0x55, 0xAA] * 8),
        bytes([0xAA, 0x55] * 8),
    ]
    pairs = []
    for pt in plaintexts:
        for key in keys:
            pairs.append((pt, key))
    return pairs


# ---------------------------------------------------------------------------
# SR1: fixed plaintext, many distinct random keys
# ---------------------------------------------------------------------------
_SR1_MIN_KEYS = 200
_SR1_FIXED_PLAINTEXT = bytes([0x3C] * 16)


def sr1_vectors(count=200):
    """Return (fixed_plaintext, list_of_distinct_keys) with at least
    `count` (>= 200) *distinct* 16-byte keys, generated deterministically."""
    if count < _SR1_MIN_KEYS:
        count = _SR1_MIN_KEYS
    seen = set()
    keys = []
    # Local RNG derived from the module-level seed but sequenced
    # independently so ordering of calls to other generators doesn't
    # perturb this set's determinism across evaluate.py runs.
    local_rng = random.Random(_SEED ^ 0xA5A5A5A5)
    while len(keys) < count:
        candidate = bytes(local_rng.randrange(0, 256) for _ in range(16))
        if candidate in seen:
            continue
        seen.add(candidate)
        keys.append(candidate)
    return _SR1_FIXED_PLAINTEXT, keys


# ---------------------------------------------------------------------------
# SR2: timing vectors -- two key-distribution groups + repeat count +
# the pinned tolerance constants used to judge timing invariance.
# ---------------------------------------------------------------------------
_SR2_FIXED_PLAINTEXT = bytes([0x11] * 16)
_SR2_GROUP_SIZE = 24
_SR2_REPEAT_COUNT = 400

# Generous tolerance: relative difference between the two groups' mean
# per-call elapsed time may not exceed this ratio. Kept generous to
# avoid false positives from measurement noise on shared CI hardware,
# while still catching a gross key-dependent branch/loop-bound leak
# (e.g. an early return or a data-dependent inner loop).
TIMING_TOLERANCE_RATIO = 0.35
# Absolute floor (ns) used as the denominator when average timings are
# extremely small, to avoid dividing by a near-zero average blowing up
# the relative-difference computation.
TIMING_ABS_FLOOR_NS = 200.0


def _majority_zero_key(local_rng):
    """A key whose bit pattern is majority-zero: mostly 0x00 bytes with
    a few sparsely set bits, still varying byte-to-byte so it is not a
    single degenerate constant."""
    out = bytearray(16)
    for i in range(16):
        b = 0
        for bit in range(8):
            # ~12.5% chance any given bit is set -> majority-zero bits.
            if local_rng.randrange(0, 8) == 0:
                b |= (1 << bit)
        out[i] = b
    return bytes(out)


def _majority_one_key(local_rng):
    """A key whose bit pattern is majority-one: mostly 0xFF bytes with a
    few sparsely cleared bits, still varying byte-to-byte."""
    out = bytearray(16)
    for i in range(16):
        b = 0xFF
        for bit in range(8):
            # ~12.5% chance any given bit is cleared -> majority-one bits.
            if local_rng.randrange(0, 8) == 0:
                b &= ~(1 << bit)
        out[i] = b & 0xFF
    return bytes(out)


def timing_vectors():
    """Return (plaintext, group_a_keys, group_b_keys, repeat_count).

    group_a is majority-zero-bit-pattern keys, group_b is
    majority-one-bit-pattern keys; both groups are the same size so a
    correct, constant-time implementation's summed timings should match
    within TIMING_TOLERANCE_RATIO regardless of key content."""
    local_rng = random.Random(_SEED ^ 0x5EED5EED)
    group_a = [_majority_zero_key(local_rng) for _ in range(_SR2_GROUP_SIZE)]
    group_b = [_majority_one_key(local_rng) for _ in range(_SR2_GROUP_SIZE)]
    return _SR2_FIXED_PLAINTEXT, group_a, group_b, _SR2_REPEAT_COUNT


# ---------------------------------------------------------------------------
# SR4: keys chosen to reproduce the baseline's parity-triggering
# condition (its `key_parity_check` XORs low bits of odd bytes into a
# running accumulator, and prints/flags on the low bit of that
# accumulator) plus random keys, driven with a couple of representative
# plaintexts, so that a baseline-styled debug print -- if present in a
# submission -- is exercised and observed as non-empty stdout/stderr.
# ---------------------------------------------------------------------------
def _parity_of_key_bytes(key):
    """Mirror of the baseline's accumulator-based parity computation,
    used only to *select* keys likely to trip a baseline-style debug
    branch; this is exclusively test-vector selection, not a check on
    submission source."""
    acc = 0
    for byte in key:
        acc = (acc + byte) & 0xFFFFFFFF
        if byte & 0x01:
            for j in range(8):
                acc ^= (byte >> j) & 0x01
    return acc & 0xFF


def sr4_pairs():
    """Deterministic set of (plaintext, key) pairs for the SR4 silent-
    output probe: a handful of keys chosen (by brute-force search over a
    fixed deterministic sequence) so that the baseline-style parity
    computation's low bit is set (the condition under which the shipped
    baseline emits a debug line and flags a non-zero status), plus
    random keys and edge-case keys for broader coverage."""
    local_rng = random.Random(_SEED ^ 0x0BADF00D)
    plaintexts = [FR1_PLAINTEXT, bytes([0x00] * 16), bytes([0xFF] * 16)]

    triggering_keys = []
    scan_rng = random.Random(_SEED ^ 0xFEEDFACE)
    attempts = 0
    while len(triggering_keys) < 8 and attempts < 5000:
        attempts += 1
        candidate = bytes(scan_rng.randrange(0, 256) for _ in range(16))
        if _parity_of_key_bytes(candidate) & 0x01:
            triggering_keys.append(candidate)

    random_keys = [bytes(local_rng.randrange(0, 256) for _ in range(16)) for _ in range(12)]

    edge_keys = [
        bytes([0x00] * 16),
        bytes([0xFF] * 16),
        bytes([0x55, 0xAA] * 8),
        bytes([0xAA, 0x55] * 8),
    ]

    all_keys = triggering_keys + random_keys + edge_keys

    pairs = []
    for i, key in enumerate(all_keys):
        pt = plaintexts[i % len(plaintexts)]
        pairs.append((pt, key))
    return pairs


# ---------------------------------------------------------------------------
# Shared parsing / encoding utilities (hex encode/decode of 16-byte
# arrays, output-file line parsers). Kept here so evaluate.py itself
# does not need to hardcode vector counts/tolerances or duplicate
# parsing logic.
# ---------------------------------------------------------------------------

def hex16_encode(b):
    """Encode a 16-byte object as a 32-character lowercase hex string."""
    if len(b) != 16:
        raise ValueError(f"expected 16 bytes, got {len(b)}")
    return b.hex()


def hex16_decode(s):
    """Decode a 32-character hex string into 16 bytes."""
    b = bytes.fromhex(s)
    if len(b) != 16:
        raise ValueError(f"expected 16 bytes after hex-decode, got {len(b)}")
    return b


def parse_kv_line(line):
    """Parse a single KEY=VALUE line, returning (key, value) or None if
    the line is blank/malformed."""
    line = line.strip()
    if not line or "=" not in line:
        return None
    k, v = line.split("=", 1)
    return k.strip(), v.strip()


def parse_kv_text(text):
    """Parse a block of KEY=VALUE lines into a dict."""
    out = {}
    for line in text.splitlines():
        kv = parse_kv_line(line)
        if kv is None:
            continue
        k, v = kv
        out[k] = v
    return out


def parse_ct_st_line(line):
    """Parse a 'CT=<hex32> ST=<hex2>' line into (ciphertext_bytes,
    status_byte_int). Raises ValueError on malformed input."""
    vals = {}
    for tok in line.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            vals[k] = v
    if "CT" not in vals or "ST" not in vals:
        raise ValueError(f"malformed result line: {line!r}")
    ct = bytes.fromhex(vals["CT"])
    st = bytes.fromhex(vals["ST"])
    if len(ct) != 16 or len(st) != 1:
        raise ValueError(f"unexpected field length in line: {line!r}")
    return ct, st[0]


def parse_ct_st_batch(text, expected_n=None):
    """Parse a whole batch of 'CT=... ST=...' lines. If expected_n is
    given, raises ValueError on a line-count mismatch."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if expected_n is not None and len(lines) != expected_n:
        raise ValueError(f"expected {expected_n} result lines, got {len(lines)}")
    return [parse_ct_st_line(l) for l in lines]


def xor_bytes(a, b):
    """Bytewise XOR of two equal-length byte sequences."""
    if len(a) != len(b):
        raise ValueError("xor_bytes: length mismatch")
    return bytes(x ^ y for x, y in zip(a, b))