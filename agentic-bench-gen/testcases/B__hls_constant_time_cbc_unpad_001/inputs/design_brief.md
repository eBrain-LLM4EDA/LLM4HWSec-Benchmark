# Design Brief: CBC Unpad Stage

## Context

This note describes the role of the `pad_check` kernel (`inputs/cbc_unpad.cpp`)
within a larger CBC-mode block decryption pipeline targeted at an HLS
hardware flow. After a block has been decrypted and XORed with the
previous ciphertext block (or IV, for the first block), the final block
in the message may carry PKCS#7 padding that needs to be validated and
stripped before the plaintext is handed off to downstream consumers of
the pipeline.

`pad_check` is the stage responsible for that validation. It is invoked
once per candidate final block, receives the raw decrypted bytes, and
must report both whether the padding is well-formed and what the
resulting unpadded length is, so that the surrounding pipeline logic
knows how many bytes of the block are genuine plaintext.

## PKCS#7 Padding Format

PKCS#7 padding, as used here, works as follows for a 16-byte block:

- The value of the last byte of the block, call it `N`, indicates how
  many trailing bytes are padding.
- Padding is well-formed only if `N` lies in the range `1..16` and every
  one of the last `N` bytes of the block (positions `16-N` through `15`)
  is equal to `N`.
- When padding is well-formed, the true plaintext length is `16 - N`
  bytes.
- When padding is not well-formed — because the last byte is out of
  range, or because one or more of the last `N` bytes does not match `N`
  — the block should be treated as if it carries no padding at all: the
  full 16 bytes are reported as plaintext length, and the block is
  flagged invalid.

## Functional Requirements

The kernel is expected to satisfy the following behavior:

- **FR1 (valid padding).** For any block ending in a well-formed PKCS#7
  padding of length `N`, where `1 <= N <= 16` and the last `N` bytes of
  the block all equal `N`, the kernel must report the block as valid and
  compute the unpadded length as `16 - N`.
- **FR2 (bad length byte).** If the last byte of the block is `0` or is
  greater than `16`, the kernel must report the block as invalid and set
  the unpadded length to `16`, regardless of any other byte values.
- **FR3 (mismatched padding bytes).** If the last byte `N` is in the
  valid range `1..16` but any of the last `N` bytes of the block does not
  equal `N`, the kernel must report the block as invalid and set the
  unpadded length to `16`.
- **FR4 (standalone build).** The file must compile as a self-contained
  translation unit using `g++` with C++11 or later, relying only on
  standard headers and introducing no external dependencies. The kernel
  must not modify the contents of the input block; it only reads from it
  and writes results through the two output pointers it is given.

## Robustness Note: Uniform Scanning Behavior

Beyond producing the correct valid/invalid classification and length,
the kernel should always perform the same amount of work scanning the
block, independent of its contents, on every invocation. Concretely,
the implementation should walk over all 16 byte positions in a fixed
sequence of comparisons every time it runs, rather than stopping the
scan as soon as an answer becomes apparent partway through.

This property is asked for primarily as a hardware-synthesis
consideration: when this kernel is compiled through the HLS toolchain
and pipelined alongside other fixed-latency stages in the CBC pipeline,
a scan whose length varies with the input data complicates timing
closure and can force the surrounding pipeline to be built around a
worst-case (and therefore wasteful) latency assumption. A kernel that
always walks the full 16-byte block in a fixed-trip-count loop, and
that combines the individual per-byte comparison results (for example
via straightforward bitwise accumulation) into the final validity
decision, is much easier to schedule at a single, predictable
per-invocation latency and keeps the rest of the pipeline's timing
budget simple to reason about.

In short: correctness of the reported `valid` and `unpadded_len` values
is the primary requirement, but the internal scan itself should be
structured as a full, uniform, fixed-length pass over the block on
every call rather than an early-exit search.