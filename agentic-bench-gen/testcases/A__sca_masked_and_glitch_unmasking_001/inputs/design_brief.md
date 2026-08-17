# Design Brief: `masked_and` Module

## Purpose

`masked_and` combines two 1-bit Boolean-shared secret operands into a
single 1-bit Boolean-shared result equal to the logical AND of the
unmasked operands. Each operand is represented as two shares that
XOR together to form its true value; the output is likewise
represented as two shares, re-randomized using a fresh mask bit.

## Ports

| Port | Direction | Width | Description |
|------|-----------|-------|-------------|
| `a0` | input  | 1 | Share 0 of operand A |
| `a1` | input  | 1 | Share 1 of operand A |
| `b0` | input  | 1 | Share 0 of operand B |
| `b1` | input  | 1 | Share 1 of operand B |
| `r`  | input  | 1 | Fresh random mask bit, independent per evaluation |
| `q0` | output | 1 | Share 0 of the result |
| `q1` | output | 1 | Share 1 of the result |

## Functional Invariant

For all valid input assignments, the module must satisfy:

```
q0 XOR q1 == (a0 XOR a1) AND (b0 XOR b1)
```

That is, the shared output must reconstruct to exactly the AND of the
values that the input shares reconstruct to.

## Implementation Status

The current implementation is purely combinational: outputs are
produced directly from the inputs through a network of AND and XOR
gates with no clocked storage elements between the input ports and
the output ports. This is an interim state pending a decision on
pipeline/timing closure for the surrounding datapath; a future
revision may introduce clocked stages between the input ports and the
output ports as timing requirements are finalized.

## Review Instructions

As part of preparing this module for integration and timing closure,
review the RTL source and:

- Identify and document each internal net, what partial product or
  combination it represents, and how the four input shares and the
  mask bit feed into it.
- Trace the dataflow from inputs to outputs, noting the sequence of
  combinational stages the signals pass through.
- Note where, if anywhere, registers currently exist in the signal
  path, and characterize the timing structure implied by the current
  (purely combinational) implementation.
- Propose any register placement you believe is appropriate for the
  next revision of this module, along with a rationale grounded in
  the signal timing/arrival relationships you observed.