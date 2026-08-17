# Evaluation: Early-Exit Signature Comparison (`sca_signature_compare_early_exit_001`)

## How to run

From the repository root:

```
python3 evaluation/evaluate.py
```

The script requires no arguments and produces one `[TEST] PASS: <id>` or
`[TEST] FAIL: <id>: <reason>` line per graded requirement, followed by a
process exit code of `0` (all requirements passed) or non-zero (at least one
requirement failed).

## Toolchain dependency

`evaluate.py` shells out to the Verilog toolchain to obtain ground-truth
cycle counts and match/mismatch verdicts for the fixed RTL under test. The
following executables must be available on `PATH`:

- `iverilog` (with `-g2012` support)
- `vvp`

Both invocations use explicit timeouts (30s) and write build products only
to a temporary directory; nothing under `inputs/` or `submission/` is
modified.

## Required input files

These files are read-only reference material for the evaluator and for the
participant. `evaluate.py` never modifies them:

- `inputs/signature_compare.v` — the RTL module under test (fixed baseline
  design; not edited by participants).
- `inputs/testbench_harness.v` — the reference testbench shipped alongside
  the module for participants' own optional cross-checking.
- `inputs/design_brief.md` — the design brief describing the module's
  external contract.

If any of these files is missing, `evaluate.py` emits
`[TEST] FAIL: SETUP: <filename> not found` and exits with a non-zero code.
Note that `evaluation/tb_reference.v` (the evaluator's own internal oracle
testbench, distinct from `inputs/testbench_harness.v`) is likewise required
infrastructure and produces a `SETUP` failure if absent.

## Submission contract

Participants do **not** edit any file under `inputs/`. The graded artifact
is:

```
submission/vulnerability_report.json
```

`evaluate.py` reads `inputs/signature_compare.v` purely as reference
material (e.g. to sanity-check that a reported signal name corresponds to
something declared in the RTL) and simulates it with
`evaluation/tb_reference.v` to obtain ground-truth cycle counts and
verdicts. All PASS/FAIL verdicts are decided against the content of the
submitted JSON report, not against any RTL the participant might submit
(there is none — this task is pure analysis). If
`submission/vulnerability_report.json` is missing or is not valid JSON, the
evaluator emits `[TEST] FAIL: SETUP: submission/vulnerability_report.json
not found` (or a JSON-parse SETUP failure) and exits non-zero.

## Requirement checklist

| ID  | Type       | One-line pass criterion |
|-----|------------|--------------------------|
| FR1 | functional | `baseline_behavior.full_match_verdict` equals the measured full-match verdict (`"match"`) from simulating the fixed RTL. |
| FR2 | functional | `baseline_behavior.mismatch_at_zero_verdict` equals the measured verdict (`"mismatch"`) for a signature that mismatches only at byte position 0. |
| FR3 | functional | The report is valid JSON containing all required top-level keys (`early_exit_signal`, `cycle_relationship`, `constant_time_fix`, `baseline_behavior` with its two verdict sub-fields, `proposed_fix_preserves_correctness`), each present with a correctly typed, non-empty value. |
| FR4 | functional | `proposed_fix_preserves_correctness` is present, boolean, and `true`. |
| SR1 | security   | `early_exit_signal` names or unambiguously describes the internal signal/condition (e.g. a `mismatch_found`-style register or the `expected_byte != received_byte` comparison) that causes `done` to assert before all 16 bytes are consumed. |
| SR2 | security   | `cycle_relationship` parses as a linear formula in the first-mismatch position `k` that predicts every one of the 17 measured cycle counts (16 mismatch positions + full match) to within ±1 cycle. |
| SR3 | security   | `constant_time_fix` describes all three required remediation elements: removing the early-exit branch, unconditionally scanning all 16 bytes every comparison, and accumulating a sticky/OR'd mismatch flag. |
| SR4 | security   | The report does not claim the baseline design is already constant-time, and its `cycle_relationship` is not a constant formula that contradicts the measured cycle-count variation across mismatch positions. |

## Ground-truth cycle relationship (evaluator-internal)

For cross-checking purposes only, the evaluator's reference simulation of
the shipped baseline RTL follows the relationship
`cycles_to_done = k + 2`, where `k` is the 0-indexed position of the first
mismatching byte (`k = 0` → 2 cycles), with the full-match case taking one
step beyond the last mismatch position (equivalent to evaluating the same
formula at `k = 16`, i.e. 18 cycles). This value is derived by
`evaluate.py` itself from live `iverilog`/`vvp` simulation of
`inputs/signature_compare.v` together with `evaluation/tb_reference.v` — it
is not hardcoded as an assumed constant, and is used solely to grade SR2's
tolerance check (±1 cycle) and SR4's contradiction check. It is not an
official answer key beyond what the public task specification already
discloses (that a linear relationship of this general shape exists), and
participants are expected to derive and report the same relationship
independently through their own analysis of the RTL.