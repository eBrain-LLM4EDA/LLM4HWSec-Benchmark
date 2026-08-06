# Evaluation: SECDED Double-Fault Miscorrection Analysis

This directory contains the grading harness for task
`sca_fault_secded_double_fault_miscorrection_001`.

## What is graded

The submission contract for this task is **analysis_report**: participants do
not modify anything under `inputs/`. Instead they submit a single answer file:

```
submission/vulnerability_report.json
```

`evaluate.py` reads the reference RTL (`inputs/secded_codec.v`), the fault
enumeration (`inputs/fault_model.json`), the reference testbench
(`inputs/fault_enum_tb.v`), and the design brief (`inputs/design_brief.md`)
strictly as **reference material** used to compute ground truth. It never
modifies those files. All PASS/FAIL verdicts are computed against the
contents of `submission/vulnerability_report.json`.

## How ground truth is computed

`evaluate.py` does not hardcode any expected fault outcomes. Instead, at
grading time it:

1. Compiles `inputs/secded_codec.v` together with `evaluation/oracle_tb.v`
   using `iverilog`, and runs the result with `vvp`.
2. The oracle testbench drives the DUT with the fixed reference `data_in`
   value (encode path) to obtain the true reference codeword and true
   reference 8-bit data value, then applies the same single-bit and two-bit
   fault enumeration order used in `inputs/fault_model.json` to
   `codeword_in` (decode path), printing the DUT's `syndrome`,
   `overall_parity_error`, `correctable`, `uncorrectable`,
   `correction_mask`, and `data_out` for every one of the 91 enumerated
   cases.
3. `evaluate.py` parses this simulation output and cross-references it
   against `inputs/fault_model.json` (matching by `bit_positions`, since
   the oracle testbench generates its own labels independently of
   `fault_id` strings) to build an oracle mapping from each
   `fault_model.json` `fault_id` to true simulated decoder behavior.
4. From this oracle mapping, `evaluate.py` derives, purely from simulation:
   - the true reference 8-bit data value,
   - the ground-truth miscorrection set (two-bit faults where the DUT's
     `syndrome != 0` and `overall_parity_error == 1`),
   - the ground-truth zero-syndrome escape set (two-bit faults where the
     DUT's `syndrome == 0`).

No specific fault_id, syndrome value, or data value is hardcoded anywhere in
this evaluation directory. Every numeric fact used for grading is derived at
runtime from simulating the actual `inputs/secded_codec.v` provided in the
task's `inputs/` directory.

Note: the shipped `inputs/fault_model.json` is a Markdown document (a prose
paragraph followed by a fenced ` ```json ... ``` ` code block containing the
actual JSON payload), not a bare JSON file. `evaluate.py`'s loader is robust
to this: it tries a raw JSON parse first, then falls back to extracting and
parsing the fenced code block(s), then falls back to a balanced-brace scan
over the raw text — stopping at the first candidate that parses and looks
like a fault list.

## Requirements checked

### Functional requirements (structure / coverage)

- **FR1** — `submission/vulnerability_report.json` parses as JSON and has the
  required top-level and per-case shape (`fault_cases` array with
  `fault_id`, `bit_positions`, `classification` in the allowed enum, and a
  well-formed `observed_outputs` object with all six required sub-fields;
  plus a `summary` object).
- **FR2** — The set of `fault_id` values present in `fault_cases` exactly
  matches the 91 `fault_id` values enumerated in `inputs/fault_model.json`
  (13 single-bit + 78 two-bit), with no missing or duplicated entries.
- **FR3** — For every one of the 13 single-bit fault cases, the reported
  `classification` is `"corrected"` and the reported `observed_outputs.data_out`
  (normalized) equals the true reference 8-bit data value, as established by
  simulation.
- **FR4** — `summary.num_no_error + summary.num_corrected +
  summary.num_detected_uncorrectable == 91`, and these counts match the
  actual tally of `classification` values across the 91 submitted
  `fault_cases` entries.

### Security requirements (substantive findings)

- **SR1** — The report must substantively state, somewhere in its narrative
  fields (e.g. `hardening_suggestions`), that the decoder's
  correctable/uncorrectable decision is driven only by `syndrome != 0`
  without consulting `overall_parity_error` — i.e., that the missing
  double-error-detection gate is the root cause. This is checked via
  paraphrase-tolerant keyword/phrase matching over the submitted report's
  text fields (not over any source code), so any of several equivalent
  phrasings is accepted.
- **SR2** — The submitted `vulnerable_fault_ids` set must match the
  simulation-derived ground-truth miscorrection set (two-bit faults with
  `syndrome != 0` and `overall_parity_error == 1` under the actual decoder)
  within a symmetric-difference tolerance of at most 2 elements.
- **SR3** — For at least 90% of the ground-truth miscorrection set, the
  submission's per-case `classification` must be `"corrected"` and its
  `observed_outputs.data_out` must be well-formed and differ from the true
  reference data value — demonstrating that the report captured the silent
  data corruption rather than assuming the decoder produced correct data.
- **SR4** — The report must correctly identify the outcome for the
  simulation-derived zero-syndrome two-bit escape class. If this set is
  non-empty, at least 90% of it must be classified `"no_error"` in the
  submission (matching actual flawed-decoder behavior) AND the report must
  contain an explicit textual finding that separately identifies this
  zero-syndrome escape class as a distinct, undetected corruption risk from
  the miscorrection class. If this set is legitimately empty for the pinned
  reference codeword, the report must instead explicitly and correctly state
  that no such zero-syndrome two-bit escape cases exist, as its distinct SR4
  finding.

## Marker format

Each requirement above emits exactly one line of the form:

```
[TEST] PASS: <REQUIREMENT_ID>
[TEST] FAIL: <REQUIREMENT_ID>: <brief reason>
```

`evaluate.py` exits with code `0` only if every requirement (`FR1`–`FR4`,
`SR1`–`SR4`) emits `PASS`. If any requirement emits `FAIL`, the process exits
non-zero.

Infrastructure problems (e.g. a required input file under `inputs/` is
missing, or `evaluation/oracle_tb.v` fails to compile against the provided
RTL, or `submission/vulnerability_report.json` itself is absent) are reported
as:

```
[TEST] FAIL: SETUP: <details>
```

and also cause a non-zero exit. `SETUP` failures indicate a problem with the
evaluation environment or a missing submission file, not a graded requirement
outcome. A submission file that exists but fails to parse as JSON is instead
reported as `[TEST] FAIL: FR1: ...` (not `SETUP`), since a malformed answer
file is a graded requirement failure, not an infrastructure problem.

## Toolchain

`evaluate.py` uses only the Python standard library for its own logic. It
invokes `iverilog` and `vvp` via `subprocess` (with explicit timeouts) to
simulate `inputs/secded_codec.v` against `evaluation/oracle_tb.v`. No network
access is required or used. All simulation inputs (fault positions, fixed
reference data value) are deterministic, so repeated runs against the same
submission and inputs always produce the same verdicts.