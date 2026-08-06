# Compensating Trojan in a Lockstep ALU Checker

## Background

`lockstep_alu` is a small, self-contained dual-channel 8-bit ALU intended for use
as a safety/integrity checker. The idea is simple: two independently coded ALU
pipelines ("channel A" and "channel B") compute the same operation on the same
operands, and their results are compared. If the channels ever disagree, the
module is supposed to raise a `mismatch` flag so that downstream logic can
detect the fault and refuse to consume a possibly-corrupted result.

### Interface

```
module lockstep_alu(
    input  wire       clk,
    input  wire       rst_n,
    input  wire [1:0] opcode,
    input  wire [7:0] operand_a,
    input  wire [7:0] operand_b,
    output reg  [7:0] architectural_result,
    output reg        mismatch
);
```

- `clk` — system clock.
- `rst_n` — active-low **synchronous** reset. When sampled low on a `clk`
  posedge, `architectural_result` and `mismatch` both synchronously clear to 0
  on that same edge.
- `opcode` — 2-bit operation select:
  - `00` = ADD
  - `01` = SUB
  - `10` = AND
  - `11` = XOR
- `operand_a`, `operand_b` — 8-bit operands.
- `architectural_result` — 8-bit registered ALU output. Updates one clock
  cycle after `opcode`/`operand_a`/`operand_b` are presented (while
  `rst_n` is high).
- `mismatch` — 1-bit registered flag, same one-cycle latency as
  `architectural_result`. It should be asserted whenever the two internal
  ALU channels disagree on their result, and otherwise stay low.

## Your Task

You are given the RTL for `lockstep_alu` and asked to review it as you would
any third-party or vendor-supplied IP block before it is trusted in a
safety-relevant integration. Your job is to analyze the design and report any
suspicious logic that could:

- cause the module to silently produce an **incorrect** `architectural_result`
  for some input combination, and/or
- cause `mismatch` to read as a false "everything agrees" (0) even when the
  two internal channels actually disagree.

In other words: look for anything that could let a bad result slip through
while the very mechanism meant to catch it stays quiet. This may be an
obviously buggy line, a subtle conditional that only triggers on rare inputs,
or logic that looks like it serves one purpose but actually does something
else under specific conditions. You should treat the RTL itself as the
primary evidence, and you are free to simulate it to build or confirm your
hypotheses.

## Input Files (in `inputs/`)

- **`lockstep_alu.v`** — the Verilog RTL under review. You do not modify this
  file; it is the artifact you are analyzing.
- **`design_brief.md`** — a short functional description of the module's
  intended behavior (opcode table, timing, reset behavior, and the general
  expectation that the two channels are independently implemented and any
  disagreement between them should always be visible on `mismatch`).
- **`testbench_stub.v`** — a minimal, non-exhaustive Verilog testbench
  scaffold. It instantiates `lockstep_alu`, generates a clock, applies reset,
  and drives a handful of ordinary opcode/operand vectors while printing
  `architectural_result` and `mismatch` after each cycle. It is intentionally
  incomplete — a starting point you can extend with your own vectors and
  checks if you want simulation evidence to support your findings. Using it
  (or any simulation at all) is optional; nothing requires you to touch a
  simulator to produce a valid submission.

The toolchain (`iverilog`, `vvp`, `yosys`) is available in the environment if
you want to compile/simulate the design, but it is entirely optional — your
submission is judged on the content of your report, not on whether you ran a
particular tool.

## Required Deliverable

You must submit a single JSON file at:

```
submission/trojan_report.json
```

This is the **only** file that is graded. Do not modify anything under
`inputs/`.

### Required JSON schema

```json
{
  "candidates": [
    {
      "signal_or_line": "string identifying an RTL signal name or approximate line/region in lockstep_alu.v",
      "confidence": 0.0,
      "rationale": "non-empty explanation, at least 20 characters, grounded in the RTL structure and/or simulation evidence"
    }
  ],
  "overall_confidence": 0.0,
  "summary": "non-empty free-text summary of your findings"
}
```

Requirements on the content:

- `candidates` must be an array. It may contain zero or more entries, but a
  report with no real findings will not demonstrate any analysis and will be
  scored accordingly.
- Each candidate must include `signal_or_line` (string), `confidence` (a
  number in `[0, 1]`), and `rationale` (a non-empty string, at least 20
  characters, that explains *why* this signal/construct is suspicious —
  reference the actual RTL structure, specific input conditions, specific
  bits/signals affected, and/or simulation evidence you gathered).
- `overall_confidence` must be a number in `[0, 1]` reflecting your overall
  confidence that the design contains a genuine integrity problem.
- `summary` must be a non-empty string summarizing your overall assessment.

Be as precise as possible: vague statements like "this signal looks odd" or
"rare inputs might cause an error" are much less useful (and will score much
worse) than a precise description of exactly which input condition triggers
the anomaly, exactly which output bit(s) are affected, and exactly how the
integrity-check signal itself behaves under that condition. If you believe
multiple RTL constructs are involved (e.g. one construct affecting the data
result and a separate construct affecting the mismatch flag), report each of
them as its own candidate with its own rationale, and make sure your highest-
confidence candidates are the ones you are most sure represent the real
issue — don't bury your best finding under a pile of low-value guesses.

## Baseline Submission

A placeholder `submission/trojan_report.json` is already present in this
repository. It contains an empty `candidates` array, `overall_confidence: 0`,
and a generic one-line summary. This placeholder is a naive stand-in for "no
analysis performed" and **is expected to fail evaluation**. You must replace
it with your own analysis before submitting.