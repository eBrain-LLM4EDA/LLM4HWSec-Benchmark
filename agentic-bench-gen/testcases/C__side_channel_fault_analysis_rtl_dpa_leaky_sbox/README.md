# Power Side-Channel Leakage Analysis — S-box Round Datapath

## Objective

You are given a small single-round substitution datapath (`round_datapath.v`) that
mixes an 8-bit plaintext byte with an 8-bit round key, passes the result through an
S-box lookup, and then applies a linear diffusion stage before producing the round
output. Your job is to analyze the **data-dependent switching activity** of every
register in this datapath under a Hamming-distance (HD) power model, and report
which registers exhibit measurable data-dependent leakage across the provided
input vector set, along with concrete hardening recommendations.

This is a report-writing task, not an RTL-modification task. You will not change
any of the provided design files. You will produce a single JSON analysis report.

## Inputs

All files below are provided under `inputs/` and must not be modified:

- `round_datapath.v` — the RTL module under analysis (`round_datapath`), containing
  the registers you must evaluate.
- `sbox_table.v` — the combinational S-box lookup module (`sbox_lut`) instantiated
  by the datapath.
- `testbench_hd_trace.v` — a self-contained Verilog testbench that drives the
  datapath with a representative set of plaintext/round-key vectors and prints
  the value of every register on every clock cycle.
- `power_model.md` — the exact Hamming-distance leakage/power model definition
  and variance formula you must use to turn raw register traces into a single
  `hd_variance` number per signal.
- `design_brief.md` — a plain-English description of the datapath architecture
  and the list of signals in scope for this analysis.

## What you need to do

1. Read `design_brief.md` to understand the datapath and the full list of
   registers in scope for analysis.
2. Simulate the design to obtain register-level traces:

   ```
   iverilog -g2012 -o sim.out inputs/round_datapath.v inputs/sbox_table.v inputs/testbench_hd_trace.v
   vvp sim.out
   ```

   This prints, for every simulated cycle and every (plaintext, round_key)
   combination in the testbench, the values of `plaintext_reg`, `key_mix_reg`,
   `sbox_out_reg`, and `round_out_reg`.

3. For each register, apply the Hamming-distance power model defined in
   `power_model.md` to the trace: compute `HD = popcount(R_prev XOR R_curr)` for
   every consecutive-cycle transition observed in the simulation, across all
   vector combinations, and then compute the variance of that HD population
   exactly per the formula given in `power_model.md`.
4. Decide, for each signal, whether its measured `hd_variance` indicates
   data-dependent (and specifically key-dependent) leakage worth flagging, given
   how it compares to the other signals' variances.
5. Write up hardening recommendations for whichever signals you flag, naming a
   concrete countermeasure mechanism (e.g. masking, dual-rail/precharge logic,
   isolation, hiding) rather than generic advice.

## Required output

Write your findings to:

```
submission/vulnerability_report.json
```

This is the **only** file you should create or modify. Do not edit anything
under `inputs/`, and do not add other output files — the evaluator only reads
this one submission file.

A naive placeholder file already exists at this path. It is intentionally
incomplete and will not pass evaluation — you must replace its contents with
your own analysis before submitting.

### Schema

The file must be valid JSON with exactly this shape:

```json
{
  "signals": [
    {
      "signal_name": "string — must exactly match a register name from round_datapath.v",
      "hd_variance": 0.0,
      "flagged": true,
      "notes": "optional string"
    }
  ],
  "recommendations": [
    {
      "target_signal": "string — must match a signal_name listed above",
      "technique": "string — named countermeasure mechanism",
      "rationale": "string — why this signal needs this treatment"
    }
  ]
}
```

Rules:

- `signals` must contain one entry for every register documented in
  `design_brief.md` (i.e. every register declared in `round_datapath.v`) — an
  incomplete list will be scored as incomplete coverage.
- `hd_variance` must be a plain JSON number (not a string), computed as
  described above.
- `flagged` must be a plain JSON boolean.
- `notes` is optional free text per signal.
- Every `recommendations[].target_signal` must reference a `signal_name` that
  also appears in the `signals` array — do not recommend hardening for a
  signal you didn't analyze.
- Extra top-level keys beyond `signals` and `recommendations` are ignored, but
  no other top-level keys are required.

## Constraints

- Do not modify any file under `inputs/`.
- Do not add files anywhere other than `submission/vulnerability_report.json`.
- All numeric values must be plain JSON numbers; all boolean values must be
  plain JSON `true`/`false`.
- Your reasoning/methodology can go in the `notes` and `rationale` fields, but
  the report must stand on its own as structured JSON — no separate prose
  report is graded.

## Toolchain

`iverilog` and `vvp` are available in the environment for simulating the
provided RTL and testbench. `yosys` is also available if you want to inspect
the design's structure, though it is not required to complete the analysis.