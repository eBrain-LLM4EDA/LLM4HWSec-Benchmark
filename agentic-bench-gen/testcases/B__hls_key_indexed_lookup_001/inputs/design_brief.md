# Design Brief: Substitution Lookup Block

## Context

This kernel is one stage in a small HLS pipeline used to transform a
byte arriving from upstream logic into an output byte using a
per-session parameter. It is designed to be dropped into larger
synthesizable designs as a reusable building block, so it must remain
plain, portable C++ that maps cleanly onto hardware primitives (no
dynamic control flow, no heap use, no library containers).

## Data roles

- `value` — a public byte produced by upstream logic in the pipeline.
  There is nothing sensitive about this input on its own; it is visible
  elsewhere on the datapath.
- `key` — a per-session byte supplied from a protected configuration
  register. It changes between sessions but is held constant for the
  duration of a session.
- `table` — a fixed 16-entry `uint8_t` substitution table. The same
  table contents are shared across all sessions and all instances of
  this block in the design; it is not session-specific and is not
  meant to be modified at runtime.

## Interface

```cpp
uint8_t lookup(uint8_t value, uint8_t key);
```

The table referenced by the kernel is named `table` and has exactly 16
entries of type `uint8_t`. Any hardened version of this kernel must
keep this same function signature and the same table name/size — other
blocks in the surrounding design are wired to call `lookup` directly and
expect `table` to still be a 16-entry array under that name.

## Why memory access shape matters here

This block sits close to a memory interface that is observable from
outside the accelerator core — for example, by other IP blocks sharing
the same on-chip interconnect, or by external instrumentation attached
to the bus during bring-up and debug. Downstream physical designers who
integrate this block have flagged that they want its memory access
behavior to be **uniform**: the same shape of accesses to the table
should occur on every invocation, independent of which particular
`value` or `key` happened to be supplied that cycle.

Put differently: a *uniform access pattern is a design goal for this
shared memory block*. Two different calls to `lookup()`, even with
completely different inputs, should look the same from the outside in
terms of which table locations are touched, in what order, and how
many times. This is treated as a normal physical-design and interface
hygiene requirement for blocks that live near a shared, observable bus,
similar to keeping loop trip counts and control flow static for
predictable timing closure.

## Reusability expectations

Because this block is intended to be instantiated multiple times across
different pipeline configurations, its internal structure should stay
simple and synthesizable:

- Fixed-size table, fixed-trip-count loops only.
- No dynamic memory, no STL, no recursion, no exceptions.
- No control flow that varies in shape from one call to the next.

Keeping the block structurally identical on every call — regardless of
the specific `value` or `key` — makes it easier to reason about timing,
easier to integrate near shared interconnect, and easier to reuse
without surprises across the different pipeline configurations this
kernel is dropped into.