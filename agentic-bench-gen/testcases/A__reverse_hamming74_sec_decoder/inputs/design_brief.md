# Design Brief: Storage Controller Codeword Decoder

## Context

The storage controller under audit was built around a small combinational
block sitting on the read datapath. Every time a stored codeword is fetched
from the underlying medium, it passes through this block before the
recovered data reaches the rest of the system. The block's job, as far as
we've been able to determine from board-level documentation (which does not
cover internals), is to catch and correct isolated bit-level corruption
introduced by the storage medium, and hand back a clean data word to the
firmware.

The RTL for this block has since been lost. All that remains is a flattened,
gate-level netlist pulled from a synthesis checkpoint (`inputs/flattened_netlist.v`).
Signal names were stripped or auto-generated during flattening, so there is
no naming information left to tell us which wires correspond to which
architectural concept. Before this block can be safely replaced, audited, or
re-integrated with new firmware, someone has to reconstruct what it actually
computes, at the word level, from its gate structure and its input/output
behavior.

## Observable interface

Whatever internal structure the netlist has, its external interface is
fixed and well understood:

- `codeword` (7 bits, input) — the raw bit pattern as read back from
  storage. It may be exactly as originally written, or it may contain a
  single corrupted bit.
- `data` (4 bits, output) — the recovered data word the rest of the system
  actually cares about.
- `corrected_codeword` (7 bits, output) — the full 7-bit pattern after any
  necessary correction has been applied. If no correction was needed, this
  should simply reproduce the input.
- `error_detected` (1 bit, output) — asserted when the block believes the
  input codeword contained a single corrupted bit that it corrected.

The block is purely combinational — there is no clock anywhere in the
netlist, and none should be introduced in a faithful reconstruction. Given a
fixed `codeword` value, all three outputs should be simple, deterministic
functions of that value alone.

## What kind of code is this, generically?

Blocks of this shape — a fixed-length codeword in, a shorter data word plus
an error flag out — are extremely common in storage and communication
systems whenever a designer wants cheap protection against isolated bit
flips: a single stuck cell, a single-event upset, a single bad sector bit,
etc. The classical approach (well documented in coding theory since the
1950s) works roughly like this:

- Not every bit position in the codeword carries "real" data. Some
  positions are reserved to carry redundancy information (traditionally
  called *parity* bits), and the remaining positions carry the actual
  payload (*data* bits).
- Each parity bit is defined to cover — i.e., its value is computed as the
  XOR of — a specific subset of the codeword's bit positions, chosen so
  that every possible single-bit error produces a *different* pattern of
  parity violations.
- On decode, the receiver recomputes each parity check against the
  received codeword. The resulting vector of "does this check pass or
  fail" bits is called the *syndrome*. If the syndrome is all zero, no
  single-bit error is present. If it is nonzero, its value (interpreted as
  a small binary number) identifies *which* codeword bit position is in
  error, and that bit is flipped to correct it.
- After correction, the data bits are simply read off the corrected
  codeword at whatever positions were originally designated as data
  positions — but the *order* in which they're presented at the output
  interface (e.g., which corrected bit becomes the MSB of the recovered
  data word) is a design choice, not something inherent to the code.

This is a well-known and widely deployed family of single-error-correcting
codes for exactly this reason: a handful of XOR trees at encode/decode time
buys detection *and* correction of any single-bit flip, at low gate cost.

## What is specifically NOT documented

Everything in the previous section is generic background, true of an entire
family of designs. It is deliberately *not* a specification of this
particular block. In particular, none of the following survived the loss of
the original RTL and are **not** given anywhere in this repository:

- Which of the 7 codeword bit positions were chosen to be parity positions
  versus data positions.
- Which specific subset of bit positions each parity check covers (i.e.,
  the exact fan-in of each XOR tree).
- How the syndrome bits are ordered/combined into a position index, and
  therefore which bit gets flipped for a given syndrome value.
- The order in which the recovered data bits are presented at the `data`
  output — i.e., which corrected codeword position becomes `data[3]`,
  which becomes `data[2]`, and so on.

All of this has to be reconstructed by analyzing `inputs/flattened_netlist.v`
directly. Don't assume any particular textbook convention applies without
verifying it against the netlist — the whole point of this exercise is that
the convention used by *this specific* implementation is exactly what's
unknown.

## Suggested analysis approach

1. **Read the gate structure.** Even with generic names, the shape of the
   netlist is informative. Look for small XOR trees that each combine a
   distinct subset of the raw `codeword` bits — these are almost certainly
   computing check/syndrome values. Separately, look for mux-like or
   case-like structures driven by those syndrome values — these are
   candidates for "decide which bit to flip." Finally, look for the final
   stage that selects which corrected bits feed the `data` output.

2. **Build truth tables.** Simulate the netlist (e.g. with `iverilog`/`vvp`)
   over representative subsets of the 128-value input space, or exhaustively
   if convenient. Compare `codeword` against `corrected_codeword` and
   `error_detected` bit by bit to see which output bits change in response
   to which single-bit perturbations of the input.

3. **Separate parity-like positions from data-like positions.** A bit
   position that participates in exactly one syndrome computation with a
   distinctive fan-in pattern, and whose value does *not* end up copied
   directly into `data`, is likely a parity position. The remaining
   positions, which do show up (post-correction) in `data`, are the data
   positions. Confirm this by checking which single-bit-flip experiments
   change `error_detected`/`corrected_codeword` versus which change `data`.

4. **Recover the syndrome-to-position mapping.** For each of the 7 possible
   nonzero syndrome values, determine experimentally which single codeword
   bit position gets flipped in `corrected_codeword`. This tells you exactly
   how the syndrome bits are ordered and combined into a bit-position index.

5. **Recover the data extraction order.** Once you know which codeword
   positions are data positions, determine — again by observing
   `corrected_codeword` versus `data` across your test vectors — which
   corrected bit lands in `data[3]`, which in `data[2]`, and so on.

6. **Re-implement, independently.** Once you're confident you understand the
   full word-level function, write your own clean RTL implementing it from
   scratch in `submission/recovered_rtl.v`, using the pinned port list.
   Don't reference or instantiate the original netlist module — the goal is
   an independently authored, readable description that reproduces its
   externally observable behavior for every one of the 128 possible
   codeword values.

## A note on validation

You are encouraged to build your own test harness against
`inputs/flattened_netlist.v` while developing your solution — simulating
all 128 codewords is cheap and will quickly reveal whether your
understanding of the parity positions, syndrome ordering, and data
extraction order is correct. The grading process performs an equivalent
exhaustive check independently; there is no shortcut around actually
recovering the correct mapping.