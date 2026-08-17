# Conditional Point-Addition Timing in a Scalar-Multiplication Controller

## Overview

`inputs/scalar_mult_ctrl.v` implements a small double-and-add controller
that computes a scalar multiple of a base point using a compact field
datapath (`inputs/field_datapath.v`). The controller processes a 16-bit
scalar from bit 15 down to bit 0, performing one DOUBLE operation per
bit and, depending on the scalar bit value, an ADD operation.

Your job is to analyze the **timing / cycle-count behavior** of this
controller as a function of the input scalar, and to characterize the
control-flow states involved, then propose a concrete RTL-level fix
that makes the cycle count **independent of the scalar** while still
producing correct results.

You do not need to modify any RTL. This is a pure analysis task: you
read the provided design, optionally simulate it yourself, and write
your findings into a single JSON report.

## Provided artifacts (do not edit)

- `inputs/scalar_mult_ctrl.v` — the controller module (`scalar_mult_ctrl`).
- `inputs/field_datapath.v` — the multi-cycle field datapath used for
  DOUBLE and ADD operations (`field_datapath`).
- `inputs/design_brief.md` — functional description of the interface,
  state machine, and datapath timing.
- `inputs/fault_model.md` — describes the observation methodology
  available to you: you may drive `scalar` and `start` repeatedly with
  different 16-bit values and observe `done`, `result_x`, `result_y`,
  and the debug ports (`state`, `cycle_count`, `cycle_count_valid`)
  in simulation.

**Do not modify anything under `inputs/`.** Only files under
`submission/` are graded.

## Tooling

`iverilog` and `vvp` are available in the environment if you want to
build your own testbench to drive `scalar_mult_ctrl` with different
scalar values, capture `cycle_count` when `cycle_count_valid`/`done`
assert, and tabulate the results. This is strongly recommended: your
report's cycle-count data will be checked against an independent
simulation of the provided RTL, so any numbers you report should come
from actually running the design under test with the scalars you
report, not from a hand-derived formula.

## What to submit

Write your findings to:

```
submission/vulnerability_report.json
```

This is the **only** file that is graded. It must be a single JSON
object with exactly the following top-level fields:

| Field | Type | Description |
|---|---|---|
| `vulnerable_signal` | string | The signal/condition that gates the scalar-dependent behavior. |
| `vulnerable_states` | string | The FSM state(s) whose entry depends on the scalar. |
| `timing_dependency_description` | string | How and why cycle count varies with the scalar. |
| `remediation_description` | string | Plain-language description of your proposed fix. |
| `remediation_rtl_sketch` | string | Concrete RTL-level sketch of the fix (enough detail to identify it precisely — e.g. what gets executed unconditionally, what gets muxed, and on what condition). |
| `preserves_correct_output` | boolean | Whether your remediation still produces correct scalar-multiplication results. |
| `cycle_count_range` | object | `{ "min": <int>, "max": <int> }` — the min/max `cycle_count` you observed across the scalars you tested. |
| `cycle_counts_by_scalar` | array | List of `{ "scalar": <int>, "cycle_count": <int> }` entries. |

### Requirements on `cycle_counts_by_scalar`

You must include **at least four distinct 16-bit scalars**, chosen so
that they span:

- at least one scalar with **low Hamming weight** (≤ 2 set bits),
- at least one scalar with **high Hamming weight** (≥ 14 set bits),
- at least two scalars with **intermediate** Hamming weight.

Each `cycle_count` value must be reproducible by running the provided
`scalar_mult_ctrl.v` (unmodified) with the corresponding scalar in
simulation — your data will be cross-checked against an independent
`iverilog` simulation of the same design. Numbers that were only
estimated or derived analytically, without actually simulating the
provided RTL, may not match and will be marked inconsistent.

## Guidance

- Think about which states are entered on every bit versus only some
  bits, and how that relates to the scalar value.
- A meaningful characterization of the timing behavior should let you
  predict, for an arbitrary scalar, roughly how its cycle count
  compares to others — express that relationship in
  `timing_dependency_description`, but back any specific numbers with
  actual simulation output rather than a guessed formula.
- A good remediation should make the controller's cycle count and
  state sequence identical for every possible scalar, without changing
  the final `result_x`/`result_y` for any scalar. Vague fixes (e.g.
  "add random delay") that don't equalize the actual cycle count are
  not sufficient.
- Be explicit and concrete in `remediation_rtl_sketch` — describe what
  operation(s) execute unconditionally each bit, where their result
  goes when it should not be committed, and how the real accumulator
  update is selected.

## Starting point

A placeholder `submission/vulnerability_report.json` is included with
empty/naive content. It will **fail** grading as shipped — replace its
contents entirely with your own analysis before submitting.