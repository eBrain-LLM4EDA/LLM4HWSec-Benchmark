#!/usr/bin/env python3
"""
evaluation/private/reference.py

Reference PKCS#7 padding-validation oracle for the CBC unpad kernel
(`pad_check`) under test, plus deterministic vector construction used
by evaluate.py as the single source of truth for expected outputs
across FR1-FR3 and SR2.

This module is intentionally free of any hardcoded crypto tables or
recalled constants: `reference_pad_check` is pure PKCS#7 arithmetic
matching the ground-truth semantics exactly:

  - Let N = block[15].
  - If N == 0 or N > 16: invalid, unpadded_len = 16.
  - Else if any of block[16-N .. 15] != N: invalid, unpadded_len = 16.
  - Else: valid, unpadded_len = 16 - N.

`make_vectors()` builds the deterministic (fixed-seed, no true
randomness) vector set covering:
  - all valid padding lengths N = 1..16 (including the fully-padded
    N=16 boundary, where the entire block is padding),
  - invalid last-byte cases (0, 17, 255),
  - adversarial mismatch-position blocks for N=8 with the corrupted
    byte placed explicitly at the first byte of the padding region
    (offset 8), the middle of the padding region (offset 11), and the
    last byte of the padding region before the length byte itself
    (offset 14).

This module is imported by evaluate.py; it is not itself a test
harness and prints nothing.
"""

import random

BLOCK_SIZE = 16


def reference_pad_check(block):
    """
    block: a sequence (bytes/bytearray/list) of exactly 16 integers in
    0..255.

    Returns (valid, unpadded_len) exactly per the hidden ground-truth
    PKCS#7 semantics:
      - N = block[15]
      - N == 0 or N > 16          -> (0, 16)
      - any of block[16-N:16]!=N  -> (0, 16)
      - otherwise                 -> (1, 16-N)
    """
    if len(block) != BLOCK_SIZE:
        raise ValueError(f"block must be exactly {BLOCK_SIZE} bytes, got {len(block)}")

    n = block[15]
    if n == 0 or n > 16:
        return 0, 16

    start = BLOCK_SIZE - n
    for i in range(BLOCK_SIZE - 1, start - 1, -1):
        if block[i] != n:
            return 0, 16

    return 1, start


def to_hex(block):
    """Render a 16-byte sequence as a 32-character lowercase hex string."""
    if len(block) != BLOCK_SIZE:
        raise ValueError(f"block must be exactly {BLOCK_SIZE} bytes, got {len(block)}")
    return "".join("%02x" % (b & 0xFF) for b in block)


def _filler_byte(seed_rng, avoid_value):
    """
    Deterministic pseudo-random filler byte (0..255) that is guaranteed
    not to equal avoid_value, so filler bytes never accidentally satisfy
    a padding comparison they aren't meant to.
    """
    v = seed_rng.randint(0, 255)
    if v == avoid_value:
        v = (v + 1) & 0xFF
    return v


def make_valid_vectors(seed=1234):
    """
    One vector per valid PKCS#7 padding length N = 1..16.

    For each N: the last N bytes equal N; the leading (16-N) bytes are
    deterministic pseudo-random filler bytes (fixed seed) each guaranteed
    not to equal N, so no incidental extra matches occur outside the
    intended padding region. N=16 is included as the fully-padded
    boundary case: the entire block is padding, and there is no filler
    prefix at all.

    Returns a list of (label, bytes) tuples.
    """
    rng = random.Random(seed)
    vectors = []
    for n in range(1, 17):
        block = bytearray(BLOCK_SIZE)
        for i in range(BLOCK_SIZE - n):
            block[i] = _filler_byte(rng, n)
        for i in range(BLOCK_SIZE - n, BLOCK_SIZE):
            block[i] = n
        vectors.append((f"valid_len{n}", bytes(block)))
    return vectors


