# Evaluation Harness for RTL Second-Order Share Leakage

## Grading Contract

This evaluation follows the **report_grading** contract. The participant submits an analysis report (`submission/vulnerability_report.json`) that is graded against hidden ground truth. The input artifacts (`inputs/masked_datapath.v` and `inputs/leakage_models.json`) are provided for reference and optional cross-checks, but the PASS/FAIL verdicts are based solely on the content of the submitted answer file.

## Input Artifacts

- `inputs/masked_datapath.v` — Two-share masked datapath RTL with pipeline stages.
- `inputs/leakage_models.json` — Defines first-order and pairwise Hamming-distance leakage models.

## Submission File

The participant must place their answer at `submission/vulnerability_report.json`. The file must be valid JSON and conform to the schema described in the task specification.

## Requirements Checked

The harness (`evaluation/evaluate.py`) checks the following requirements:

### Functional Requirements (FR)
- **FR1** — The submission file is valid JSON and parses without errors.
- **FR2** — The `leaking_register_pair` field contains exactly two strings matching signal names present in the RTL.
- **FR3** — The `first_order_analysis` array contains entries for at least the two registers in the leaking pair, each with a boolean `safe` field.
- **FR4** — The `second_order_analysis` object contains a boolean `leaking` field and a non-empty `explanation` string.

### Security Requirements (SR)
- **SR1** — The report correctly identifies the leaking register pair (`share0_stage2_q`, `share1_stage2_q`).
- **SR2** — The report states that both registers appear safe under individual first-order Hamming-distance analysis.
- **SR3** — The report correctly identifies the alignment condition under which the joint transition leaks (both registers update in the same clock cycle).

## Toolchain Availability

The following tools are installed and available for optional cross-checks on the input artifacts:
- `iverilog` — Verilog compiler
- `vvp` — Verilog simulation runtime
- `yosys` — RTL synthesis framework

These tools are **not required** for grading the answer file; `evaluate.py` uses only Python standard library to parse and validate the submission.