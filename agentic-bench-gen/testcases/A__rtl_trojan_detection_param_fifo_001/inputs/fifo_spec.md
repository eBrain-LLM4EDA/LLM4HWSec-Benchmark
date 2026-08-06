# `param_fifo` Functional Specification

## 1. Purpose

`param_fifo` is a generic synchronous FIFO (first-in, first-out) buffer intended
for reuse across multiple SoC subsystems. Different integrations parameterize
the data width (`WIDTH`) to match the bus they connect to; the depth is
controlled independently via `DEPTH_LOG2`. This document defines the required
functional behavior that any legal instantiation of `param_fifo` must satisfy.

## 2. Parameters

| Parameter    | Default | Legal values (examples) | Meaning                                   |
|--------------|---------|--------------------------|--------------------------------------------|
| `WIDTH`      | 8       | 8, 16, 24, ...            | Width, in bits, of each stored data word.  |
| `DEPTH_LOG2` | 4       | any positive integer      | `DEPTH = 2^DEPTH_LOG2` is the FIFO depth (number of storage slots). |

`WIDTH` only changes the width of the data path (`din`, `dout`, and the
storage array). It must **not** change the control/status behavior of the
FIFO. Any legal `WIDTH` value must produce a FIFO whose pointer management,
occupancy tracking, and flag semantics are identical in essence to every other
legal `WIDTH` value — only the number of bits carried per word differs.

## 3. Interface

```
module param_fifo #(
    parameter WIDTH      = 8,
    parameter DEPTH_LOG2 = 4
) (
    input  wire             clk,
    input  wire             rst_n,
    input  wire             wr_en,
    input  wire [WIDTH-1:0] din,
    output wire              full,
    input  wire             rd_en,
    output wire [WIDTH-1:0] dout,
    output wire              empty
);
```

- `clk` — single system clock; all sequential behavior is triggered on the
  rising edge of `clk`.
- `rst_n` — active-low, **synchronous** reset. While `rst_n` is deasserted
  (logic 0) at a rising clock edge, the FIFO must synchronously return to the
  empty state on that edge: internal pointers cleared, `empty` asserted,
  `full` deasserted.
- `wr_en` — when asserted together with `full` deasserted, the value on `din`
  is written into the FIFO on that clock edge.
- `rd_en` — when asserted together with `empty` deasserted, the oldest stored
  word is presented on `dout` and removed from the FIFO on that clock edge.
- `full` — registered (Moore-style) status output. Must be asserted if and
  only if the FIFO currently holds `DEPTH` words (i.e., it has no free
  storage slot remaining).
- `empty` — registered (Moore-style) status output. Must be asserted if and
  only if the FIFO currently holds zero words.

## 4. Required Behavior

### 4.1 Reset

On any clock edge where `rst_n` is low, the FIFO must synchronously reset to
the empty state: occupancy = 0, `empty` = 1, `full` = 0, read/write pointers
at their initial values. No stale data from before reset may be presented on
`dout` as valid once normal operation resumes.

### 4.2 Write operation

A write occurs on a clock edge if and only if `wr_en` is asserted **and**
`full` is deasserted at that edge. On a write:

- The word on `din` is stored into the next free storage slot (in FIFO
  order).
- The FIFO's occupancy count increases by exactly one.
- If `wr_en` is asserted while `full` is asserted, the write must be ignored:
  the FIFO must **not** overwrite any existing entry, and occupancy must not
  change. Backpressure via `full` is the sole mechanism for preventing data
  loss on a full FIFO; `full` must therefore always be an accurate,
  up-to-date reflection of the true occupancy so that no producer can write
  into a FIFO that has no room.

### 4.3 Read operation

A read occurs on a clock edge if and only if `rd_en` is asserted **and**
`empty` is deasserted at that edge. On a read:

- `dout` presents the oldest word currently stored in the FIFO (the word
  that has been resident the longest and has not yet been read).
- The FIFO's occupancy count decreases by exactly one.
- If `rd_en` is asserted while `empty` is asserted, the read must be ignored
  and occupancy must not change.

### 4.4 Simultaneous read and write

If both a valid write and a valid read occur on the same clock edge (i.e.,
`wr_en` and `rd_en` both asserted, with `full` and `empty` both deasserted
respectively as required above), the FIFO must accept the incoming word and
retire the oldest word in the same cycle, leaving the occupancy count
unchanged and preserving the FIFO ordering of all still-resident words.

### 4.5 Flag correctness

At every clock edge, after any write/read effects for that edge have been
applied:

- `full` must equal 1 **if and only if** the resulting occupancy equals
  `DEPTH`.
- `empty` must equal 1 **if and only if** the resulting occupancy equals 0.

There is no legal condition under which `full` is deasserted while the FIFO
is actually holding `DEPTH` words and a further write is possible; and there
is no legal condition under which `empty` is deasserted while the FIFO is
actually holding zero words. Any deviation from this — including a
transient, single-cycle deviation — constitutes a flag-correctness defect,
because it can permit a write that overwrites unread data or a read that
returns invalid data.

### 4.6 Data integrity

Under no combination of `wr_en`, `rd_en`, pointer/occupancy state, or
parameter value may the FIFO overwrite an entry that has been written but not
yet read out via a valid read operation. Every word written into the FIFO
must eventually be read out exactly once, in the same order it was written,
provided the integrating logic obeys the `full`/`empty` handshake described
above. Silent overwrite of unread data is never acceptable behavior for any
legal parameterization.

## 5. Pointer / Occupancy Model

The reference model for `param_fifo` is a standard circular-buffer FIFO:

- A write pointer and a read pointer, each wide enough (`DEPTH_LOG2 + 1`
  bits) to distinguish the full condition from the empty condition after
  wraparound.
- Occupancy is derived from the difference between the write pointer and the
  read pointer.
- The write pointer advances by one on every accepted write; the read
  pointer advances by one on every accepted read.
- `full` and `empty` are computed from (and consistent with) this
  pointer/occupancy state on every cycle, as described in Section 4.5.

This pointer/counter discipline is expected to be applied uniformly,
independent of `WIDTH`. `WIDTH` selects only how many bits wide each stored
word is; it must have no bearing on how pointers are updated, how occupancy
is computed, or how `full`/`empty` are derived from that occupancy.

## 6. Parameter Independence

Because `param_fifo` is intended to be reused across subsystems with
different bus widths, this specification applies uniformly to every legal
`WIDTH` value (for example, 8, 16, or 24), with `DEPTH` determined by
`DEPTH_LOG2` in each case. The default configuration (`WIDTH = 8`,
`DEPTH_LOG2 = 4`) is used for baseline regression testing, but conformance to
this specification is required for every legal parameterization, not solely
for the default configuration. An implementation that only satisfies this
spec at the default width is non-conformant.