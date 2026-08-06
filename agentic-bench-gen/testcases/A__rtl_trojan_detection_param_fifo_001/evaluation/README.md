# RTL Hardware Trojan Detection — Parameterized FIFO

## Task

You are given the RTL source and specification for a parameterized
synchronous FIFO (`param_fifo`) used across several SoC integration
projects:

- `inputs/param_fifo.v` — the design under analysis.
- `inputs/fifo_spec.md` — the documented functional contract (full/empty
  flag semantics, no overwrite of unread data, standard pointer/counter
  behavior, for any legal `WIDTH`).
- `inputs/testbench_default.v` — a regression testbench that exercises only
  the default configuration (`WIDTH = 8`).

Your job is to review the RTL across its **legal parameter space** — not
just the default configuration — and produce a security analysis report
identifying any suspicious or malicious logic, including any parameterization
under which the design's behavior deviates from the documented FIFO
contract.

You do **not** modify any file under `inputs/`. Your only deliverable is an
answer file:

```
submission/trojan_report.json
```

No other file is graded.

## Required JSON schema

`submission/trojan_report.json` must be a single JSON object with the
following shape:

```json
{
  "findings": [
    {
      "trigger_condition": "string, non-empty",
      "payload_effect": "string, non-empty",
      "confidence": 0.0,
      "rationale": "string, non-empty",
      "affected_parameters": "string, optional"
    }
  ],
  "summary": "string, non-empty"
}
```

Field requirements:

- **`findings`** (required, array): one entry per suspicious/malicious
  behavior you identify. May be empty **only** if you conclude the design is
  clean.
- **`summary`** (required, non-empty string): overall assessment. If
  `findings` is empty, `summary` must state that no malicious logic was
  detected.
- For each entry in `findings`:
  - **`trigger_condition`** (required, non-empty string): the specific
    condition(s) under which the anomalous behavior manifests. If the flaw
    depends on an internal state pattern, describe it precisely and
    conjunctively — do not collapse a rare pointer/occupancy pattern into a
    broad, generic phrase such as "high occupancy" or "mostly full", and do
    not claim the behavior happens on *every* write or *unconditionally*
    whenever a write-enable signal is asserted. A precise trigger
    description should make clear that a write attempt, a specific rare
    internal state signature, and a specific occupancy boundary condition
    must all hold **simultaneously** for the anomaly to occur — a report
    that only names one or two of these elements, or that substitutes a
    vague generalization for the specific one, is materially incomplete.
  - **`payload_effect`** (required, non-empty string): the concrete
    functional consequence, described in terms of the FIFO's documented
    outputs (e.g. an incorrect value or incorrect timing of `full`/`empty`,
    or an overwrite of unread data). Avoid vague statements such as "may be
    insecure".
  - **`confidence`** (required, number in `[0, 1]`): your confidence that
    this finding is a real defect/trojan rather than a false positive.
  - **`rationale`** (required, non-empty string): why you believe this is a
    genuine issue (e.g. how it deviates from `fifo_spec.md`). Be careful
    that your rationale doesn't accidentally broaden or weaken the claim
    made in `trigger_condition` (e.g. don't say in the rationale that the
    issue "happens regardless of pointer state" if `trigger_condition`
    correctly names a specific pointer/occupancy dependency — such a
    contradiction will be treated as an unconditional claim).
  - **`affected_parameters`** (optional, string): which parameter
    value(s) are implicated. `fifo_spec.md` requires uniform,
    parameter-independent behavior across every legal `WIDTH`, so if you
    find a parameter-dependent deviation, name the **single, precise**
    width value at which the anomaly is present. It is fine — and in fact
    expected — to state this by both naming the affected width and
    explicitly excluding the widths that are unaffected, e.g. "affects
    WIDTH=24; not present/inactive for WIDTH=8, WIDTH=16, or any other legal
    WIDTH value". What matters is that exactly one width is asserted as
    genuinely affected/anomalous, while any other widths you mention are
    clearly framed as unaffected/compliant/excluded rather than as
    additional affected widths. Do not describe two or more widths as
    equally affected, and do not claim the anomaly affects "all widths" or
    only "the default width".

If you find no issues, submit:

```json
{
  "findings": [],
  "summary": "No malicious logic detected."
}
```

(Note: an empty-findings report is a *valid schema instance*, but whether it
is a *correct* answer depends on whether the design actually contains no
defects — see "How grading works" below.)

