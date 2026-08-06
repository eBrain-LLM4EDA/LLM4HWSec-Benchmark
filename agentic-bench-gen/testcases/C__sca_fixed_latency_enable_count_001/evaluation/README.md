# Evaluation Harness: Fixed-Latency Multiplier Controller Activity Analysis

This directory contains the grading harness for task
`sca_fixed_latency_enable_count_001`.

## What this grades

`evaluate.py` grades the participant's answer file at
`submission/vulnerability_report.json` against the functional and security
requirements described in the task specification (FR1-FR4, SR1-SR3).

It does **not** grade or execute any file under `inputs/`. The files under
`inputs/` (`mult_ctrl.v`, `fault_model.md`, `trace_manifest.json`,
`traces.csv`, `design_brief.md`) are read-only reference material:

- `inputs/traces.csv` is a plain CSV file whose first line is the literal
  header `trial_id,secret_operand,cycle_index,mul_en,done`, with no
  surrounding prose or markdown fencing. It is loaded and parsed to
  reconstruct, per distinct `secret_operand` value, the ground-truth
  `enable_count` (number of cycles with `mul_en == 1` during the active
  8-cycle window of a transaction) and the cycle on which `done` is
  asserted. This ground truth is what the submitted report's
  `activity_analysis` and `timing_analysis` fields are checked against.
- `inputs/mult_ctrl.v` may optionally be used for an independent
  cross-check via `iverilog`/`vvp` simulation (see
  `evaluation/tb_mult_ctrl_check.v`), but this is not required for grading
  and does not change any PASS/FAIL verdict -- the graded artifact is
  always the submitted report, cross-checked against `traces.csv` ground
  truth.

**Participants must not edit any file under `inputs/`.** Only
`submission/vulnerability_report.json` is graded.

## How to run

From the repository root:

```
python3 evaluation/evaluate.py
```

The script expects:

- `inputs/traces.csv` to exist and be a well-formed, directly parseable CSV
  (per-cycle records of `trial_id,secret_operand,cycle_index,mul_en,done`,
  with that header row as the literal first line -- no narrative text or
  code-fence markers).
- `submission/vulnerability_report.json` to exist and contain a JSON object
  with the fields described in the task's functional requirements
  (`summary`, `timing_analysis`, `activity_analysis`,
  `hardening_recommendations`).

If either required file is missing, or `traces.csv` cannot be parsed as
plain CSV, or the submission is not valid JSON, the script reports a
setup/parse failure for every requirement and exits non-zero.

## Output format

For every requirement checked, the script prints exactly one line of the
form:

```
[TEST] PASS: <requirement_id>
```

or

```
[TEST] FAIL: <requirement_id>: <brief reason>
```

where `<requirement_id>` is one of `FR1`, `FR2`, `FR3`, `FR4`, `SR1`, `SR2`,
`SR3`, matching the identifiers used in the task specification.

## Exit codes

- **Exit code 0**: every requirement passed (every emitted line is a
  `[TEST] PASS` line).
- **Exit code non-zero (1)**: at least one requirement failed, including
  the case where required input/submission files are missing, malformed,
  or `inputs/traces.csv` is not parseable as plain CSV.

## Requirements checked

The script checks the following requirements, each corresponding to an
identically-named requirement in the task's public specification:

- **FR1** -- Structural validity of `vulnerability_report.json`: required
  top-level fields are present and correctly typed.
- **FR2** -- The report's stated observed latency (8 cycles, constant)
  matches what is actually observed in `inputs/traces.csv`.
- **FR3** -- The `activity_analysis` array covers a sufficient number of
  distinct `secret_operand` values drawn from `inputs/traces.csv`, and the
  reported `enable_count` for each exactly matches the count of
  `mul_en == 1` rows for that operand in `inputs/traces.csv`.
- **FR4** -- `hardening_recommendations` contains a sufficient number of
  well-formed, non-empty recommendation strings.
- **SR1** -- The report correctly identifies the relationship between
  `enable_count` and the Hamming weight of `secret_operand` for every
  analyzed entry.
- **SR2** -- The report explicitly acknowledges that constant/fixed `done`
  latency alone does not prevent side-channel leakage.
- **SR3** -- At least one hardening recommendation targets equalizing
  per-cycle switching/enable activity, rather than relying solely on
  timing/delay-based countermeasures.

See the task's `public_spec` (functional and security requirements) for the
full normative wording of each requirement.