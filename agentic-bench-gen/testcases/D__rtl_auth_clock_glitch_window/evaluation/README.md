# Evaluation Harness for RTL Auth Clock Glitch Window

## Grading Contract

This evaluation follows a **report_grading** contract. The participant submits an analysis report (a JSON file) that identifies the vulnerable cycle and critical registers in the provided RTL design under a clock-glitch fault model. The evaluation script (`evaluate.py`) grades the submitted answer file against hidden ground truth. The participant does **not** modify the input artifacts; they only provide the answer file.

## Input Artifacts

The following files are provided in the `inputs/` directory and are read-only for the participant:

- `auth_fsm.v` – The RTL design of an authentication finite state machine.
- `fault_model.json` – Description of the clock-glitch fault model.
- `normal_trace.txt` – Cycle-by-cycle behavior of the design under normal (fault-free) operation.

## Submission

The participant must place their answer file at:

```
submission/vulnerability_report.json
```

The file must be a valid JSON object containing the keys `vulnerable_cycle` (integer), `state_register` (string), `result_register` (string), and `explanation` (string).

## Requirements Checked

The evaluation script checks the following requirements:

### Functional Requirements (FR)

- **FR1** – The submission file must be valid JSON and parseable by a standard JSON parser.
- **FR2** – The report must identify exactly one `vulnerable_cycle` as an integer.
- **FR3** – The `state_register` and `result_register` must be strings that match signal names declared in `auth_fsm.v`.
- **FR4** – The `explanation` field must be a non-empty string.

### Security Requirements (SR)

- **SR1** – The reported `vulnerable_cycle` must match the ground truth cycle index (the cycle where the state transitions from COMPARE to DECIDE).
- **SR2** – The reported `state_register` must be `state_q` and the `result_register` must be `auth_result_q`.

## Evaluation Script

The main entry point is `evaluation/evaluate.py`. It:

1. Reads the submission file from `submission/vulnerability_report.json`.
2. Validates the structure and content against the functional requirements.
3. Compares the reported values against the hidden ground truth for the security requirements.
4. Emits `[TEST] PASS` or `[TEST] FAIL` markers for each requirement (FR1, FR2, FR3, FR4, SR1, SR2).
5. Computes and reports the three metrics: `leakage_detection_accuracy`, `fault_coverage`, and `hardening_precision`.
6. Exits with code 0 if all requirements pass, or 1 if any requirement fails.

The toolchain (`iverilog`, `vvp`) is available for optional cross-checks on the input artifacts, but the PASS/FAIL verdicts are based solely on the content of the submitted answer file.