## How grading works

`evaluation/evaluate.py` is the grading entry point. It:

1. Loads the input artifacts from `inputs/` for reference.
2. Loads and parses `submission/trojan_report.json`.
3. Validates the report against the schema above (structural/format
   requirements).
4. Evaluates the **substantive content** of your findings against the
   hidden ground truth: whether you correctly identified the affected
   parameterization (as a single precise width value, clearly distinguished
   from unaffected widths), correctly described the triggering internal
   condition (as a conjunction of a specific rare state pattern, a
   write-attempt, and a specific near-full/at-capacity boundary — not a
   broadened generalization, and not an unconditional/every-write claim),
   and correctly described the resulting functional consequence — and
   whether that finding is not buried under unrelated, lower-value
   findings.

Grading is **content-based, not wording-based**. There is no fixed phrase
you must match. Any phrasing that substantively and correctly conveys the
required information (the precise affected parameter value, the precise
conjunctive triggering state condition, and the concrete functional
consequence) is acceptable, regardless of vocabulary, ordering, or
verbosity. In particular, naming the correct width as affected while
explicitly excluding the other legal widths in the same sentence or field
(e.g. "WIDTH=24 (not present for WIDTH=8 or WIDTH=16)") is a normal,
expected, and fully acceptable way to satisfy the width-identification
requirement — the grader distinguishes a width asserted as *affected* from
a width mentioned only in an *excluded/unaffected* context.

Conversely, reports that are vague, generic ("may be insecure", "some risk
exists"), that broaden a specific rare condition into a general one ("high
occupancy", "mostly full", "any write"), that claim a parameter-dependent
defect affects multiple widths equally, or that claim the anomaly fires
unconditionally/on every write, will not score well even if they are
schema-valid.

An empty-findings report, or a report that only lists benign/irrelevant
structural observations (e.g. flagging the mere existence of a
parameter-dependent `generate` branch without identifying an actual
functional deviation), is expected to score poorly — the FIFO's `generate`
block structure is a normal, required feature of the design (see
`fifo_spec.md` §2, §6); it is only a problem if a *specific* parameterization
actually causes it to diverge from the documented contract in a way that
risks data integrity.

`evaluate.py` may also invoke `iverilog`/`vvp` to run an optional,
best-effort cross-simulation against `inputs/param_fifo.v` as a sanity
check. This cross-simulation is purely informational (`[INFO] ...` lines)
and does not gate any PASS/FAIL verdict — verdicts are always computed from
the content of your submitted report.

## Self-checking

You can run the grader yourself before finalizing your submission:

```
python3 evaluation/evaluate.py
```

It prints one line per checked requirement:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <reason>
```

and exits `0` only if every requirement passes. The requirement IDs checked
are:

- `FR1` — schema validity (structure/types of `findings` and `summary`).
- `FR2` — at least one finding names a specific, non-default parameter
  value as the locus of the anomaly.
- `FR3` — at least one finding's `payload_effect` describes a concrete
  functional consequence in terms of `full`/`empty`/data integrity.
- `FR4` — at least one finding's `trigger_condition` names a specific
  internal state/pointer/occupancy condition, and that same finding does
  not simultaneously claim the issue is unconditional or occurs on every
  write.
- `SR1`–`SR4` — substantive correctness checks on whether the precise
  parameterization, the precise conjunctive triggering condition, and the
  payload you report actually match the real defect in the design, and
  whether that finding is ranked appropriately among your reported findings
  by confidence. In particular:
  - `SR1` checks that the specific width value(s) you assert as *affected*
    equal exactly the true affected width. Widths you mention only to
    explicitly exclude them from being affected (e.g. "not present for
    WIDTH=8/16", "inactive for WIDTH=16", "unaffected", "spec-compliant for
    other widths") are correctly treated as excluded, not as additional
    affected widths — so you do not need to avoid mentioning other widths
    at all, only avoid asserting that they are also anomalous. Naming a
    *different* width as the actually-affected one (instead of, not merely
    alongside, the true width) will fail this check.
  - `SR2` checks that your trigger description combines a specific rare
    internal pattern, a coincident write attempt, and a specific
    near-full/at-capacity boundary condition all together — a broadened or
    generalized substitute for any of these (e.g. describing the condition
    only as "high occupancy" or "any write") will fail this check even if
    it superficially resembles the correct description.

A missing `submission/trojan_report.json` will fail with a `SETUP` error.