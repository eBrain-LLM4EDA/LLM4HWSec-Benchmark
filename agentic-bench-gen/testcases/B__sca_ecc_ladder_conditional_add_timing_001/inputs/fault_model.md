# Observation Model — scalar_mult_ctrl / field_datapath

This document describes the measurement setup available to someone
characterizing the runtime behavior of `scalar_mult_ctrl.v` in
simulation. It does not describe any part of the RTL's internal
implementation beyond what is needed to drive it and record its
outputs.

## Operating assumptions

- `scalar` is presented once, held stable for the single cycle on
  which `start` is asserted, and is not required to remain stable
  afterward. The controller latches it internally at the start of
  processing.
- `start` should be pulsed for exactly one cycle while the controller
  is idle (i.e., not currently between a previous `start` and the
  corresponding `done`).
- `done` asserts for exactly one cycle once processing for the given
  scalar has finished. `result_x` and `result_y` are valid in that
  same cycle and remain latched (holding their last value) until the
  next completed run.
- The controller may be restarted with a new `scalar` value as soon as
  `done` has been observed; there is no requirement to wait any
  additional cycles beyond that.

## Debug/analysis ports

Three additional outputs are provided purely for use in simulation
and are not part of any production interface:

- `state` — the controller's current 3-bit control state, sampled on
  every clock edge.
- `cycle_count` — a running count of clock cycles elapsed since the
  most recent `start` pulse. It increments once per cycle while the
  controller is processing.
- `cycle_count_valid` — asserted for exactly one cycle, in the same
  cycle as `done`, indicating that `cycle_count` reflects the total
  number of cycles taken to complete that run.

These signals can be probed directly in a testbench (e.g. via
hierarchical reference or simple output ports on the top-level
instance) without modifying the module under test.

## Suggested measurement procedure

A simple procedure for building a table of scalar values against
their corresponding cycle counts:

1. Reset the design.
2. Drive `scalar` to a chosen 16-bit value and pulse `start` for one
   cycle.
3. Wait until `done` (equivalently `cycle_count_valid`) asserts.
4. Record the pair `(scalar, cycle_count)`.
5. Repeat from step 2 with a new `scalar` value (no reset is required
   between runs, only that the controller be idle).

Because `scalar` can be varied freely across independent runs, and
`cycle_count` is captured precisely at completion, this procedure is
sufficient to build an arbitrarily large table mapping input scalar
values to the number of clock cycles the controller took to process
them, entirely from the outputs already exposed by the module. The
`state` trace can additionally be recorded across the same run to see
which control states were visited and in what order for a given
scalar.

This is intended purely as a black-box, simulation-based measurement
methodology for characterizing timing behavior as a function of the
input scalar — it does not require any modification to
`scalar_mult_ctrl.v` or `field_datapath.v`. Any cycle-count figures
reported from this methodology should come directly from running the
provided RTL with the scalar in question, rather than from an
analytically derived estimate, since small differences in how
operation start/completion cycles are counted can otherwise lead to
mismatches with an independent simulation of the same design.