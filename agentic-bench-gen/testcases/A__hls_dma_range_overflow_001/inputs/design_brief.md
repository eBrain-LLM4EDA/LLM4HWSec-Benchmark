# Design Brief: DMA Descriptor Range Validator

## Context

This module is part of the memory-mapped I/O (MMIO) subsystem for an
HLS-generated DMA engine. Before the engine issues a transfer, a hardware
descriptor is parsed into four plain 32-bit fields:

- `base` — the starting address of the requested transfer.
- `length` — the number of bytes the transfer will move.
- `region_start` — the starting address of the memory region the requester
  is permitted to touch.
- `region_size` — the size, in bytes, of that permitted region.

All four values are ordinary public `uint32_t` quantities. There is no
secret data involved anywhere in this check — the validator's job is purely
about arithmetic correctness of address-range containment, not about
protecting confidential information.

`validate_dma` is the single gatekeeping function that decides, ahead of
time, whether the requested transfer window is allowed. The transfer engine
calls this function once per descriptor and only proceeds with the actual
transfer if it returns a non-zero result. No memory is read or written by
this function itself — it is a decision function only.

## Interval Semantics

Both the requested transfer and the allowed region are expressed as
half-open byte intervals:

- Requested transfer: `[base, base + length)`
- Allowed region: `[region_start, region_start + region_size)`

The requested transfer is valid only when it is a full subset of the
allowed region: every byte address the transfer would touch, from `base`
up to but not including `base + length`, must fall within
`[region_start, region_start + region_size)`.

An interval of length zero does not describe any real transfer of bytes,
so it should never be treated as a valid request regardless of where
`base` happens to point.

## Performance / Structural Constraints

This function sits directly in the hot path of descriptor processing and
is synthesized as fixed-function combinational/pipeline logic in the HLS
flow, so it must:

- Execute in O(1) time — a fixed, small number of arithmetic and
  comparison operations, independent of the actual values of `base`,
  `length`, `region_start`, or `region_size`.
- Contain no loops of any kind. The interval containment check must be
  expressed purely through arithmetic and comparisons, never by iterating
  over the byte range.
- Perform no memory access whatsoever. None of the four parameters should
  ever be treated as an address to dereference — they are plain integers
  describing addresses and sizes, not pointers to be read through.
- Introduce no I/O, no dynamic allocation, and no dependence on external
  or global state. The result must depend only on the four input values.

## Correctness Expectations

`base`, `length`, `region_start`, and `region_size` can each independently
take on any value representable in 32 bits. The validator is expected to
produce the mathematically correct containment decision for **every one**
of the 2^32 × 2^32 × 2^32 × 2^32 possible input combinations — including
values near the extreme ends of the 32-bit range (close to `0x00000000`
or close to `0xFFFFFFFF`).

When implementing the interval arithmetic, keep in mind that intermediate
sums such as `base + length` or `region_start + region_size` can, for some
input combinations, exceed what a 32-bit unsigned integer can represent.
Any implementation must be evaluated carefully to ensure that such large
intermediate quantities are still compared correctly against one another,
so that the final containment decision always reflects the true numeric
relationship between the requested window and the allowed region rather
than an artifact of how the intermediate sum happened to be represented.
More generally, the function must be free of undefined behavior for every
possible combination of inputs, and its return value must always be
derivable purely from arithmetic — never from a partial or coincidentally
correct comparison that only happens to work for common-case inputs.

## Summary

`validate_dma` is a small but security-relevant building block: every
descriptor the DMA engine processes passes through it, and its correctness
directly determines which memory the engine is allowed to touch. Treat it
as a precise mathematical predicate over four public 32-bit integers, and
verify its behavior extensively at the edges of the representable integer
range, not just for typical mid-range values.