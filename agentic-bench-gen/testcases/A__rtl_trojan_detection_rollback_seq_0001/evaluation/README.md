# Evaluation: RTL Hardware Trojan Detection — `version_ctrl`

## Overview

This task asks you to analyze the RTL design in `inputs/version_ctrl.v`
(with supporting context in `inputs/design_brief.md`) and produce a
structured analysis report identifying any conditions under which the
firmware version register, `version_q`, could be updated to a value other
than the maximum of its current value and the presented candidate version.

You do **not** modify any files under `inputs/`. Your deliverable is a
single JSON report file at:

```
submission/trojan_report.json
```

## Running the grader

From the root of the task directory:

```
python3 evaluation/evaluate.py
```

The grader:

1. Reads `inputs/version_ctrl.v` for reference (it must exist; this is the
   module under analysis). It also parses this file to determine which
   identifiers are genuinely declared internal registers of the design, as
   opposed to the module's documented public interface ports.
2. Reads and parses `submission/trojan_report.json`.
3. Checks the report's structure against the functional requirements
   (FR1-FR4).
4. Checks the report's substantive findings against the security
   requirements (SR1-SR4).
5. Prints one result line per requirement and exits with a status code
   reflecting the overall verdict.

This is a **report-grading** task: the thing being graded is the content of
your submitted JSON report, not code that gets compiled or synthesized.
`iverilog`, `vvp`, and `yosys` are available in the environment and may be
used *by you* (or by an extended grader) as optional cross-checks to
confirm claims made in your report by simulating or analyzing
`inputs/version_ctrl.v` directly — but they are **not required** for
grading, and `evaluate.py` does not invoke them to compute the pass/fail
verdicts described below.

## Requirement summary

### Functional requirements (structure/format of the report)

- **FR1** — `submission/trojan_report.json` must be valid JSON with
  top-level fields `candidates` (array), `summary` (string), and
  `tool_version` (string).
- **FR2** — Every element of `candidates` must include the fields `id`
  (string), `description` (string), `confidence` (number in `[0,1]`),
  `trigger_condition` (string), and `payload_effect` (string).
- **FR3** — At least one candidate must reference an actual internal
  register/state variable that is genuinely declared in `version_ctrl.v`
  and is responsible for tracking the sequence of accepted requests. This
  must be a real signal name that appears in the design's source, and it
  must be distinct from the module's documented public interface ports
  (`clk`, `rst_n`, `req_valid`, `candidate_version`, `req_accept`,
  `version_q`, `update_ack`). Simply using a phrase that contains the word
  "internal" or "state" (e.g. "some internal logic", "hidden internal
  state") without naming a real declared signal does **not** satisfy this
  requirement — the grader checks the referenced identifier against the
  registers actually declared in `inputs/version_ctrl.v`.
- **FR4** — The highest-confidence candidate must state the exact update
  expression asserted in the terminal/triggering condition (i.e. what
  value `version_q` is assigned instead of the expected
  `max(version_q, candidate_version)`).

### Security requirements (substantive correctness of the findings)

- **SR1** — The report must identify that `version_q`'s update logic is
  *not* purely a function of `(version_q, candidate_version, req_valid,
  req_accept)` on the current cycle, but depends on hidden sequential
  state accumulated across multiple prior accepted requests. As with FR3,
  this requires naming a real internal register declared in the design
  (not a generic placeholder phrase), together with language that
  explicitly contrasts that dependency with pure combinational logic over
  the four public interface signals.
- **SR2** — The report must correctly identify the three specific
  low-nibble trigger values and their required order as the activation
  condition.
- **SR3** — The report must correctly identify that the payload effect is
  a decrement of the version register on the triggering cycle, rather
  than a no-op, a jump to a fixed value, or a generic "incorrect update"
  description.
- **SR4** — The confidence assigned to the correct (true-positive)
  candidate must be the maximum (or tied-maximum) among all submitted
  candidates and must meet or exceed the 0.5 confidence threshold; the
  report must not bury the correct finding under a large number of
  unsubstantiated, equally-or-more-confident spurious candidates.

All of these are graded against the actual *content* of your report using
style-invariant text/structure matching — the exact wording, field
ordering, candidate IDs, and JSON formatting style are up to you, as long
as the required information is substantively present. In particular, for
FR3 and SR1 you are free to name the relevant internal signal(s) however
you like in prose (e.g. quoting it, capitalizing it, embedding it in a
sentence) as long as the actual identifier text appears somewhere in the
candidate's `description`, `trigger_condition`, or `payload_effect` and
that identifier corresponds to a signal genuinely declared in
`version_ctrl.v` rather than one of its documented ports.

## Marker line format

For every requirement checked, `evaluate.py` prints exactly one line in
one of these two forms:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <brief reason>
```

Requirement IDs are exactly: `FR1`, `FR2`, `FR3`, `FR4`, `SR1`, `SR2`,
`SR3`, `SR4`.

If the submission file is missing entirely, or a required input artifact
is missing, you will instead see a setup failure of the form:

```
[TEST] FAIL: SETUP: <path> not found
```

Setup failures short-circuit the run: no further requirement checks are
attempted, and the process exits non-zero.

## Exit code semantics

- **Exit code 0** — every requirement printed `[TEST] PASS`.
- **Exit code non-zero** — at least one requirement printed `[TEST] FAIL`
  (including any `SETUP` failure).

## Notes

- An empty or boilerplate submission (empty `candidates` list, or a single
  vague candidate that never names a real internal register declared in
  `version_ctrl.v`, the specific nibble trigger values, or the decrement
  payload) is expected to fail FR3/FR4 and/or SR1-SR4.
- A report that only generically flags "possible non-monotonic update" or
  "rarely-taken FSM state" — without naming an actual declared internal
  signal, the specific nibble trigger sequence, and the decrement payload
  — will fail the functional and security requirements even if it is
  well-formed JSON satisfying FR1/FR2.