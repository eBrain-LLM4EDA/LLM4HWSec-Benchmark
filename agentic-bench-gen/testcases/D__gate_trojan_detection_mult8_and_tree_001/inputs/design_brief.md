# Design Brief: mult8_top — 8x8 Unsigned Array Multiplier

## Overview

This brief accompanies the gate-level netlist `mult8_netlist.v`, delivered
by a third-party vendor as part of an arithmetic IP block for integration
into a larger SoC datapath. The block implements an 8-bit by 8-bit
unsigned combinational multiplier and is intended to sit directly in the
datapath with no intervening buffering — it must be purely combinational
and free of internal state.

## Functional intent

- **Module:** `mult8_top`
- **Ports:** `a[7:0]` (multiplicand), `b[7:0]` (multiplier), `p[15:0]`
  (product)
- **Behavior:** For all valid unsigned 8-bit inputs, the output must
  satisfy `p = a * b`, computed as unsigned arithmetic. The 16-bit output
  width is sufficient to represent the full product of two 8-bit unsigned
  operands without overflow (max value 255 * 255 = 65025, which fits
  in 16 bits).
- **Timing:** The block is combinational only. There is no clock, reset,
  or enable port, and none should be required — output `p` must be a
  pure function of the current values of `a` and `b`.

## Delivery format

The vendor has supplied the design already synthesized to gate level
rather than as RTL. Per the integration contract, the netlist is
restricted to a small, fixed library of structural primitives:

```
and, or, nand, nor, not, xor, xnor, buf
```

No behavioral Verilog constructs (`always` blocks, `+`, `*`, or other
operators) appear anywhere in the file — every computation is expressed
as an explicit, named instance of one of the above primitives, wired
together with explicitly declared internal nets. This restriction was
imposed so that the block can be dropped directly into the physical
design flow without further synthesis and so that its structure is
fully inspectable prior to place-and-route.

## Review scope

Before this block is accepted for tape-out, it needs to be reviewed for:

1. **Functional correctness** — does the netlist, as delivered, actually
   compute `p = a * b` for the full input space, or are there
   discrepancies between the structural implementation and the intended
   arithmetic behavior?
2. **Structural integrity** — does every gate instance in the netlist
   plausibly belong to the multiplication function, or are there
   portions of the fan-in/fan-out graph that do not correspond to any
   part of a standard multiplier construction (partial-product
   generation followed by a carry/sum reduction tree)?
3. **Interface compliance** — do the port names, widths, and directions
   match the expected interface (`a[7:0]`, `b[7:0]`, `p[15:0]`), and is
   the module fully self-contained in a single file with a single top
   module as specified?

## What to produce

The output of this review should be a written report that:

- States whether the netlist, as delivered, is acceptable for
  integration as-is, or whether it requires further vendor
  clarification/rework before sign-off.
- Documents the gate-level composition of the netlist (counts of each
  primitive type used), to serve as a baseline record for future
  revisions of this IP block.
- Identifies, by instance name, any specific gates whose role in the
  design cannot be explained by the intended multiplication function,
  along with enough detail (in terms of the primary input bits `a` and
  `b`) to reproduce and verify the reviewer's findings using standard
  simulation tooling.

This review is a standard pre-tape-out gate to catch functional bugs,
synthesis errors, or unexplained structure introduced anywhere in the
vendor's delivery flow, and should be treated with the same rigor as any
other third-party IP acceptance review.