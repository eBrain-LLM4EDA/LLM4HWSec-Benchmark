# SEU Hardening Candidate Identification — Evaluation

This directory contains the automated grader for the
`seu_tmr_candidate_identification_v1` task.

## What gets graded

The grader does **not** evaluate any code you write. Your deliverable is a
single analysis report:

```
submission/vulnerability_report.json
```

`evaluation/evaluate.py` reads the reference input artifacts under `inputs/`
(`controller_datapath.v`, `fault_model.md`, `register_map.json`) purely for
context/cross-reference, and grades the content of your submitted report
against a hidden set of correctness criteria derived from those artifacts.
You must not modify anything under `inputs/`.

## How to run

From the repository root, with `inputs/` and `submission/` present:

```
python evaluation/evaluate.py
```

The script prints one line per checked requirement:

```
[TEST] PASS: <REQUIREMENT_ID>
[TEST] FAIL: <REQUIREMENT_ID>: <reason>
```

It exits with code `0` only if every requirement passes, and non-zero
otherwise. If `submission/vulnerability_report.json` is missing entirely, or
one of the expected `inputs/` files is missing, the script reports a
`SETUP` failure and exits non-zero.

## Structural / format checks (FR1–FR4)

These checks verify that your report is well-formed and complete. They are
purely mechanical — they do not evaluate whether your engineering judgment
is correct, only whether the report is shaped correctly and internally
consistent:

- **FR4 — Valid JSON envelope.** The submission file must parse as valid
  JSON. Its top-level object must contain *exactly* the three keys
  `schema_version`, `summary`, and `registers` (no additional or missing
  top-level keys), and `schema_version` must equal the string `"1.0"`.

- **FR1 — Complete, accurate register inventory.** The set of
  `signal_name` values appearing in your `registers` array must exactly
  match the set of register names declared in `inputs/register_map.json` —
  no omissions, and no fabricated names that don't appear there.

- **FR2 — Well-typed per-register entries.** Every entry in `registers`
  must include:
  - `signal_name` (a non-empty string),
  - `bit_width` (a positive integer — this is a type/format check only;
    your own bit-width value for a given register is accepted as long as
    it is a positive integer, since your independent read of the RTL is
    the source of truth for the numeric value),
  - `category` (exactly one of the strings `"control_state"` or
    `"data_pipeline"`),
  - `tmr_recommended` (boolean),
  - `justification` (a non-empty string).

- **FR3 — Consistent summary counts.** The top-level `summary` object must
  contain integer fields `total_registers`, `control_state_count`,
  `data_pipeline_count`, and `tmr_recommended_count`, and each of these
  must equal the value obtained by actually counting the corresponding
  entries in your `registers` array (e.g. `tmr_recommended_count` must
  equal the number of entries with `tmr_recommended == true`).

A report that fails FR4 (unparseable JSON or wrong envelope shape) will
also be reported as failing FR1–FR3, since those checks depend on being
able to interpret the register list and summary.

## Substantive correctness checks (SR1–SR3)

These checks grade whether your analysis is actually *correct* — not just
well-formatted — against a hidden ground-truth classification and fault
rationale derived from the RTL and the fault model document. In general
terms, without revealing the specific answer:

- **SR1 — Correct identification of the highest-priority hardening
  candidates.** A subset of the registers declared in
  `controller_datapath.v` play a control/state role in the design (i.e.
  their corruption can silently redirect control flow, corrupt an
  addressing/pointer value, or otherwise persist undetected with no
  self-correcting mechanism). Your report must correctly classify *all*
  of these as `category == "control_state"` and must recommend TMR
  hardening (`tmr_recommended == true`) for every one of them. Missing
  any one of them, misclassifying it, or declining to recommend TMR for
  it will fail this check.

- **SR2 — Avoiding over-hardening of the data path.** A separate subset
  of registers form a bounded, transient data-processing pipeline whose
  single-bit errors are generally overwritten each cycle or are otherwise
  low-priority for TMR under a fixed hardening budget. Your report must
  not recommend TMR for more than a small minority of these — over-
  hardening the data path at the expense of prioritizing control logic is
  penalized.

- **SR3 — Substantive, non-boilerplate justifications.** For the
  registers identified as control/state candidates, the majority of your
  written justifications must actually reflect the relevant fault-model
  rationale (e.g. referencing the silent, unrecoverable, or
  undetected/uncorrected nature of a state, address, or control-flow
  corruption) rather than generic or templated text that could apply to
  any register regardless of its actual role in the design.

The exact list of which signals fall into which category, and the exact
keyword/rationale matching used for SR3, are intentionally not enumerated
here — you are expected to derive them yourself from
`inputs/controller_datapath.v` and `inputs/fault_model.md`, exactly as a
hardening engineer would when reviewing an unfamiliar design under a
generic SEU fault model.

## Notes on toolchain availability

`iverilog`, `vvp`, and `yosys` are available in the evaluation environment
and may be used by the grader for optional cross-checks against the RTL in
`inputs/`. The pass/fail verdict for every requirement, however, is always
based on the content of your submitted `vulnerability_report.json`.