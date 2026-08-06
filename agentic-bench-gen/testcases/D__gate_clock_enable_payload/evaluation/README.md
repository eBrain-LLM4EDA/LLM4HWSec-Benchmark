# Evaluation Harness for Gate-Level Trojan Detection

## Grading Contract

This evaluation follows the **report_grading** contract: the participant submits an answer file, not code. The grading script (`evaluate.py`) reads the submitted answer and grades its content against hidden ground truth. The input artifacts (`inputs/design.v` and `inputs/cells.lib`) are provided for reference and are not modified by the participant.

## Submission File

The participant must place a single JSON file at:

```
submission/trojan_report.json
```

The file must conform to the schema described in the task specification:
- `trojan_detected` (boolean)
- `suspect_nodes` (list of strings)

## How Grading Works

`evaluate.py` performs the following checks:

1. **Functional Requirements (FR1–FR3):** Validates the structure and format of the submitted JSON (valid JSON, correct field types, list of strings).
2. **Security Requirements (SR1–SR2):** Checks the substantive correctness of the reported findings against the hidden ground truth (exact hierarchical node names of the trigger and payload).

Each requirement produces a `[TEST] PASS` or `[TEST] FAIL` marker. The script exits with code 0 if all requirements pass, and non-zero otherwise.

## Available Toolchain

The evaluation environment includes the following tools, which may be used for optional cross-checks on the input artifacts (e.g., simulating the netlist to confirm a reported trigger):

- `yosys`
- `iverilog`
- `vvp`

These tools are not required for grading the answer file itself but are available if needed.