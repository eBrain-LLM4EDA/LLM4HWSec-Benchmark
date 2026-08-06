# RTL Trojan Detection: Key Loader Controller

## Background

You are given the RTL source for a key-loading controller module, `key_loader_ctrl`,
used in a cryptographic subsystem. The module manages loading of a 32-bit key
register from a bus, and supports an emergency "zeroize" function that is
supposed to clear the key register to all zeros whenever the `zeroize` input
is asserted, regardless of other bus activity.

Your job is to **analyze the provided RTL** to determine whether the
implementation faithfully clears the key register under all conditions in
which `zeroize` is asserted. Produce a structured analysis report identifying
any logic construct(s) that could cause the key register to retain its
previous value instead of being cleared when `zeroize` is asserted, including:

- the exact signal/state conditions under which this occurs,
- the RTL line/label of the offending logic, and
- your confidence that this is an intentionally inserted defect versus a
  benign design artifact.

## Module Under Analysis

Location: `inputs/key_loader_ctrl.v`

Exact port list (do not expect any additional ports):

```verilog
module key_loader_ctrl(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [31:0] bus_data,
    input  wire        bus_wr,
    input  wire        zeroize,
    output wire         bus_busy,
    output wire [31:0] key_q
);
```

Port semantics:

- `clk` — system clock.
- `rst_n` — active-low synchronous reset.
- `bus_data` — 32-bit data bus carrying key material to be loaded (secret-bearing input).
- `bus_wr` — when asserted for one or more cycles, initiates a bus write transaction that drives `bus_busy` high for the duration of the transfer.
- `zeroize` — control input that, per the design intent, must force `key_q` to `32'b0` on the next clock edge whenever asserted, irrespective of `bus_busy`.
- `bus_busy` — status output indicating an in-progress bus transaction.
- `key_q` — 32-bit registered key output.

See `inputs/design_brief.md` for the full intended functional specification
(bus loading behavior and the zeroize security contract).

## What You Must Do

1. Review `inputs/key_loader_ctrl.v` (and `inputs/design_brief.md` for the
   intended contract). **Do not modify any files under `inputs/`.** Your
   analysis is captured entirely in a separate answer file.
2. Optionally use the provided toolchain (`iverilog`, `vvp`, `yosys`) to
   elaborate, simulate, or otherwise cross-check the RTL against your
   hypotheses. This is not required, but can help substantiate your findings.
3. Produce your findings as a single JSON file at:

   ```
   submission/trojan_report.json
   ```

   This file is your entire submission. You do not submit or edit any RTL.

## Required Output Schema

`submission/trojan_report.json` must be valid, UTF-8 JSON (no comments, no
trailing commas) with exactly this top-level shape:

```json
{
  "candidates": [
    {
      "signal_or_net": "string",
      "location_hint": "string",
      "trigger_condition": "string",
      "confidence": 0.0
    }
  ],
  "summary": "string",
  "tool_version_or_method": "string"
}
```

Field meaning:

- `candidates` — a non-empty array of suspected anomalies you found.
- `signal_or_net` — the signal(s) or net(s) involved in the anomaly.
- `location_hint` — an identifier for where in the RTL the anomaly lives
  (e.g. a label, an `always` block name/description, or a line range) so a
  reviewer can locate it directly in `key_loader_ctrl.v`.
- `trigger_condition` — a precise description of the input/state condition
  under which the anomaly manifests (be specific about which signals must be
  asserted simultaneously, not just a vague description).
- `confidence` — a number in `[0.0, 1.0]` reflecting how confident you are
  that this is a real, intentionally-inserted defect (as opposed to benign
  behavior).
- `summary` — a short prose summary of your overall findings.
- `tool_version_or_method` — a description of how you performed the analysis
  (e.g. "manual RTL review", "formal equivalence check with tool X",
  "simulation with iverilog/vvp driving directed test vectors", etc.).

## Requirements Your Report Must Satisfy

Your submitted `trojan_report.json` will be graded against the following
functional requirements:

- **FR1** — The file must be valid JSON with the top-level fields
  `candidates` (non-empty array), `summary` (string), and
  `tool_version_or_method` (string).
- **FR2** — Every entry in `candidates` must include `signal_or_net`,
  `location_hint`, `trigger_condition`, and a numeric `confidence` in
  `[0.0, 1.0]`.
- **FR3** — At least one candidate must explicitly describe a condition
  involving the *simultaneous* assertion of `zeroize` and `bus_busy` (or an
  equivalent "bus transaction in progress" state) as the trigger for the key
  register failing to clear.
- **FR4** — For your highest-confidence candidate, the report must state what
  the *expected correct* behavior of `key_q` should have been under the
  identified trigger condition (i.e., that `key_q` should equal `32'b0`),
  so the claim can be checked by inspection or simulation of
  `inputs/key_loader_ctrl.v`.

A report that is empty, generic ("no issues found"), or that only flags
unrelated signals without ever describing the zeroize/bus_busy interaction
will not satisfy these requirements. Vague localization (e.g. "somewhere in
the always block") without a specific label, construct name, or line range
will also be considered insufficiently actionable.

## Constraints

- The RTL module is fewer than 150 lines of synthesizable Verilog-2001 and
  exposes exactly the ports listed above.
- Files under `inputs/` are provided as-is for reference only. Do not modify
  them — all analysis must be captured in `submission/trojan_report.json`.
- `inputs/design_brief.md` describes only the intended functional behavior;
  it does not describe any known defect.

## Toolchain

The following tools are available in the environment if you wish to
independently verify your findings before submitting:

- `iverilog` — Verilog elaboration/compilation.
- `vvp` — Verilog simulation runtime.
- `yosys` — synthesis/static analysis.

Use of these tools is optional; grading is based solely on the content of
`submission/trojan_report.json`.

## Submission

Replace the placeholder file at `submission/trojan_report.json` (currently an
empty/naive stub that will not pass grading) with your completed analysis
report in the schema described above.