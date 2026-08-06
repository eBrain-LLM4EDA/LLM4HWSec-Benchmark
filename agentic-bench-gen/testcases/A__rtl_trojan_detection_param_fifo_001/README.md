# RTL Security Review: Parameterized FIFO

## Objective

You are given the RTL source for a parameterized synchronous FIFO (`param_fifo`) that is reused across several SoC integration projects. Different teams instantiate this FIFO with different data widths (`WIDTH`) depending on the bus they connect to, while the depth is controlled by `DEPTH_LOG2`.

Your job is to review the RTL and produce a security analysis report identifying any suspicious or malicious logic in the design, including **any parameterization under which the design's behavior deviates from the documented FIFO contract** (correct `full`/`empty` flag semantics, no silent data corruption, no overwrite of unread data).

Analyze the design across its legal parameter space — do not limit your analysis to the default configuration. The module may be instantiated with several different `WIDTH` values in different subsystems, and a flaw that never manifests at the default width could still manifest at another legal width chosen by a downstream integrator.

## Input Artifacts

All inputs are under `inputs/` and must **not** be modified:

- `inputs/param_fifo.v` — the RTL source under analysis (module `param_fifo`).
- `inputs/fifo_spec.md` — the documented functional specification the FIFO is supposed to satisfy for any legal `WIDTH`.
- `inputs/testbench_default.v` — a regression testbench that exercises only the default configuration (`WIDTH=8`), included so you can see what verification is already being done and reason about its coverage gaps.

## Module Under Analysis

```
module param_fifo #(
    parameter WIDTH      = 8,
    parameter DEPTH_LOG2 = 4
) (
    input  wire             clk,
    input  wire             rst_n,
    input  wire             wr_en,
    input  wire [WIDTH-1:0] din,
    output wire              full,
    input  wire             rd_en,
    output wire [WIDTH-1:0] dout,
    output wire              empty
);
```

- `clk` — single clock, posedge-triggered.
- `rst_n` — active-low, synchronous reset.
- `wr_en` / `din` — write a word when `full` is deasserted.
- `rd_en` / `dout` — read the oldest word when `empty` is deasserted.
- `full` / `empty` — registered, Moore-style status outputs.
- `WIDTH` default is `8`; the module is expected to support at least three legal parameterizations (e.g. 8, 16, 24) per `inputs/fifo_spec.md`.

Do not rename or otherwise reinterpret these ports in your analysis — refer to them exactly as above in your report.

## What You Submit

This is a **report-grading task**. You do not submit or modify RTL. You submit a single JSON answer file:

```
submission/trojan_report.json
```

Only this file is graded. Everything under `inputs/` is reference material for your analysis and must be left untouched.

### Required schema

`submission/trojan_report.json` must be a valid JSON object with the following shape:

```json
{
  "findings": [
    {
      "trigger_condition": "string, required, non-empty",
      "payload_effect": "string, required, non-empty",
      "confidence": 0.0,
      "rationale": "string, required, non-empty",
      "affected_parameters": "string, optional"
    }
  ],
  "summary": "string, required"
}
```

Field notes:

- `findings` is a required array. It may be empty **only if** you conclude, after full analysis, that no malicious or anomalous logic exists — in that case `summary` must state clearly that no malicious logic was detected.
- Each finding's `trigger_condition` must describe the specific internal condition (parameter value(s), pointer/counter state, and/or control-signal combination) under which the anomaly occurs. Avoid vague claims that a flaw "occurs on every write" if it is in fact conditional.
- Each finding's `payload_effect` must describe the concrete functional consequence in terms of the FIFO's documented outputs/behavior (e.g., an incorrect `full`/`empty` value or timing, or an overwrite of unread data) — not a vague statement like "may be insecure."
- `confidence` is a number in `[0.0, 1.0]`.
- `rationale` should explain why you believe this is the case (e.g., referencing specific lines/blocks of the RTL and how they deviate from `inputs/fifo_spec.md`).
- `affected_parameters`, if present, should name the specific parameter values (e.g., a specific `WIDTH`) for which the behavior deviates from spec, as distinct from parameter values for which the FIFO behaves correctly.
- Order findings so that your highest-confidence, most relevant finding is not buried beneath unrelated or low-value observations.

## Guidance

- Consider the full legal parameter space, not just `WIDTH=8`. The spec in `inputs/fifo_spec.md` claims uniform behavior "in essence" across all legal `WIDTH` values (e.g. 8, 16, 24) — verify whether the RTL actually honors that claim for each value, or whether some parameterization selects different internal logic that departs from the documented contract.
- `inputs/testbench_default.v` only ever instantiates the default configuration. Passing that testbench does not by itself establish that every legal parameterization is free of issues — you may want to reason about (or simulate) other configurations directly.
- `iverilog` and `vvp` are available in your environment if you want to write your own quick testbenches against `inputs/param_fifo.v` at non-default parameter values to confirm or refute a hypothesis before writing it up. This is optional but can help you justify your `confidence` values.
- Focus on correctness relative to `inputs/fifo_spec.md`: flag/timing correctness, data-integrity (no overwrite of unread entries), and honest handling of the occupancy/pointer state. Avoid flagging ordinary, spec-compliant generate-based parameterization as suspicious merely because it exists — the goal is to find genuine deviations from the documented contract, not every occurrence of conditional or parameterized code.

## Getting Started

A placeholder file already exists at `submission/trojan_report.json`. It is a minimal, schema-valid but empty report — you are expected to replace its contents with your actual findings before submitting.