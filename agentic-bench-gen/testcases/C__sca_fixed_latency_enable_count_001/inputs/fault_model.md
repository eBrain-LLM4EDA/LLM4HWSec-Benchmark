# Trace Capture Methodology

## Purpose of This Document

This document describes how the per-cycle activity traces in `traces.csv`
were captured, what each trace record represents, and how the data set is
organized. It is provided so that the traces can be interpreted correctly
during analysis.

## Observation Setup

During each transaction, an external monitor records the value of two
signals on every clock cycle, starting from the cycle `start` is sampled
and continuing for several cycles afterward:

- `mul_en` — the controller's internal accumulate-enable strobe, exposed on
  the module's output port for observability.
- `done` — the controller's completion pulse.

This kind of per-cycle activity capture is representative of what could be
obtained from a debug probe on the exposed signal, or approximated
externally via a measurement proxy (for example, monitoring supply-current
or electromagnetic activity correlated with internal switching during the
transaction window). For the purposes of this analysis, the exact physical
capture mechanism is not important; what matters is that the recorded
per-cycle values of `mul_en` and `done` faithfully reflect the controller's
actual behavior during each transaction, cycle by cycle.

## Trial Structure

Each trial in the data set corresponds to one complete transaction of
`mult_ctrl`: a single `start` pulse followed by monitoring of the
controller's outputs for 10 consecutive cycles (`cycle_index` 0 through 9
relative to the cycle `start` was sampled). This window is long enough to
capture the full 8-cycle active sequence plus one idle cycle before and
after.

For every trial:

- `secret_operand` is set to a chosen 8-bit value before the `start` pulse
  is issued.
- `public_operand` is held at a fixed constant value across **all** trials
  in the data set (see `trace_manifest.json` for the exact value used).
  Since `public_operand` never changes between trials, any differences
  observed in the captured signals across trials must be attributable to
  differences in `secret_operand` or to the controller's own internal
  sequencing.
- The controller starts each trial from a clean reset state (`rst_n`
  asserted, then released) before the `start` pulse is issued, so that
  trials are independent of one another.

## Trace Record Fields

Each row in `traces.csv` represents the state of the monitored signals on
one clock cycle of one trial. The columns are:

| Column           | Description                                                                 |
|------------------|-------------------------------------------------------------------------------|
| `trial_id`       | Integer identifier for the transaction this row belongs to. All rows sharing a `trial_id` belong to the same trial and share the same `secret_operand` value. |
| `secret_operand` | The 8-bit multiplicand value used for this trial, recorded as a hex string (e.g. `0x3F`). Constant across all rows of the same trial. |
| `cycle_index`    | Integer 0 through 9, giving the cycle position relative to the cycle on which `start` was sampled for this trial (`cycle_index = 0` is the cycle `start` was sampled; `cycle_index = 9` is one cycle after the transaction's `done` pulse). |
| `mul_en`         | The value of the `mul_en` output as observed on this cycle (0 or 1).       |
| `done`           | The value of the `done` output as observed on this cycle (0 or 1).         |

## Data Set Composition

The full data set spans a range of distinct `secret_operand` values chosen
to cover a variety of bit patterns (different numbers of set bits, as well
as different bit positions). `trace_manifest.json` records the total number
of trials included and how the sampled `secret_operand` values were
selected from the full 8-bit range.

## Notes for Analysis

- Rows should be grouped by `trial_id` (equivalently, by `secret_operand`,
  since each trial uses a single fixed operand) to reconstruct the
  per-cycle signal sequence for that transaction.
- Because every trial monitors the same 10-cycle window relative to its own
  `start` pulse, trials can be directly compared cycle-by-cycle with one
  another.
- The data set is intended to support straightforward aggregate
  computations per trial, such as counting how many cycles within a trial
  have a particular signal value, without requiring re-simulation of the
  controller — though the RTL in `mult_ctrl.v` is also provided for anyone
  who wishes to reproduce or cross-check the captured traces directly.