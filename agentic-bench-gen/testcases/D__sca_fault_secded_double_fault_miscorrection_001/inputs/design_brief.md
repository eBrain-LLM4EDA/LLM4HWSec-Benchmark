# Design Brief: 8-bit Extended-Hamming SECDED Codec

## Purpose

This module implements a Single-Error-Correcting, Double-Error-Detecting
(SECDED) codec for an 8-bit data memory protection subsystem. It is intended
to protect a stored 8-bit value against transient bit-flip faults (e.g.
radiation-induced upsets, glitches on a memory bus) by encoding the data into
a larger, redundant codeword before storage, and by decoding + checking that
codeword when the data is read back.

The scheme is the classical "extended Hamming code": a (12,8) Hamming code
augmented with one additional overall parity bit, giving a 13-bit codeword
that stores 8 data bits and carries 5 bits of redundancy in total.

## Codeword Layout

The 13-bit codeword vector is indexed 0 through 12. The bit assignment is:

- **Bit position 0**: the overall (extended) parity bit. It is computed as
  the parity (XOR) of all of the other 12 bits in the codeword.
- **Bit positions 1, 2, 4, 8**: the four Hamming parity bits. Each one is the
  parity of a specific subset of the data bits, chosen according to the
  standard Hamming bit-numbering scheme (a bit position contributes to
  Hamming parity bit `2^k` if and only if bit `k` of that position's binary
  index is set).
- **All remaining bit positions (3, 5, 6, 7, 9, 10, 11, 12)**: the 8 data
  bits, placed in ascending order of bit position (the lowest-numbered
  non-parity position holds the least-significant data bit, and so on up to
  the highest-numbered position holding the most-significant data bit).

## Intended Decode Semantics

On decode, the codec re-derives the four Hamming parity checks from the
stored (possibly faulty) codeword and packs the results into a 4-bit
**syndrome**. Under standard Hamming-code theory:

- If the syndrome is **zero**, the four parity groups are each internally
  consistent, which (in the absence of an overall parity violation) normally
  indicates the codeword is either free of errors or contains an even number
  of errors that happen to cancel out across the Hamming parity structure.
- If the syndrome is **nonzero**, its numeric value identifies a single bit
  position that, if flipped, would restore consistency with all four parity
  groups.

The codec additionally recomputes the **overall/extended parity bit** by
XOR-ing all codeword bits together and comparing it against a fresh XOR of
the received bits, producing an `overall_parity_error` flag. In classical
SECDED theory, the syndrome and the overall parity flag are meant to be used
*together* to distinguish between the three cases that a real ECC memory
subsystem must handle differently:

- **Zero errors**: syndrome is zero and the overall parity check passes.
- **Exactly one bit flipped**: the syndrome is nonzero and points at the
  flipped position (or, for an error in the overall parity bit itself,
  syndrome zero with a parity mismatch), and the overall parity check is
  consistent with a single flip. This case is safely correctable by
  XOR-flipping the indicated bit.
- **Exactly two bits flipped**: the pattern of syndrome and overall parity
  together should indicate that an even (specifically double) number of
  errors has occurred, which is a case a single-error-correcting code cannot
  safely repair. A conformant SECDED decoder is expected to raise this as a
  *detected but uncorrectable* condition rather than attempt a correction,
  since blindly trusting the syndrome value in this situation could produce
  a "corrected" codeword that does not match the original data.

## Output Signals

- `syndrome`: 4-bit Hamming syndrome derived from the four parity checks.
- `overall_parity_error`: 1-bit flag from the extended parity check.
- `correctable`: intended to indicate that the decoder has decided a
  single-bit correction can safely be applied.
- `uncorrectable`: intended to indicate that a detected error pattern cannot
  be safely corrected and should be flagged to the surrounding system rather
  than silently "fixed."
- `correction_mask`: the bit-flip mask that would be applied to repair a
  correctable single-bit error.
- `data_out`: the 8 data bits recovered after any applied correction.

## Usage Context

This codec is intended to sit between a memory array and the rest of a
larger system (e.g. a register file, key-storage element, or safety-critical
state holder). Downstream logic is expected to consult `correctable` and
`uncorrectable` to decide whether to trust `data_out` for a given read, since
re-verifying data integrity independently at every consumer would be
prohibitively expensive.