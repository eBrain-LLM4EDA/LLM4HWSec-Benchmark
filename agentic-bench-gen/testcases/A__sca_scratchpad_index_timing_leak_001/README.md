# Secret-Dependent Scratchpad Index Timing Analysis

## Overview

This task asks you to analyze a small RTL lookup unit, `scratchpad_lookup`,
and produce a structured report describing its observable timing behavior
plus a hardening recommendation.

`scratchpad_lookup` is a dual-bank scratchpad memory lookup module. It takes
an 8-bit index (treated as a sensitive/secret-derived value), fetches the
corresponding 16-bit data word from one of two internal banks, and returns
it once ready. The high bit of the index (`index[7]`) selects which bank is
consulted; the low 7 bits (`index[6:0]`) select the offset within that bank.

Your job is to characterize how the module behaves over time as a function
of the index value, determine whether that behavior is uniform across all
index values, and — regardless of what you find — propose a hardening
strategy that gives the module constant, index-independent timing while
preserving its functional correctness.

## Input Artifacts

- **`inputs/scratchpad_lookup.v`** — The synthesizable Verilog module under
  test. Ports and timing contract are documented in `design_brief.md`.
- **`inputs/design_brief.md`** — The design specification: port list,
  timing contract (start/valid handshake), and the intended data mapping
  formulas for each bank. Use this as the reference for what "functionally
  correct" output means for a given index.
- **`inputs/fault_model.json`** — Describes the observation model you should
  assume: which signals an observer can see, what they can measure (e.g.
  cycle counts between `start` and `valid` over repeated lookups), and what
  assumptions hold about the environment (single clock domain, index is a
  sensitive input).
- **`inputs/testbench_timing.v`** — A ready-to-run testbench that exercises
  the module with a couple of representative index values and prints the
  cycle count from `start` assertion to `valid` assertion along with the
  resulting `data_out`. You can simulate it yourself:

  ```
  iverilog -g2012 -o sim inputs/scratchpad_lookup.v inputs/testbench_timing.v
  vvp sim
  ```

  Use this to empirically verify any timing claims you make in your report
  rather than guessing from the source alone.

## Objective

1. Determine whether the module's timing (cycles from `start` to `valid`)
   varies depending on the index, and if so, which bit(s) of the index
   control that variation.
2. Identify the specific RTL construct(s) (states, branches, signals)
   responsible for any timing variation you find.
3. Confirm whether `data_out` is functionally correct for every case you
   analyze (per the mapping formulas in `design_brief.md`), independent of
   how long it took to arrive.
4. Propose a concrete mitigation that makes the module's timing constant
   (independent of the index) without changing what value `data_out`
   ultimately produces for any given index.

You do **not** modify `inputs/scratchpad_lookup.v` or any other input
artifact. Your deliverable is an analysis report.

## Required Output

Write your findings to:

```
submission/vulnerability_report.json
```

This must be a single valid JSON object with **at least** the following
top-level fields:

| Field | Type | Description |
|---|---|---|
| `module_under_test` | string | Must equal `"scratchpad_lookup"`. |
| `functional_correctness_confirmed` | boolean | Whether you confirmed `data_out` is correct for both bank selections (`index[7]=0` and `index[7]=1`) per the mapping in `design_brief.md`. |
| `latency_measurements` | array of exactly 2 objects | Each object has `bank_select_bit_value` (0 or 1) and `observed_latency_cycles` (integer), reporting the measured start-to-valid cycle count for each bank selection. |
| `report_format_version` | string | Must be `"1.0"`. |
| `leaking_index_bits` | array of integers | The index bit position(s) whose value you determined to be distinguishable from the outside purely via timing. |
| `latency_divergent_paths` | array of strings | The specific RTL states/signals/branches (from `scratchpad_lookup.v`) responsible for any timing divergence you identified — be specific, not generic. |
| `mitigation` | object with `strategy` (string) and `description` (string) | A concrete, constant-latency hardening approach that removes any index-dependent timing while preserving `data_out` correctness for both banks. |

Populate `latency_measurements`, `leaking_index_bits`, and
`latency_divergent_paths` based on what you actually observe from reading
the RTL and/or simulating `testbench_timing.v` — not from assumptions.

## Notes

- `iverilog` and `vvp` are available in the evaluation environment if you
  want to simulate `testbench_timing.v` yourself to cross-check any timing
  numbers before submitting.
- Your report is graded on the accuracy and specificity of its findings
  against the actual behavior of the RTL, as well as on the presence and
  correct typing of the required fields listed above.
- A minimal or placeholder report (missing fields, empty arrays, vague
  text) will not pass grading.