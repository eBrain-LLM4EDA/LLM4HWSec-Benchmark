# Design Brief: Sequential Controller Under Reverse Engineering

## Purpose of this document

This brief defines the **black-box behavioral contract** for the circuit
implemented in `flattened_netlist.v`. It tells you what the pins mean and how
the circuit's reset behaves. It intentionally does **not** describe the
internal logic, the number of internal states, their encoding, or the
specific condition that causes `out` to pulse. That information is exactly
what you are being asked to recover by reading the gate-level netlist and by
simulating the circuit with your own testbenches.

## Interface

The circuit is a single synchronous module with the following ports:

| Port  | Direction | Width | Description                                              |
|-------|-----------|-------|------------------------------------------------------------|
| `clk` | input     | 1     | Free-running clock. All internal state updates on the rising edge of `clk`. |
| `rst` | input     | 1     | Synchronous, active-high reset.                             |
| `in`  | input     | 1     | Single-bit control input, sampled on every rising edge of `clk`. |
| `out` | output    | 1     | Single-bit Moore-style output, a function of the current internal state only. |

## General nature of the circuit

The circuit is a small synchronous sequential controller. It maintains some
internal state that is updated once per rising clock edge, based on the
current state and the current value of `in`. The output `out` is a Moore
output: it depends only on the current internal state (not combinationally on
`in`), so it is stable between clock edges and changes only as a result of a
state transition on a `clk` edge.

Over time, as a sequence of values is applied to `in`, the controller's
internal state moves through some sequence of configurations, and under
certain conditions related to the recent history of `in`, the controller
produces a pulse on `out`. The exact triggering condition, the number of
distinct internal states involved, and how those states are encoded in the
gate netlist are **not specified here** — you are expected to determine them
by:

- reading `flattened_netlist.v` together with the primitive definitions in
  `primitives.v` and tracing the combinational next-state and output logic
  by hand, and/or
- writing your own scratch testbenches, driving `rst` and `in` with chosen
  sequences, simulating with `iverilog`/`vvp`, and observing the resulting
  `out` waveform to build up a behavioral model of the controller.

Do not assume any particular state count, encoding, or trigger condition in
advance; derive it from the artifact itself.

## Reset behavior

`rst` is a **synchronous, active-high** reset:

- While `rst` is asserted (driven high) at a rising edge of `clk`, the
  internal state updates on that edge to the circuit's single, fixed initial
  state.
- The output `out` corresponding to that initial state becomes visible
  starting from the same rising edge at which the state register updates
  (i.e., on the clock edge immediately following the edge at which `rst` was
  sampled high, `out` reflects the initial state).
- Holding `rst` high for more than one cycle keeps the circuit in its initial
  state; the circuit does not accumulate any input history while `rst` is
  asserted.
- Once `rst` is deasserted (driven low), the circuit resumes tracking `in` on
  subsequent rising edges starting from its initial state.
- Reset may be asserted again at any point during operation (not only at the
  very start of a simulation); each time it is asserted for at least one
  cycle, the circuit must return to the same initial state and corresponding
  output, regardless of what internal state it was previously in.

## What you need to produce

Using the netlist, the primitive library, the sample stimulus, and your own
simulation experiments, build a clear behavioral understanding of exactly
when and for how long `out` pulses relative to the history of `in`, and how
the circuit responds to `rst`. Then express that behavior as clean,
word-level Verilog (a state register plus behavioral transition/output
logic) meeting the interface and constraints described in the top-level
`README.md`. Your recovered design does not need to reuse the same number of
state bits or the same state encoding as the original netlist — only the
same observable input/output behavior, cycle for cycle, is required.