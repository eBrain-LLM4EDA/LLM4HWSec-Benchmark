# Design Brief: 8-bit Bidirectional Shift/Rotate Unit

**Document status:** Recovered from legacy project archive. Original
authors and revision history are unavailable. This brief reflects the
best-known documentation for the block at the time of archival; some
encodings were left unassigned in the original specification and are
noted below.

## Overview

This block implements an 8-bit combinational shift/rotate unit used as a
datapath element in a larger bit-manipulation IP core. It takes an 8-bit
operand and produces a shifted or rotated 8-bit result based on a
mode/direction/amount control word. The unit is purely combinational:
there is no clock, no reset, and no internal state. The output is valid
in the same evaluation step as the inputs.

## Pinout

| Signal      | Width | Direction | Description                                             |
|-------------|-------|-----------|-----------------------------------------------------------|
| `data_in`   | 8     | input     | Operand to be shifted or rotated                          |
| `amount`    | 3     | input     | Shift/rotate amount, unsigned, range 0–7                  |
| `direction` | 1     | input     | Shift/rotate direction: 0 = left, 1 = right                |
| `mode`      | 2     | input     | Operating mode select (see table below)                    |
| `data_out`  | 8     | output    | Result of the shift/rotate operation                       |

## Operating Modes

The `mode` field selects between the operation families supported by the
unit. `direction` selects left vs. right within whichever mode is active.
`amount` gives the number of bit positions involved, 0 through 7
inclusive (an `amount` of 0 is a no-op: `data_out = data_in`).

### mode = 00 — Logical shift

The operand is shifted left or right by `amount` bit positions. Bits
shifted out of the operand are discarded, and vacated bit positions are
filled with zero, regardless of shift direction.

- `direction = 0` (left): `data_out` = `data_in` shifted left by
  `amount`, with zeros filling the low-order bits vacated by the shift.
- `direction = 1` (right): `data_out` = `data_in` shifted right by
  `amount`, with zeros filling the high-order bits vacated by the shift.

### mode = 01 — Arithmetic shift

This mode is intended for signed operands.

- `direction = 1` (right): `data_out` is the arithmetic right shift of
  `data_in` by `amount` bit positions. The vacated high-order bits are
  filled by replicating the original sign bit (`data_in[7]`), i.e. the
  sign is preserved/extended into the vacated positions.
- `direction = 0` (left): there is no distinct "arithmetic left shift"
  operation in this unit; a left shift in this mode behaves the same as
  the logical left shift described under mode 00 (zero-fill of the
  vacated low-order bits).

### mode = 10 — Rotate

The operand is rotated (circularly shifted) by `amount` bit positions.
Bits shifted out of one end of the operand re-enter at the opposite end,
so no information is lost — this is a bijective permutation of the input
bits for any given `amount`.

- `direction = 0` (left): `data_out` = `data_in` rotated left by
  `amount` bit positions (bits leaving the top re-enter at the bottom).
- `direction = 1` (right): `data_out` = `data_in` rotated right by
  `amount` bit positions (bits leaving the bottom re-enter at the top).

Rotation amounts are effectively taken modulo 8, matching the operand
width, so `amount` values 0 through 7 each produce a distinct rotation
(an `amount` of 0 leaves the operand unchanged, consistent with the
general no-op rule above).

### mode = 11 — Reserved / unassigned

This encoding of `mode` was never assigned a function in the original
design documentation available in the archive. No specification,
truth table, or design note describing the intended behavior of
`mode = 11` was preserved. It is unknown from this brief alone whether
this encoding was reserved for a future feature, intended to be
unreachable in normal operation, or simply never finalized before the
unit was taped out.

The unit that was actually fabricated and fielded, however, is a fixed
piece of combinational logic: for every possible input vector — including
every vector where `mode = 11` — the real circuit produces some
concrete, repeatable 8-bit output. Whatever that behavior turns out to
be, it is a property of the physical netlist, not of this document.
Anyone working from the fielded design who needs the unit's behavior
under `mode = 11` should treat this brief as silent on the matter and
determine the actual behavior directly from the netlist itself.

## General notes

- All arithmetic in this unit operates on 8-bit unsigned bit vectors
  except where explicitly noted as sign-preserving (mode 01, right
  shift).
- `amount` is always taken as an unsigned 3-bit value, 0 through 7.
- The unit has no notion of overflow or carry-out; `data_out` is always
  exactly 8 bits wide.
- This brief describes external, observable behavior only. It makes no
  claims about internal implementation structure, gate count, or timing
  characteristics of the fielded netlist.