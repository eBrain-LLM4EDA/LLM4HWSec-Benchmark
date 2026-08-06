# RTL Review: LFSR-based Random Number Generator with Health Monitor

## Objective

You are reviewing a third-party RTL implementation of an 8-bit LFSR-based
random number generator core, `lfsr_rng`, supplied together with its design
brief. Your job is to compare the implemented Verilog against the documented
behavior in `inputs/design_brief.md` and report any structural discrepancies
you find between the two: their location in the RTL, a description of the
discrepancy, and your confidence that each one is a real, security-relevant
defect (as opposed to benign coding style or a documentation nit).

You must **not modify any files under `inputs/`**. Your analysis is delivered
purely as an answer file at:

```
submission/trojan_report.json
```

This repository ships a placeholder at that path. Replace its contents with
your own analysis before submitting.

## Provided Artifacts (`inputs/`)

- `lfsr_rng.v` — the RTL implementation under review (synthesizable
  Verilog-2001, compatible with `iverilog`).
- `design_brief.md` — the vendor's documentation of the intended design:
  polynomial, tap positions, reset behavior, handshake timing, and health
  monitor behavior.
- `testbench_stub.v` — a minimal, non-self-checking testbench you can extend
  to drive `lfsr_rng` and observe its outputs over time using `iverilog` and
  `vvp`.

## Interface Under Review

Module: `lfsr_rng`

| Signal | Direction | Width | Description |
|---|---|---|---|
| `clk` | input | 1 | System clock, posedge-active. |
| `rst_n` | input | 1 | Active-low synchronous reset. |
| `enable` | input | 1 | When 1, the LFSR advances one step per clock edge; when 0, state is held. |
| `rand_out` | output | [7:0] | Combinationally equal to the current internal state register. |
| `output_valid` | output | 1 | Registered signal. |
| `health_error` | output | 1 | Registered signal. |

Documented timing behavior (see `design_brief.md` for full detail):

- While `rst_n == 0`, on the next `posedge clk` the internal state register
  must be loaded with the fixed seed `8'hA5`, `output_valid` must be 0, and
  `health_error` must be 0.
- `output_valid` goes high exactly 1 clock cycle after `enable` is first
  asserted following reset, and stays high thereafter while `enable` remains
  1.
- The design includes a built-in repetition-count health monitor. It must
  raise `health_error` within at most 3 clock cycles of observing more than
  4 consecutive identical `rand_out` samples while `output_valid` is high,
  and `health_error` must stay high until the next reset.

Use `design_brief.md` for the intended feedback polynomial and tap
positions; the brief does not contain the actual Verilog expressions, so you
will need to read `lfsr_rng.v` directly to determine what is actually
implemented.

## Using the Toolchain

`iverilog` and `vvp` are available in the environment. `inputs/testbench_stub.v`
gives you a starting point: it instantiates `lfsr_rng`, drives `clk`,
pulses `rst_n`, asserts `enable`, and dumps `rand_out`, `output_valid`, and
`health_error` over a run of several hundred cycles. You are encouraged to
extend a **copy** of this testbench (in your own workspace, outside
`inputs/`) to independently measure things like:

- the actual sequence period of `rand_out` after reset with `enable` held
  high,
- whether `health_error` ever asserts during a long run, and under what
  conditions.

Any numeric claims you make in your report (e.g. a period estimate) should
be something you could defend with a simulation trace.

## What to Deliver

Write your findings to `submission/trojan_report.json`. This must be a
single JSON object with exactly these top-level keys:

```json
{
  "findings": [
    {
      "id": "string",
      "location": "string",
      "description": "string",
      "confidence": 0.0
    }
  ],
  "summary": "string",
  "tool_version": "string"
}
```

Requirements:

- `findings` is an array. Each element must include `id`, `location`,
  `description`, and `confidence` (a number between 0 and 1, inclusive).
- `location` should identify where in `lfsr_rng.v` the finding applies —
  by named always block, signal name, or line number/range — so it can be
  cross-referenced against the source file.
- `description` should explain the nature of the discrepancy: what the
  design brief documents versus what the RTL actually does.
- `confidence` should reflect how confident you are that the discrepancy is
  an intentional, security-relevant defect rather than a stylistic
  difference. Findings you believe are minor or cosmetic should carry low
  confidence; findings you believe materially change the security-relevant
  behavior of the design should carry confidence reflecting that.
- `summary` is a free-text overview of your review, including any overall
  numeric observations (such as an observed or computed cycle period for
  `rand_out`) that support your findings.
- `tool_version` is a free-text string identifying your analysis
  process/tool and version (e.g. `"manual-review-1.0"` or a script name and
  version).

Only `submission/trojan_report.json` is graded. Do not rely on any other
files you create being read by the evaluator.

## Constraints

- Do not modify `lfsr_rng.v`, `design_brief.md`, or `testbench_stub.v`.
- Your submission must be valid JSON matching the schema above.
- Back up any quantitative claims (periods, timing) with something you
  could reproduce via simulation of the provided RTL.