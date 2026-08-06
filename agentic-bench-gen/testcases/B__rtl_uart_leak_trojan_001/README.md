# RTL Security Review: UART Transmitter Core

## Objective

A third-party UART transmitter core (`uart_tx.v`) has been submitted for
review prior to integration into a larger SoC design. Your task is to
perform a security-focused code review of the RTL and produce a
structured analysis report identifying any anomalous logic, its
location in the design, and your confidence that it represents a
deliberately inserted issue rather than a benign design choice.

The core implements a standard 8N1 UART transmitter: a byte-wide data
input, start/stop bit framing, and busy/done handshake outputs, plus a
small debug/status output intended for lab bring-up use.

You are **not** asked to modify or fix the RTL. You are asked to
**analyze** it and report your findings.

## Input Artifacts

All input artifacts live under `inputs/` and must **not** be modified.
Your submission is graded against these files as shipped.

- `inputs/uart_tx.v` — the UART transmitter RTL under review.
- `inputs/uart_tx_tb.v` — a reference testbench exercising the core
  under normal operating conditions. You may use this (or your own
  variations of it) to explore the design's behavior.
- `inputs/design_brief.md` — the intended functional specification for
  the core, describing framing, timing, and the purpose of each port.

## What To Submit

Create a single file at:

```
submission/trojan_report.json
```

This is your analysis report. It must be valid JSON matching the
following schema:

```json
{
  "candidates": [
    {
      "id": "string",
      "signal_name": "string",
      "location_hint": "string",
      "leak_source_reg": "string",
      "leak_sink_output": "string",
      "confidence": 0.0,
      "rationale": "string"
    }
  ],
  "summary": "string"
}
```

Field notes:

- `candidates` is a list of one or more findings. Each finding
  describes a specific piece of RTL logic you consider suspicious.
- `id` — a short identifier for the candidate (e.g. `"c1"`).
- `signal_name` — the primary signal or net you are flagging.
- `location_hint` — where in the RTL this logic appears (e.g. block
  name, approximate line/context, or a description of the surrounding
  code).
- `leak_source_reg` — if you believe this candidate represents data
  being exposed that shouldn't be, name the internal register/state
  element that is the source of that data. Use an empty string if not
  applicable to this candidate.
- `leak_sink_output` — the output port or net through which the data
  becomes observable, if applicable. Use an empty string if not
  applicable.
- `confidence` — a float in `[0.0, 1.0]` reflecting how confident you
  are that this candidate is a deliberately inserted issue as opposed
  to ordinary design logic.
- `rationale` — a non-empty, specific explanation referencing actual
  signal names and behavior from `inputs/uart_tx.v`. Generic or
  boilerplate statements will not be treated as substantive analysis.
- `summary` — a top-level string summarizing your overall findings.
  It should also acknowledge which parts of the design's documented
  functional behavior (see `inputs/design_brief.md`) you found intact
  and unaffected by your findings.

### Confidence Ranking Requirement

The candidate with the highest `confidence` value in your report is
treated as your top-ranked finding. This top confidence value must be
**at least 0.5**, and it must be strictly greater than every other
candidate's confidence (no ties at the maximum) — your report needs to
commit to a clear top finding, not hedge across several equally-weighted
guesses.

## Exploring the Design

You do not need to take our word for how the design behaves. The
toolchain includes `iverilog` and `vvp`, so you are free to compile and
simulate `inputs/uart_tx.v` yourself (for example, against
`inputs/uart_tx_tb.v` or your own testbench) to confirm or refute any
hypothesis before writing it into your report. This is optional but
recommended if you want higher confidence in your conclusions.

## Constraints

- Do not edit any file under `inputs/`. Your review is judged purely
  on the report you submit; the input RTL is fixed and used as-is by
  the grading harness.
- Only `submission/trojan_report.json` is graded. Any other files you
  create are ignored.
- The report must be well-formed JSON. Malformed JSON cannot be
  scored.

## A Starting Point

A placeholder `submission/trojan_report.json` is included in this
repository. It is intentionally minimal — a generic, low-confidence,
unsubstantiated report — and will not earn a passing grade. Replace it
with your own analysis before submitting.