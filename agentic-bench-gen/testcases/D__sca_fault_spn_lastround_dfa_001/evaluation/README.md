# Evaluation Harness — Last-Round DFA on a Toy SPN

This directory contains the grading harness for task
`sca_fault_spn_lastround_dfa_001`.

## How to run

```
python3 evaluation/evaluate.py
```

The script requires no arguments and no network access. It uses only the
Python standard library. It exits with status code `0` if every requirement
check passes, and a non-zero status code if any requirement check fails.

## What it reads

- `inputs/spn_core.v` — the cipher datapath RTL, used as the reference
  source for the S-box table (parsed directly from the source text, never
  hardcoded) and for the internal register pipeline structure.
- `inputs/spn_top.v` — the top-level wrapper RTL (validated as present; may
  optionally be used for simulation-based cross-checks with `iverilog`/`vvp`).
- `inputs/fault_model.md` — the fault-injection methodology description
  (validated as present; documents the campaign that produced
  `trace_pairs.json`).
- `inputs/design_brief.md` — the cipher's functional design description
  (validated as present).
- `inputs/trace_pairs.json` — the correct/faulty ciphertext trace pairs used
  to independently re-derive the recoverable final-round subkey nibble via
  differential fault analysis (DFA).
- `submission/vulnerability_report.json` — **the file being graded.** This
  is the only file the participant produces. If it is missing, unreadable,
  or not valid JSON, every requirement below is reported as a `SETUP`
  failure and the harness exits non-zero.

The harness does **not** modify anything under `inputs/`, and it does not
require or use any file other than the five listed above plus the
submission file.

## What it checks

Two families of checks are run, one PASS/FAIL line per requirement, each
printed as either:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <brief reason>
```

### Structural / format checks (FR1–FR4)

These verify that `vulnerability_report.json` is well-formed and matches the
interface contract described in the task's `public_spec`:

- **FR1** — the JSON object contains all seven required top-level fields,
  each with the correct type (string / integer / string / integer / string
  / string / array of strings).
- **FR2** — `affected_nibble_index` and `recovered_subkey_nibble_index` are
  each integers in the range 0–3 inclusive.
- **FR3** — `recovered_subkey_nibble_value` is exactly one hexadecimal
  character (`0`–`9`, `a`–`f`, or `A`–`F`).
- **FR4** — `hardening_recommendations` contains at least two distinct,
  non-empty strings of at least 10 characters each, and `analysis_method`
  is at least 20 characters long.

These checks are purely structural: they do not evaluate whether the
*content* of the report is correct, only whether it is shaped correctly.

### Substantive correctness checks (SR1–SR4)

These verify that the *content* of the report is actually correct, judged
against the hidden ground truth for this task and, where applicable,
independently cross-validated against the reference RTL and trace data
rather than trusting the submission's own claims:

- **SR1** — the reported `vulnerable_register` correctly identifies the
  exploitable register in the design (not an unrelated register).
- **SR2** — the reported `vulnerable_cycle_offset` and
  `affected_nibble_index` correctly localize the fault in time and bit
  position.
- **SR3** — the reported `recovered_subkey_nibble_index` and
  `recovered_subkey_nibble_value` are cross-checked against an independent
  brute-force differential fault analysis. The harness parses the actual
  S-box table directly out of `inputs/spn_core.v` (never from a hardcoded
  table), builds its inverse, and tests all 16 possible final-round subkey
  nibble values against every trace pair in `inputs/trace_pairs.json`,
  eliminating any candidate that is inconsistent with the documented
  nonzero single-nibble fault model on any trace. The submission's claimed
  value is only credited if it matches the independently-derived unique
  surviving candidate.
- **SR4** — at least two of the submitted `hardening_recommendations`
  entries describe concrete, register-level fault-hardening techniques
  (e.g. redundancy/TMR, parity/ECC, duplicate-and-compare, glitch
  detection, randomized timing) rather than generic or irrelevant advice
  (e.g. "use a stronger cipher").

This document intentionally does not disclose the specific expected
values for `vulnerable_register`, `vulnerable_cycle_offset`,
`affected_nibble_index`, `recovered_subkey_nibble_index`, or
`recovered_subkey_nibble_value` — determining those correctly from the
provided RTL and trace data is the analysis task itself. SR3 in particular
is graded by independent recomputation from `inputs/spn_core.v` and
`inputs/trace_pairs.json`, not by comparison against a value stored in
this repository.

## Interpreting the exit code

- **Exit code 0**: every `[TEST] PASS` line was printed; the submission
  satisfies all functional and security requirements.
- **Exit code non-zero**: at least one `[TEST] FAIL` (or `[TEST] FAIL:
  SETUP: ...`) line was printed. `SETUP` failures indicate a missing or
  unreadable required file (either the submission itself or one of the
  reference input artifacts) rather than an incorrect answer.