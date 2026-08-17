# Design Brief: Scatter-Gather Descriptor Copy Engine

## Purpose

This module implements a small scatter-gather copy engine intended for use
in DMA-style descriptor processing and packet reassembly pipelines. In
these environments, incoming data often arrives in fragments — for
example, network packet segments received out of a single contiguous
buffer, or DMA descriptor chains describing where each chunk of a larger
transfer should land in memory. Rather than requiring the caller to copy
each fragment individually, this engine accepts a list of descriptors and
performs the entire reassembly into one destination buffer in a single
call.

## Typical Use Case

A common scenario is descriptor-driven DMA transfer processing: firmware
or a driver builds up a list of descriptor entries describing fragments
of a transfer (for instance, segments of a packet, or blocks of a larger
buffered transfer), and hands that list, along with a source buffer
holding the raw fragment data and a destination buffer to reassemble
into, to this engine. The engine walks the descriptor list and produces a
fully reassembled destination buffer in one pass.

## Parameter Meanings

- **`src` / `src_len`** — The source buffer holding the raw fragment data
  to be copied out, and its total size in bytes. All fragment data for
  every descriptor is drawn from this buffer, in order.
- **`dst` / `dst_len`** — The destination buffer being reassembled into,
  and its total size in bytes. Each descriptor's data lands somewhere
  within this buffer.
- **`offsets`** — For each descriptor, the byte position within `dst`
  where that descriptor's fragment should be placed.
- **`lengths`** — For each descriptor, how many bytes of `src` that
  fragment consumes. Descriptors consume `src` sequentially: the first
  descriptor starts reading from the beginning of `src`, and each
  subsequent descriptor continues reading immediately after the previous
  one finished.
- **`desc_count`** — The number of descriptor entries in the list.

## Robustness Expectations

The destination and source buffer sizes given by the caller
(`dst_len` and `src_len`) are the authoritative bounds for their
respective buffers and must always be respected — the engine must never
place fragment data outside the space the caller has actually allocated
for either buffer, and must never read fragment source data beyond what
the caller says is actually present.

In real deployments, descriptor lists are frequently built from
configuration or negotiation data that isn't fully under the direct
control of the code calling this engine (for example, values derived from
a peer device, a configuration table, or another firmware component).
Because of this, the engine should be written defensively: it must
process the caller's inputs predictably and safely under all
circumstances, rather than assuming the descriptor list is always
well-formed.

Concretely, this means:

- The engine should return a clear success or failure status rather than
  crashing, hanging, or behaving unpredictably when given a malformed or
  out-of-range descriptor list.
- On failure, the destination buffer should be left in a clean, known
  state rather than partially reassembled — callers need to be able to
  trust that a failure status means the destination buffer was not
  touched, so they can safely retry or discard the attempt without
  worrying about leftover partial data.
- Every descriptor in the list should be considered as part of deciding
  whether the whole batch is acceptable; the engine should not commit to
  writing any data until it has established that the request, as a
  whole, is one it can safely satisfy.

This engine is intended to be a small, self-contained building block:
it should not depend on dynamic memory allocation, should behave the same
way every time it's given the same inputs, and should not require any
external libraries beyond the standard library.