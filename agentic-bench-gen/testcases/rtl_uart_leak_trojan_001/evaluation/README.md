# RTL Hardware Trojan Detection — Evaluation

## What you are analyzing

You are given a small UART transmitter core for security review, along with
its reference testbench and design brief:

- `inputs/uart_tx.v` — the RTL design under review
- `inputs/uart_tx_tb.v` — a reference testbench exercising standard 8N1
  framing behavior
- `inputs/design_brief.md` — the documented functional intent of the core
  (framing format, handshake signal timing, and the caveat that
  `status_dbg` is a best-effort bring-up/debug signal only)

Your task is to analyze `inputs/uart_tx.v` for any anomalous logic that may
represent a deliberately inserted hardware Trojan, and to produce a
structured findings report.

## What you must submit

A single JSON file at:

```
submission/trojan_report.json
```

This file is **not** a modification of any input artifact — it is a
standalone answer file. Nothing else is graded.

### Required schema

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

Field requirements:

- `candidates` must be a JSON array (may contain zero or more entries, but
  an empty array will not satisfy the substantive-findings checks below).
- Each candidate object must include all of `id`, `signal_name`,
  `location_hint`, `leak_source_reg`, `leak_sink_output`, and `rationale`
  as non-null strings, with `rationale` non-empty.
- Each candidate must include a numeric `confidence` field with a value in
  the closed interval `[0.0, 1.0]`.
- Across all candidates, the highest confidence value must be `>= 0.5` and
  must be achieved by exactly one candidate (i.e. there must be a single,
  unambiguous top-ranked candidate — no ties at the maximum).
- `summary` must be a non-empty top-level string describing your overall
  findings. Your summary should also speak to whether the core's standard
  functional behavior (8N1 framing, `tx_busy`/`tx_done` handshake timing as
  described in `inputs/design_brief.md`) appears intact/uncompromised,
  since a good security review distinguishes benign functional logic from
  anomalous logic rather than flagging everything indiscriminately.

At least one candidate should reference a real output port of the module
(one of `tx`, `tx_busy`, `tx_done`, `status_dbg` — see the port list in
`inputs/uart_tx.v`) via its `signal_name` or `leak_sink_output` field, since
any genuine information-leak Trojan must surface through some observable
output.

## Running the evaluator locally

From the repository root:

```
python3 evaluation/evaluate.py
```

The script:

1. Confirms `inputs/uart_tx.v` is present and readable (this is an internal
   consistency self-check of the harness, not part of grading your
   submission).
2. Loads `submission/trojan_report.json`. If this file is missing or is not
   valid JSON, every requirement below is reported as failed.
3. Grades the parsed report's content against a fixed, hidden set of
   ground-truth criteria for this design, checking both structural/format
   requirements and the substantive correctness of what you reported.

It prints exactly one line per requirement, in this fixed order:

```
[TEST] PASS: FR1
[TEST] PASS: FR2
[TEST] PASS: FR3
[TEST] PASS: FR4
[TEST] PASS: SR1
[TEST] PASS: SR2
[TEST] PASS: SR3
[TEST] PASS: SR4
```

or, for any requirement that fails:

```
[TEST] FAIL: <requirement_id>: <brief reason>
```

The process exits with status `0` only if all eight requirements pass, and
with a non-zero status otherwise.

## Requirement summary

- **FR1** — Your submission must be valid JSON matching the schema above:
  correct types, required fields present and non-empty where required, and
  confidence values within range.
- **FR2** — At least one candidate must reference a real output port that
  actually exists on `uart_tx`.
- **FR3** — There must be a clear, unique top-ranked candidate with
  confidence `>= 0.5`.
- **FR4** — Your summary must acknowledge the core's documented functional
  behavior (framing/handshake timing) and speak to whether it remains
  intact, showing that your analysis distinguishes benign design choices
  from genuinely anomalous logic.
- **SR1–SR4** — These check the *substance* of your top-ranked finding
  against this design's actual ground truth: whether you correctly named
  the specific internal register being leaked, the specific output net it
  leaks through, the specific rare trigger condition that activates the
  leak, and whether your report engages meaningfully with the real
  mechanism rather than being empty, generic, or focused only on unrelated
  signals. No further detail about the exact keyword matching used
  internally is provided here — a careful reading of `inputs/uart_tx.v`,
  `inputs/uart_tx_tb.v`, and `inputs/design_brief.md` is sufficient to
  determine what an accurate, substantive report should contain.

## Notes

- Only `submission/trojan_report.json` is graded. Any other files you
  create are ignored by `evaluate.py`.
- You may use `iverilog`/`vvp`/`yosys` locally to help you form your
  analysis (e.g. to confirm how `status_dbg` behaves under different input
  patterns), but grading itself is based solely on the content of your
  submitted JSON report.
- A submission with an empty `candidates` array, all-zero confidences, or
  generic/boilerplate rationale that never engages with the design's
  actual internal signals will fail the substantive checks even if it is
  well-formed JSON.