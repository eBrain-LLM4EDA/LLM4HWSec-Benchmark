# Fixed-Latency Multiplier Controller: Activity Trace Analysis

## Overview

`mult_ctrl` is an 8-cycle shift-add multiplier controller intended for use in
an embedded coprocessor. It multiplies a `secret_operand` byte by a
`public_operand` byte over a fixed sequence of clock cycles and reports the
result on `product` alongside a `done` pulse.

Your task is to analyze the provided RTL and the accompanying per-cycle
activity traces captured while exercising the controller across a range of
`secret_operand` values, and to produce a structured analysis report
describing:

1. The controller's timing behavior (is transaction latency constant?).
2. The relationship between the internal `mul_en` enable signal's activity
   and the bit pattern of `secret_operand` across the recorded trials.
3. Concrete recommendations for hardening the design's per-cycle switching
   behavior.

## Provided Materials (`inputs/`, read-only)

- `mult_ctrl.v` — the Verilog RTL of the controller under analysis. Ports:
  `clk`, `rst_n`, `start`, `secret_operand[7:0]`, `public_operand[7:0]`,
  `done`, `product[15:0]`, `mul_en`.
- `design_brief.md` — functional description of the module, its port list,
  and its intended use.
- `fault_model.md` — describes how the activity traces were captured (what
  an external monitor observes on `mul_en` and `done` during each
  transaction) and what the trace record fields mean.
- `trace_manifest.json` — structural metadata about `traces.csv` (trial
  count, field descriptions, sampling notes). This file intentionally
  contains no computed results.
- `traces.csv` — per-cycle records with columns
  `trial_id,secret_operand,cycle_index,mul_en,done` for a set of distinct
  `secret_operand` values, with `public_operand` held constant across all
  trials. Each trial spans `cycle_index` 0 through 9 relative to the cycle
  `start` was sampled.

You do **not** need to run a simulator to complete this task — `traces.csv`
already contains everything necessary to compute the required statistics.
However, if you want to cross-check your findings against the RTL directly,
`iverilog`/`vvp` are available in the environment and you are free to write
your own testbench against `inputs/mult_ctrl.v` for verification purposes.

## Your Task

Produce a single file at:

```
submission/vulnerability_report.json
```

containing **exactly** the following top-level fields (plain JSON, no
markdown, no extra wrapping):

```json
{
  "summary": "string",
  "timing_analysis": {
    "observed_latency_cycles": 0,
    "latency_is_constant": true
  },
  "activity_analysis": [
    {
      "secret_operand": "0x3F",
      "enable_count": 0,
      "hamming_weight": 0
    }
  ],
  "hardening_recommendations": [
    "string", "string"
  ]
}
```

### Field requirements

- **`summary`** (string): a written overview of what you found, including
  whether constant transaction latency by itself is sufficient to rule out
  information leakage from the design's internal activity.
- **`timing_analysis.observed_latency_cycles`** (integer): the number of
  cycles between `start` being sampled and `done` being asserted, as
  measured from `traces.csv`.
- **`timing_analysis.latency_is_constant`** (boolean): whether this latency
  is the same across all trials in the trace set.
- **`activity_analysis`** (array): one entry per distinct `secret_operand`
  value you analyze, covering **at least 16 distinct values** drawn from
  `traces.csv`. For each entry:
  - `secret_operand`: the operand value as a hex string (e.g. `"0x3F"`).
  - `enable_count`: the number of rows with `mul_en=1` for that operand's
    trial in `traces.csv`.
  - `hamming_weight`: the population count (number of set bits) of the
    operand byte.
- **`hardening_recommendations`** (array of strings, at least 2 entries):
  concrete, circuit-level modifications to the controller that would make
  its per-cycle switching activity uniform across all possible operand
  values — not just proposals that adjust timing or add delay around
  `done`.

## Constraints

- Do **not** modify any file under `inputs/`. Only
  `submission/vulnerability_report.json` is graded.
- Your report is graded on field presence/format as well as on the
  substantive correctness of the numbers and claims it contains — cross-check
  your `enable_count` and `hamming_weight` values carefully against
  `traces.csv` (and, optionally, against a fresh simulation of
  `inputs/mult_ctrl.v`).
- A starter file already exists at `submission/vulnerability_report.json`.
  It is a placeholder and will not pass grading — replace its contents with
  your own analysis.

## Getting Started

1. Read `design_brief.md` for the functional intent of the module.
2. Read `fault_model.md` to understand what the columns in `traces.csv`
   represent and how the traces were captured.
3. Inspect `inputs/mult_ctrl.v` to understand exactly how `mul_en` and
   `done` are driven cycle by cycle.
4. Load `traces.csv` and, for each distinct `secret_operand` value, compute
   the count of cycles where `mul_en=1` and compare it against the operand's
   bit pattern.
5. Write your findings and recommendations into
   `submission/vulnerability_report.json` following the schema above.