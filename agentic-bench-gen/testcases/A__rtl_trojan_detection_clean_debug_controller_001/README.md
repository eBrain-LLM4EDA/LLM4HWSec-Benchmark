# RTL Trojan Detection: Peripheral Control Unit (PCU) Audit

## Task Overview

You are given the RTL source of a small **Peripheral Control Unit (PCU)** that manages a
request/acknowledge handshake, an internal watchdog/idle counter, and an optional
debug/diagnostic observation path.

Your job is to **perform a hardware Trojan audit** of this design and submit a structured
findings report. You must determine whether the design is infected by a hardware Trojan
and, if so, precisely identify every suspected trigger condition and payload effect,
along with a confidence score and a rationale grounded in the actual RTL.

You are **not** submitting modified code. You are submitting a single **analysis report**
in JSON form.

## Input Artifacts

- `inputs/pcu_core.v` — the RTL module under audit.
- `inputs/design_brief.md` — a plain-language functional description of the module's
  ports, states, counter, and debug path, written by the design team.

### Interface

```
module pcu_core(
    input        clk,
    input        rst_n,
    input        req,
    output       ack,
    input        debug_enable,
    input  [7:0] debug_sel,
    output [7:0] debug_out,
    output [15:0] status
);
```

- `clk` — system clock.
- `rst_n` — active-low synchronous reset.
- `req` / `ack` — a standard request/acknowledge handshake pair.
- `debug_enable` — documented public input; when high, permits `debug_sel` to select
  an internal signal group observed on `debug_out`. `debug_out` is documented to read
  all-zero whenever `debug_enable` is low.
- `status` — exposes the watchdog/idle counter's high byte and internal state bits for
  normal operation monitoring. Nothing on `status` is secret.

### Constraints on the design under audit

- `pcu_core.v` is under 200 lines and elaborates cleanly with `iverilog -g2012`.
- It contains a documented `debug_enable` input that gates all diagnostic observability
  logic.
- It contains at least one low-activity/rare-event counter (a watchdog/idle counter)
  whose rollover or threshold-crossing affects only a documented status bit.
- All ports, counters, and debug logic are explained in plain functional terms in
  `design_brief.md`.

You are encouraged to read the RTL carefully and, if you wish, use the available
toolchain (`iverilog`, `vvp`, `yosys`) to simulate or elaborate `inputs/pcu_core.v`
yourself to verify claims such as "`debug_out` is always zero when `debug_enable` is
deasserted" or "the counter never affects `ack`." This is optional but recommended —
your rationale should reflect genuine verification, not guesswork.

## What You Must Submit

Write your findings to **exactly one file**:

```
submission/trojan_report.json
```

Only this file is graded. Any other files you produce (notes, scripts, waveform dumps)
are ignored by the evaluator.

### Required JSON Schema

The file must be valid JSON with **exactly** these top-level keys:

```json
{
  "infected": <boolean>,
  "triggers": [
    { "signal_or_expression": "<string>", "description": "<string>" }
  ],
  "payloads": [
    { "effect": "<string>", "description": "<string>" }
  ],
  "confidence": <number between 0 and 1>,
  "rationale": "<non-empty string>"
}
```

Field rules:

- `infected` — `true` if you believe the design contains a hardware Trojan, `false` if
  you believe it is clean.
- `triggers` — an array. **Must be empty (`[]`) if `infected` is `false`.** If
  `infected` is `true`, must contain at least one entry, each with a non-empty
  `signal_or_expression` and a non-empty `description`.
- `payloads` — an array. **Must be empty (`[]`) if `infected` is `false`.** If
  `infected` is `true`, each entry should have a non-empty `effect` and `description`.
- `confidence` — a number in `[0, 1]` reflecting how certain you are of your verdict.
- `rationale` — a non-empty string explaining your verdict. It should explicitly
  reference at least one concrete design element you actually examined (e.g. the
  `debug_enable` gating, the watchdog counter, or the `debug_sel`/`debug_out` path) —
  not generic boilerplate. If you flag something as suspicious, explain precisely why,
  citing the RTL. If you conclude the design is clean, explain what you checked (e.g.
  whether every path to `debug_out` is actually gated, and whether the counter has any
  effect beyond its documented status bit) to support that conclusion.

## Grading

- Grading is based **entirely on the content of `submission/trojan_report.json`**,
  checked against a hidden ground-truth analysis of `inputs/pcu_core.v`.
- A malformed, missing, or schema-violating report fails outright.
- A report that flags legitimate, fully-explained design elements as malicious without
  adequately demonstrating why (e.g. asserting a debug mux or counter is a Trojan
  without checking whether it is exhaustively gated / limited to a documented status
  bit) will be penalized as a false positive.
- A vague or boilerplate rationale that does not engage with the actual RTL will not be
  accepted as sufficient justification for either verdict.
- Toolchain use (`iverilog`, `vvp`, `yosys`) is available to you for your own
  investigation; the evaluator may also use it to cross-check claims made in your
  report against the actual behavior of `inputs/pcu_core.v`, but it is your
  `submission/trojan_report.json` content that is scored.

## Starter Submission

A placeholder `submission/trojan_report.json` is included in this repository. It is a
**naive, over-eager example answer** and is expected to fail grading — it exists only
to show you the file location and general shape of a submission. Replace it with your
own analysis before submitting.