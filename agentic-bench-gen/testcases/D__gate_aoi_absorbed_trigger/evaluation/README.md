# Evaluation Harness for Gate-Level Trojan Detection

## Grading Contract

This task uses **report grading**: the participant submits an analysis report (not modified source code). The evaluation script `evaluate.py` reads the submitted answer file and grades it against a hidden ground truth. The input artifacts (`design.v`, `cells.lib`) are provided for reference only; the participant does not modify them.

## Submission Requirements

The participant must produce a single file:

```
submission/trojan_report.json
```

This file must be a valid JSON object containing the following fields, each mapping to a non-empty array of strings:

- `trigger_cells`: instance names of cells implementing the trigger condition
- `trigger_nets`: names of nets carrying the trigger signal
- `payload_cells`: instance names of cells implementing the payload
- `payload_nets`: names of nets carrying the payload effect

## Evaluation Process

`evaluate.py` performs the following checks:

1. **FR1**: Validates that the submission file exists and contains parseable JSON.
2. **FR2**: Verifies that the JSON object contains exactly the four required top-level keys.
3. **FR3**: Ensures each required key maps to a non-empty array of strings.
4. **FR4**: Confirms that all reported cell instance names and net names exist in the provided netlist (`inputs/design.v`).
5. **SR1**: Checks that the reported trigger components match the hidden ground truth (specific AOI21/OAI22 cells and the net connecting them).
6. **SR2**: Checks that the reported payload components match the hidden ground truth (specific XOR cell and the net connecting the trigger output to it).

Each check emits a `[TEST] PASS` or `[TEST] FAIL` marker. The script exits with code 0 only if all checks pass.

## Available Toolchain

The evaluation environment includes `yosys`, `iverilog`, and `vvp`. These tools are available for optional cross-checks on the input artifacts (e.g., simulating the netlist to confirm a reported trigger), but the PASS/FAIL verdicts are based solely on the content of the submitted `trojan_report.json`.

## Hidden Ground Truth

The exact expected trigger and payload components are stored in `evaluation/private/ground_truth.json` and are never revealed to participants. The evaluation script compares the submitted report against this ground truth to determine substantive correctness.