def make_invalid_lastbyte_vectors(seed=5678):
    """
    Blocks whose last byte is 0, 17, or 255 (each individually invalid
    as a PKCS#7 length byte), with deterministic pseudo-random filler
    for the remaining 15 bytes (fixed seed).

    Returns a list of (label, bytes) tuples.
    """
    rng = random.Random(seed)
    vectors = []
    for n in (0, 17, 255):
        block = bytearray(BLOCK_SIZE)
        for i in range(BLOCK_SIZE - 1):
            block[i] = rng.randint(0, 255)
        block[15] = n & 0xFF
        vectors.append((f"invalid_lastbyte_{n}", bytes(block)))
    return vectors


def make_mismatch_vectors(seed=9012):
    """
    Adversarial single-byte-mismatch vectors for a fixed valid padding
    length N = 8. The length byte (offset 15) is always kept equal to 8
    so the length byte itself remains well-formed; exactly one byte
    within the 8-byte padding region [8..15] is corrupted (forced to a
    value different from 8) at each of three explicit positions within
    that region:

      - offset 8  : the FIRST byte of the padding region
                    (label 'mismatch_region_first_offset8'). In a naive
                    end-to-start (15 -> 8) early-exit scan, this
                    mismatch is discovered only after every other byte
                    of the padding region has already been examined,
                    i.e. this is the worst case for such a scan (most
                    comparisons executed before detection).
      - offset 11 : the MIDDLE of the padding region
                    (label 'mismatch_region_middle_offset11'). Roughly
                    half of the padding region must be scanned before
                    this mismatch is discovered in a naive end-to-start
                    scan.
      - offset 14 : the LAST byte of the padding region before the
                    length byte itself (label
                    'mismatch_region_last_offset14'). In a naive
                    end-to-start scan this is the very first byte
                    (after the length byte) that gets compared, so this
                    mismatch is discovered immediately (fewest
                    comparisons executed before detection).

    These labels intentionally describe *position within the padding
    region* (first/middle/last), which is the framing FR3 and SR3 use,
    as distinct from the "distance scanned from the end of the block"
    framing SR1 uses for the same underlying offsets.

    The non-padding prefix (offsets 0..7) is filled with deterministic
    pseudo-random filler bytes (fixed seed), each guaranteed not to
    equal 8, matching the "keep everything outside the intended
    mismatch irrelevant to the padding check" property.

    Returns a list of (label, bytes) tuples.
    """
    rng = random.Random(seed)
    n = 8
    base = bytearray(BLOCK_SIZE)
    for i in range(BLOCK_SIZE - n):
        base[i] = _filler_byte(rng, n)
    for i in range(BLOCK_SIZE - n, BLOCK_SIZE):
        base[i] = n

    positions = {
        "region_first_offset8": 8,
        "region_middle_offset11": 11,
        "region_last_offset14": 14,
    }

    vectors = []
    for label, off in positions.items():
        block = bytearray(base)
        corrupted = (block[off] + 1) & 0xFF
        if corrupted == n:
            corrupted = (corrupted + 1) & 0xFF
        block[off] = corrupted
        vectors.append((f"mismatch_{label}", bytes(block)))
    return vectors


def make_vectors():
    """
    Build and return the full deterministic vector table used across
    FR1, FR2, FR3, and SR2:

      [(label, block_bytes), ...]

    covering all valid padding lengths (1..16, including the N=16
    fully-padded boundary), invalid last-byte cases (0, 17, 255), and
    the three adversarial region-position mismatch vectors for N=8
    described in make_mismatch_vectors().

    Every vector's expected (valid, unpadded_len) can be obtained via
    reference_pad_check(block), guaranteeing a single source of truth
    shared by every consumer (evaluate.py, harness invocations) instead
    of duplicating expected values in multiple places.
    """
    vectors = []
    vectors.extend(make_valid_vectors())
    vectors.extend(make_invalid_lastbyte_vectors())
    vectors.extend(make_mismatch_vectors())
    return vectors


if __name__ == "__main__":
    # Simple self-check when run directly (not used by evaluate.py at
    # grading time, but useful for sanity-checking this module in
    # isolation).
    for label, block in make_vectors():
        valid, unpadded_len = reference_pad_check(block)
        print(f"{label:24s} hex={to_hex(block)} valid={valid} unpadded_len={unpadded_len}")