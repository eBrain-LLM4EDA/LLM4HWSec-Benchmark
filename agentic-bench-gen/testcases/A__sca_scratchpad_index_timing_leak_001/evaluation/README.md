# Evaluation: Secret-Dependent Scratchpad Index Timing Leak

## What you are analyzing

The RTL module `scratchpad_lookup` (in `inputs/scratchpad_lookup.v`) implements a
dual-bank scratchpad lookup unit. Its interface, timing contract, and data
mapping are fully specified in `inputs/design_brief.md`. An attacker model
describing what an external observer can measure (start/valid timing, but not
`index` or `data_out` directly) is described in `inputs/fault_model.json`.
`inputs/testbench_timing.v` is a reference testbench you can use (via
`iverilog`/`vvp`) to empirically characterize the module's timing behavior for
representative index values.

Your job is **not** to modify any file under `inputs/`. Instead, you submit a
single structured analysis report at:

```
submission/vulnerability_report.json
```

describing what you found: which bit(s) of `index` create an observable
timing side channel, what the measured latencies are for each case, which
RTL construct causes the divergence, and a mitigation that removes the timing
dependence while preserving functional correctness.

## How grading works

`evaluation/evaluate.py` is the grading entry point. It:

1. Confirms all required input artifacts exist under `inputs/` (fails with a
   `SETUP` error otherwise).
2. Confirms `submission/vulnerability_report.json` exists and is valid JSON
   (fails with a `SETUP` error otherwise).
3. Independently compiles and simulates the DUT (`inputs/scratchpad_lookup.v`)
   together with `evaluation/tb_leak_check.v` via `iverilog`/`vvp` to
   establish ground-truth cycle counts for representative index values,
   covering both bank selections.
4. Grades the submitted report's fields and claims against that ground truth
   and against the specification in `design_brief.md`.

Each requirement below emits exactly one `[TEST] PASS: <id>` or
`[TEST] FAIL: <id>: <reason>` line. The run exits `0` only if every
requirement passes.

## Required JSON schema

Your `submission/vulnerability_report.json` must be a single JSON object with
at least the following top-level fields (see `public_spec.response_format`
for the authoritative list):

| Field | Type | Description |
|---|---|---|
| `module_under_test` | string | Must equal `"scratchpad_lookup"`. |
| `functional_correctness_confirmed` | boolean | Whether you confirmed `data_out` is correct for both bank selections per the mapping in `design_brief.md`. |
| `latency_measurements` | array of exactly 2 objects | Each object has `bank_select_bit_value` (0 or 1) and `observed_latency_cycles` (integer), reporting the measured start-to-valid latency for each bank selection. |
| `report_format_version` | string | Must equal `"1.0"`. |
| `leaking_index_bits` | array of integers | The index bit position(s) that control the observable timing difference. |
| `latency_divergent_paths` | array of strings | Named RTL signal(s)/FSM state(s)/code construct(s) responsible for the divergent timing (concrete references into the RTL, not generic prose). |
| `mitigation` | object with `strategy` and `description` (strings) | A concrete fix that equalizes latency across both bank selections without changing `data_out`'s functional correctness. |

Extra fields are permitted and ignored; field ordering does not matter.

## What is checked

**Functional / format requirements (FR1-FR4):** presence and correct typing
of `module_under_test`, `functional_correctness_confirmed`,
`latency_measurements` (exactly 2 well-formed entries, one for each bank
selection value), and `report_format_version == "1.0"`.

**Security / substantive requirements (SR1-SR4):**

- **SR1** — Your `leaking_index_bits` must correctly identify the index bit
  that controls bank selection and access latency.
- **SR2** — Your `latency_measurements` must match the actual measured
  cycle counts for each bank selection, cross-validated against an
  independent simulation of the DUT using `evaluation/tb_leak_check.v`.
- **SR3** — Your `latency_divergent_paths` must name concrete RTL
  constructs (state names, signal names, or the branching construct
  responsible for the divergence) rather than vague/generic statements.
- **SR4** — Your `mitigation` must describe a constant-latency /
  timing-equalization strategy (e.g. padding the faster path to match the
  slower path's cycle count, or otherwise removing the index-dependence of
  the latency) and must not propose anything that would break functional
  correctness of `data_out` for either bank.

A missing, empty, or generic/placeholder report will fail multiple of the
above checks and the overall run will exit non-zero.

## Reproducing the ground-truth simulation yourself

You are encouraged to independently verify your findings before submitting,
e.g.:

```
iverilog -g2012 -o /tmp/sim.vvp inputs/scratchpad_lookup.v inputs/testbench_timing.v
vvp /tmp/sim.vvp
```

Observe the printed cycle counts for the tested index values and compare
against the timing contract described in `inputs/design_brief.md`.