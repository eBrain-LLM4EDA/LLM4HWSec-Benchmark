# RTL Hardware Trojan Detection — Bus Arbiter Task

## Overview

This task asks you to review the finite-state machine implemented in
`inputs/bus_arbiter.v`, a 4-master round-robin bus arbiter, and produce a
structured analysis report identifying any state(s) or transitions that
could cause the arbiter to stop granting bus access to legitimate masters
(a permanent denial-of-service condition), along with the exact request
sequence required to reach such a state.

You must **not** modify `inputs/bus_arbiter.v` or `inputs/design_brief.md`.
Both files are read-only reference artifacts describing the design under
review. Your analysis, and your analysis alone, is what gets graded.

## What you must submit

A single file at:

```
submission/trojan_report.json
```

This is the only artifact evaluated. Nothing else you produce is read by
the grader.

## Running the evaluator

From the repository root:

```
python3 evaluation/evaluate.py
```

The script:

1. Confirms `inputs/bus_arbiter.v` is present (it is used only as the
   read-only reference design; its content is fixed and must not be
   changed by you).
2. Loads and validates `submission/trojan_report.json`.
3. Prints one line per requirement in the form
   `[TEST] PASS: <ID>` or `[TEST] FAIL: <ID>: <reason>`.
4. Exits `0` only if every requirement passes; otherwise exits non-zero.

If `submission/trojan_report.json` is missing, the script fails immediately
with `[TEST] FAIL: SETUP: submission/trojan_report.json not found`.

## Required JSON schema

`submission/trojan_report.json` must be a single JSON object with exactly
these top-level keys:

```json
{
  "candidates": [
    {
      "state_name": "string",
      "trigger_condition": "string",
      "confidence": 0.0,
      "rationale": "string",
      "impact": "string"
    }
  ],
  "overall_assessment": "string",
  "recommended_fix": "string"
}
```

Field requirements:

- **`candidates`** — a non-empty array. Each entry must be a JSON object
  with all five fields below present and non-empty (as applicable):
  - `state_name` (string) — the name/label you use for the state you are
    flagging.
  - `trigger_condition` (string) — the concrete signal condition(s) and/or
    originating state that lead into this state.
  - `confidence` (number) — a float in the closed interval `[0.0, 1.0]`.
    Values outside this range, booleans, or non-numeric values are
    rejected.
  - `rationale` (string) — your reasoning, grounded in the actual RTL.
  - `impact` (string) — the operational consequence of reaching this
    state (e.g. what happens to `gnt`/`busy` afterward).
- **`overall_assessment`** (string) — a substantive statement (not a
  one-word stub) that explicitly answers, with a clear yes/no, whether the
  arbiter can enter a state from which it never asserts any `gnt` bit
  again (a permanent denial-of-service condition). Hedged or ambiguous
  answers that do not commit to yes or no will not be accepted as
  satisfying this field.
- **`recommended_fix`** (string) — a description of how the design should
  be corrected or hardened.

## Grounding requirement

At least one candidate's combined text (across `state_name`,
`trigger_condition`, `rationale`, `impact`) must reference:

- a concrete state name that literally appears in `inputs/bus_arbiter.v`
  (e.g. one of the FSM's `localparam` state labels), **and**
- a concrete signal name that literally appears in `inputs/bus_arbiter.v`
  (e.g. `req`, `gnt`, `busy`, `rst_n`), **and**
- a concrete bit-pattern or selector token (such as a `4'b...` literal, a
  `0x...`/`0b...` literal, a bit-index like `[2]`, or an explicit `==`
  comparison) rather than vague, generic language.

Generic boilerplate ("there may be an unreachable state" with no specific
state name, signal, or bit pattern) will not satisfy this requirement.

## What "correct" looks like

A correct submission does real analysis of the FSM described in
`inputs/bus_arbiter.v` and `inputs/design_brief.md`:

- It identifies which state(s), if any, act as an unintended absorbing
  condition — i.e. a state from which no legitimate `req` pattern ever
  leads back to granting service to any master, short of a full
  asynchronous reset.
- It reports the precise originating state and the precise `req` bit
  pattern (in binary, hex, or Verilog-literal form) that triggers entry
  into that state, not a vague description like "an unusual request
  sequence."
- It gives a confident, substantiated verdict on whether a permanent
  denial-of-service condition exists in the design, and assigns a
  `confidence` value commensurate with how certain and precise the
  finding is.

An empty `candidates` array, or a report consisting only of generic
placeholder text that does not reference actual states/signals/bit
patterns from `inputs/bus_arbiter.v`, will fail evaluation. Confidence
scores that are too low, or trigger descriptions that are too vague to
pin down a specific bit pattern and originating state, will also fail to
receive credit for the substantive findings, even if the JSON is
otherwise well-formed.

## Notes

- Confidence values must always be expressed as numbers in `[0.0, 1.0]`,
  not strings or percentages.
- You are encouraged (but not required) to justify your findings in a way
  that could be independently verified by simulating
  `inputs/bus_arbiter.v` with `iverilog`/`vvp` from reset using your
  reported trigger sequence.
- Do not rely on the design brief's summary table alone — it describes the
  *intended* behavior; your review should be grounded in what the RTL
  `case` statements actually implement.