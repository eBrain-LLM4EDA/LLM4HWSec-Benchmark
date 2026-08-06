# RTL Trojan Detection: Key Loader Controller Analysis

## Task Overview

This is a **report grading** task. You are given the RTL source for a
key-loading controller module (`key_loader_ctrl`) and a design brief
describing its intended behavior. Your job is **not** to modify or
resubmit the RTL — it is to analyze it and produce a structured findings
report.

- Input artifacts (read-only, provided under `inputs/`):
  - `inputs/key_loader_ctrl.v` — the RTL under analysis.
  - `inputs/design_brief.md` — the documented functional/security intent
    of the module (key loading over the bus, and unconditional zeroize).
- Submission artifact (what you produce):
  - `submission/trojan_report.json` — your analysis report, per the
    schema below.

`evaluate.py` reads `inputs/key_loader_ctrl.v` only for reference/optional
cross-checks; the actual PASS/FAIL verdicts grade the content of
`submission/trojan_report.json` against the hidden ground truth.

## Submission Schema

`submission/trojan_report.json` must be valid UTF-8 JSON (no comments, no
trailing commas) with the following top-level shape:

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

- `candidates` must be a non-empty array.
- Each candidate must include all four fields above, with `confidence` a
  number in `[0.0, 1.0]`.
- `summary` is a free-text overview of your findings.
- `tool_version_or_method` describes how you performed the analysis
  (e.g. manual review, simulation with iverilog/vvp, a formal tool, etc.).

## How the Report Is Graded

`evaluate.py` checks the following requirement ids, each producing exactly
one `[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>` line. The process
exits `0` only if every requirement passes.

### Functional Requirements (structure/format)

- **FR1** — The submission file must exist and be valid JSON with the
  required top-level fields (`candidates` non-empty array, `summary`
  string, `tool_version_or_method` string).
- **FR2** — Every entry in `candidates` must contain `signal_or_net`,
  `location_hint`, `trigger_condition` (all strings), and `confidence`
  (a number in `[0.0, 1.0]`).
- **FR3** — At least one candidate's `trigger_condition` must describe the
  simultaneous assertion of `zeroize` together with `bus_busy` (or an
  equivalent bus-transaction-in-progress condition) as the trigger for the
  anomaly, rather than mentioning only one of the two signals.
- **FR4** — The report's *highest-confidence* candidate must state, in
  text scoped specifically to that candidate (its own `signal_or_net`,
  `location_hint`, and `trigger_condition` fields, plus any sentence of
  `summary` that clearly discusses that same candidate), that the
  expected/correct value of `key_q` under the identified trigger is
  all-zero (`32'b0`). If that scoped text instead names a different
  explicit constant as the expected outcome (e.g. an all-ones or other
  nonzero literal), or omits an expected-value claim entirely, this
  requirement fails — even if the word "zero" happens to appear
  elsewhere in the document in connection with a *different* candidate.
  In other words, the expected-value claim must be genuinely attached to
  the top-confidence finding, not merely present somewhere in the report.

### Security Requirements (substantive correctness)

- **SR1** — The report must correctly identify that the vulnerability
  requires the specific *coincidence* of `zeroize=1` **and** `bus_busy=1`
  — not `zeroize` alone, not `bus_busy` alone, and not a generic or
  unrelated condition (e.g. reset, power-on).
- **SR2** — Using text scoped specifically to the report's
  highest-confidence candidate (the same per-candidate scoping described
  for FR4), the report must correctly identify the root cause as
  combinational masking/gating of the zeroize signal by a
  `bus_busy`-derived term feeding the next-state selection logic for
  `key_q`, and must describe the faulty branch as causing `key_q` to
  retain/hold its own current value (rather than being loaded from some
  other source such as `bus_data`). If the top candidate's own scoped
  root-cause narrative instead attributes the defect to an unrelated
  mechanism (e.g. a reset synchronizer, clock-domain-crossing,
  metastability, or power-on issue), this requirement fails — even if
  masking/gating vocabulary happens to appear elsewhere in the report in
  connection with a *different* (non-top) candidate. The root-cause claim
  must genuinely belong to the top-confidence finding.
- **SR3** — The single highest-confidence candidate (by the numeric
  `confidence` field) must be the zeroize/bus_busy root-cause finding
  described above (i.e. it must satisfy both SR1's trigger-conjunction
  criterion and SR2's scoped root-cause criterion), with
  `confidence >= 0.6`. A decoy or unrelated top-ranked finding fails this
  requirement.
- **SR4** — The report must provide actionable localization: the
  `location_hint` of a qualifying candidate must identify the specific
  construct/label or a line range closely matching the actual offending
  logic in `inputs/key_loader_ctrl.v`, not merely assert that a trojan
  exists without pointing at where it lives.

A report only receives an overall PASS if **all** of FR1–FR4 and SR1–SR4
hold. An empty or naive "no anomalies detected" report, or a report that
only performs generic keyword-matching without correctly conjoining
`zeroize` and `bus_busy`, or whose top-confidence claim does not itself
carry the correct expected-value/root-cause content, will fail.

## Running the Grader

```
python3 evaluation/evaluate.py
```

This prints one `[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>` line
per requirement and exits `0` if all requirements pass, or non-zero
otherwise.