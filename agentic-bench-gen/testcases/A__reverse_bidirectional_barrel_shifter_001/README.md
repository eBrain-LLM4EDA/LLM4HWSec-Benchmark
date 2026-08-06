# Recover a Bidirectional Barrel Shifter

## Background

A legacy bit-manipulation IP block has come to you with all hierarchy and
meaningful signal names stripped out during a netlist-flattening pass. What
remains is a purely combinational gate-level netlist built from staged
multiplexer trees, with obfuscated internal net names. You have two things
to work with:

- `inputs/net_shifter_flat.v` — the flattened, gate-level reference netlist.
  It is fully combinational (no clock, no latches) and implements an 8-bit
  variable shift/rotate unit.
- `inputs/design_brief.md` — a short legacy design brief describing the
  intended pinout and the semantics of the block's documented operating
  modes.

Your job is to reverse-engineer the netlist into clean, readable,
word-level Verilog that is **bit-for-bit behaviorally identical** to the
original netlist for every possible input combination.

## What you must produce

Write a single self-contained Verilog file at:

```
submission/recovered_rtl.v
```

It must define exactly this module, with exactly these ports (no more, no
fewer), matching widths and directions precisely:

```verilog
module barrel_shifter_top (
    input  [7:0] data_in,   // 8-bit operand to be shifted or rotated
    input  [2:0] amount,    // shift/rotate amount, 0 through 7
    input        direction, // 0 = left, 1 = right
    input  [1:0] mode,      // 00 = logical shift, 01 = arithmetic shift,
                            // 10 = rotate, 11 = unspecified in the brief
    output [7:0] data_out
);
```

This module is **purely combinational**: `data_out` must settle to its
final value within the same simulation time step as any change to
`data_in`, `amount`, `direction`, or `mode`. There is no clock, no reset,
and no internal state anywhere in this design. Do not add registers,
latches, or any additional ports beyond the ones listed above.

## Known (documented) semantics

The design brief describes three operating modes of the block, based on
the `mode` and `direction` fields:

- **mode = 00 (logical shift):** shift `data_in` by `amount` bits, filling
  vacated bits with zero, in the direction given by `direction`.
- **mode = 01 (arithmetic shift):** when shifting right, sign-extend using
  the original MSB of `data_in` into the vacated high bits; when shifting
  left, behaves the same as the logical left shift in mode 00.
- **mode = 10 (rotate):** rotate `data_in` by `amount` bits in the
  direction given by `direction`, with bits that fall off one end
  re-entering on the opposite end (rotation is modulo 8, matching the
  8-bit operand width).

`amount` ranges over 0 through 7 and `direction` is a single bit (0 =
left, 1 = right) for all three modes above.

## The gap you need to close

The design brief documents only three of the four possible values of the
2-bit `mode` field. The fourth encoding, `mode = 11`, was never assigned a
defined meaning in the original documentation — but the netlist you have
is a real, physically-fielded circuit, and its multiplexer tree produces
*some* concrete, deterministic output for every input vector, including
every vector with `mode = 11`. There is no "don't care" in a real gate
network: every combination of `mode`, `direction`, `amount`, and `data_in`
drives a fully determined value out of the tree.

Your recovered RTL will be checked against the reference netlist by
**exhaustive simulation** across the entire input space — that includes
every `mode = 11` vector. Treating `mode = 11` as free (e.g. leaving it
unassigned, defaulting to `x`, or guessing an arbitrary constant) will not
match the netlist's actual resolved behavior and will fail grading. You
must determine, by inspecting and/or simulating `net_shifter_flat.v`
directly, exactly what the netlist produces for `mode = 11` across the
input space, and reproduce that behavior in your RTL.

Similarly, be careful not to conflate the arithmetic-shift mode's
right-shift sign-extension behavior with its left-shift behavior — these
follow different fill rules, and the netlist is the ground truth for
which is which.

## How grading works

Grading is **purely behavioral simulation**, not source inspection. The
evaluator will:

1. Compile `inputs/net_shifter_flat.v` and `submission/recovered_rtl.v`
   together with a generated testbench using `iverilog`.
2. Drive both the reference netlist instance and your
   `barrel_shifter_top` instance with identical input vectors, covering
   the full input space (`data_in` × `amount` × `direction` × `mode`,
   8192 combinations total — small enough to exhaust completely).
3. Compare `data_out` from both instances on every single vector.

A submission **passes only if every vector matches exactly**, including
every `mode = 11` vector and every arithmetic-shift edge case. Any single
mismatch — anywhere in the input space — is a FAIL, and the first
diverging vector will be reported.

Secondary, informational-only signals may also be reported (such as
structural similarity of your RTL's decomposition to a reference
implementation via equivalence-checking tools), but these do not affect
PASS/FAIL; only the exhaustive behavioral comparison determines the
outcome.

## Constraints

- `submission/recovered_rtl.v` must be a single, self-contained file:
  synthesizable Verilog-2001 or SystemVerilog compatible with
  `iverilog`/`yosys`, with no external includes.
- Do not modify `inputs/net_shifter_flat.v` or `inputs/design_brief.md` —
  only `submission/recovered_rtl.v` is graded.
- Do not use vendor-specific or non-free simulation primitives; only
  constructs supported by `iverilog`/`yosys` are permitted.
- The port list must match the pinned interface exactly — same name,
  same widths, same directions, no extra ports.

## Starting point

A placeholder file is already present at `submission/recovered_rtl.v`. It
compiles, but it does not implement any real shifting or rotating logic,
so it will fail the behavioral comparison against the reference netlist.
Replace its contents with your reverse-engineered implementation.

## Toolchain

You can use `iverilog`, `vvp`, and `yosys` locally to explore
`net_shifter_flat.v`'s behavior (e.g. writing your own scratch
testbenches) before finalizing your submission. The evaluator uses the
same toolchain to grade your final answer.