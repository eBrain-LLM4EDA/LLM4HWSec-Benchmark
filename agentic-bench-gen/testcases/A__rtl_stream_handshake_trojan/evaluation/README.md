# Evaluation Harness for RTL Trojan Detection

## Grading Contract

This evaluation follows the **report_grading** contract. The participant submits an analysis report file at `submission/trojan_report.json`. The grader (`evaluate.py`) reads the input artifacts under `inputs/` for reference (the RTL design and design brief) but **grades only the submitted answer file**. The input artifacts are not modified by the participant.

## Requirements

The following requirements are checked by `evaluate.py`:

| ID   | Type       | Description                                                                 |
|------|------------|-----------------------------------------------------------------------------|
| FR1  | functional | The submitted `trojan_report.json` must be valid JSON and parseable.        |
| FR2  | functional | The report must contain all required fields: `trojan_present`, `trigger_condition`, `payload_effect`, `trigger_signals`, `payload_signals`, `confidence`. |
| FR3  | functional | The `confidence` field must be a number between 0.0 and 1.0 inclusive.      |
| SR1  | security   | The analysis must correctly identify the rare sequential trigger condition based on the valid-ready handshake history (trigger pattern, signals). |
| SR2  | security   | The analysis must correctly identify the payload logic that corrupts the output valid signal (payload effect, signals). |

## Running the Evaluation

Execute from the repository root:

```bash
python evaluation/evaluate.py
```

The script will:
1. Read `submission/trojan_report.json`.
2. Validate JSON structure and required fields (FR1–FR3).
3. Compare the submitted findings against the private ground truth (SR1–SR2).
4. Print `[TEST] PASS` or `[TEST] FAIL` markers for each requirement.
5. Exit with code 0 if all requirements pass, non-zero otherwise.

## Available Toolchain

The following tools are available for optional cross-checks on the input artifacts (not required for grading):

- `iverilog` – Verilog compiler
- `vvp` – Verilog simulation runtime
- `yosys` – RTL synthesis and analysis

These tools may be used to simulate the netlist or perform structural analysis to confirm a reported trigger, but the PASS/FAIL verdicts are determined solely by the content of `submission/trojan_report.json` against the hidden ground truth.