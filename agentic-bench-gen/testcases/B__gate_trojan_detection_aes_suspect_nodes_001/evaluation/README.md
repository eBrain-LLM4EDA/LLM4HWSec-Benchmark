# Gate-Level Trojan Detection — Evaluation Guide

## Overview

This task asks you to analyze `inputs/aes_sub_netlist.v` (a gate-level
Verilog netlist), together with `inputs/design_brief.md` and
`inputs/port_map.json`, and to determine whether the netlist has been
tampered with (a hardware Trojan inserted) relative to its documented
intent. Your findings must be written to a single JSON file at:

```
submission/trojan_report.json
```

You must not modify any file under `inputs/`. All of your analysis output
goes into `submission/trojan_report.json`.

## Required JSON schema

`submission/trojan_report.json` must be a single JSON object (not wrapped
in an array) with at least the following top-level keys:

| Key | Type | Description |
|---|---|---|
| `infected` | boolean | `true` if you conclude the netlist contains a Trojan, `false` otherwise. |
| `suspect_nodes` | array of strings | Gate instance names you believe are part of the Trojan (trigger and/or payload logic). Each entry **must exactly match, or be a substring of, an actual instance name declared in `inputs/aes_sub_netlist.v`** (e.g. `and t_and0 (...)` declares instance `t_and0`). If `infected` is `false`, this array must be empty. If `infected` is `true`, it must contain at least 2 entries. |
| `rationale` | string | A non-empty explanation of why you believe the netlist is (or is not) infected, referencing the specific gate instances and mechanism involved. Generic/boilerplate text will not be considered a substantive rationale. |
| `primary_output_affected` | string | The name of the primary output port (as declared in `inputs/port_map.json`) that the suspected payload logic drives. Must be the empty string `""` if `infected` is `false`. |

Additional keys are permitted in the JSON object and will be ignored by the
grader.

### Example shape (illustrative only — not a hint about the correct answer)

```json
{
  "infected": true,
  "suspect_nodes": ["some_instance_name", "another_instance_name"],
  "rationale": "Explain the mechanism here, referencing the specific gate instances and why they are suspicious relative to the design brief.",
  "primary_output_affected": "sbox_out"
}
```

## How grading works

Run the grader from the root of your working directory (the directory
containing `inputs/`, `submission/`, and `evaluation/`):

```
python3 evaluation/evaluate.py
```

`evaluate.py`:

- Reads `inputs/aes_sub_netlist.v` to determine the set of real gate
  instance names actually declared in the netlist (via structural parsing
  of primitive gate instantiations — `and`, `or`, `xor`, `not`, `nand`,
  `nor`). This is used to validate that every name you list in
  `suspect_nodes` refers to a real instance, not a fabricated one.
- Reads `inputs/port_map.json` to determine the set of valid output port
  names for validating `primary_output_affected`.
- Reads your submitted `submission/trojan_report.json` and checks it
  against a fixed set of functional and security requirements.
- Grades **only the content of your submitted JSON file**. It does not
  inspect how you produced your analysis, what tools you used, or any
  scratch notes you may keep elsewhere. There is no advantage or
  disadvantage tied to writing style, formatting, or key ordering in your
  JSON.

If `submission/trojan_report.json` is missing, the grader immediately
reports a setup failure and exits non-zero:

```
[TEST] FAIL: SETUP: submission/trojan_report.json not found
```

For every requirement it checks (functional requirements `FR1`–`FR4` and
security requirements `SR1`–`SR5`), the grader prints exactly one line of
the form:

```
[TEST] PASS: <requirement_id>
```

or

```
[TEST] FAIL: <requirement_id>: <brief reason>
```

The grader exits with status code `0` only if every requirement passes,
and non-zero if any requirement fails. A passing run means every printed
line is a `[TEST] PASS` line.

## What is checked (high level)

- **FR1** — Your submission is valid JSON containing `infected` (bool),
  `suspect_nodes` (array of strings), and a non-empty `rationale` (string).
- **FR2** — Every string in `suspect_nodes` corresponds to a real gate
  instance actually present in `inputs/aes_sub_netlist.v`.
- **FR3** — Consistency between `infected` and the size of `suspect_nodes`
  (empty when not infected; at least 2 entries when infected).
- **FR4** — `primary_output_affected` is a valid output port name from
  `inputs/port_map.json` when infected, or `""` when not infected.
- **SR1** — Whether your infection verdict matches the ground truth.
- **SR2** — Whether your `suspect_nodes` substantively cover the true
  trigger and payload logic instances involved in the Trojan.
- **SR3** — Whether you correctly identify which primary output is
  actually corrupted.
- **SR4** — Whether your rationale demonstrates real understanding of the
  underlying mechanism (rather than generic, boilerplate wording).
- **SR5** — Checks whether your submission represents a genuine,
  non-trivial attempt rather than a "did nothing" answer. Concretely, SR5
  fails only if your submission is functionally equivalent to the naive
  empty baseline (`infected == false`, `suspect_nodes == []`,
  `primary_output_affected == ""`) **and** that same submission does not
  independently satisfy SR1–SR4. Any submission that reports an infection
  with named suspect nodes and an affected output — i.e. any substantive
  attempt at the analysis — passes SR5, regardless of whether it is fully
  correct on SR1–SR4 (that correctness is judged separately by those
  requirements). SR5 exists solely to guarantee that a naive/empty answer
  cannot pass the overall rubric by accident.

The exact gold node list, keyword thresholds, and coverage cutoffs used
internally are intentionally not published here beyond what is described
in the task's public specification — this file describes the schema and
mechanics of grading, not the hidden answer key.

## Optional cross-checking

You are welcome to use `yosys`, `iverilog`, and `vvp` (available in the
evaluation environment) to synthesize or simulate
`inputs/aes_sub_netlist.v` yourself, to help build confidence in your
analysis (for example, exercising the netlist across many input
combinations to look for rare deviations from the documented behavior in
`inputs/design_brief.md`). This is entirely optional: it is not required
to produce a valid report, and `evaluate.py`'s pass/fail verdicts are based
solely on the content of your submitted `submission/trojan_report.json`,
never on whether or how you ran any external tool.