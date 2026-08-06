# Evaluation Harness for RTL Variable-Latency Divider

## Overview

This directory contains the evaluation harness for the side-channel analysis task. The participant submits a vulnerability report in JSON format, and the harness grades it against hidden ground truth criteria.

## Submission Contract

The participant must submit a single file:

```
submission/vulnerability_report.json
```

This file must be a valid JSON object with exactly three top-level keys:

- `vulnerability_found` (boolean)
- `vulnerable_component` (string)
- `recommended_fix` (string)

The participant does **not** modify the input artifacts (`inputs/divider.v`, `inputs/timing_traces.txt`). The harness reads those artifacts for reference only.

## Evaluation Contract

The evaluation is **report grading**: `evaluate.py` opens the submitted JSON file and checks its structure and content against the requirements. The toolchain (`iverilog`, `vvp`, `yosys`) is available for optional cross-checks on the input artifacts, but the PASS/FAIL verdicts are based solely on the submitted report.

## Requirements

### Functional Requirements (FR)

| ID   | Description |
|------|-------------|
| FR1  | The submission file is valid JSON and contains the top-level keys `vulnerability_found`, `vulnerable_component`, and `recommended_fix`. |
| FR2  | The `vulnerability_found` field is a boolean. |
| FR3  | The `vulnerable_component` field is a non-empty string. |
| FR4  | The `recommended_fix` field is a non-empty string. |

### Security Requirements (SR)

| ID   | Description |
|------|-------------|
| SR1  | The `vulnerable_component` string correctly identifies the `early_done` signal or the comparator that generates it as the source of variable latency. |
| SR2  | The `recommended_fix` string describes removing the early-termination condition and forcing the divider to run for a fixed number of cycles equal to the data width. |

## How to Run

```bash
python3 evaluation/evaluate.py
```

The script exits with code 0 if all requirements pass, and non-zero otherwise. Each requirement produces a `[TEST] PASS` or `[TEST] FAIL` marker on stdout.

## Hidden Ground Truth

The private ground truth constants and helper functions used for SR checks are located in `evaluation/private/ground_truth.py`. This file is not visible to participants.

## Input Artifacts

The following files are provided in `inputs/` and may be used for optional cross-validation:

- `divider.v` — Iterative unsigned divider with early termination
- `timing_traces.txt` — Timing observation model and measured cycle counts