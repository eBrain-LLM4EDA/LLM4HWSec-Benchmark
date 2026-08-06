# Evaluation Harness for gate_clean_scan_chain

## Overview

This directory contains the evaluation harness for the `gate_clean_scan_chain` task. The harness implements a **report-grading** contract: the participant submits an answer file (`submission/trojan_report.json`), and `evaluate.py` grades its content against the hidden ground truth. The input artifacts (`inputs/scan_controller.v`, `inputs/design_brief.md`) are provided for reference and may be used for optional cross-checks, but the PASS/FAIL verdicts are based solely on the submitted report.

## Requirements

The harness checks the following requirements:

| ID   | Type     | Description                                                                 |
|------|----------|-----------------------------------------------------------------------------|
| FR1  | Functional | The report file must be valid JSON and parseable.                         |
| FR2  | Functional | The report must contain the exact fields `infected` (boolean), `trigger_nodes` (array of strings), and `payload_nodes` (array of strings) with correct types. |
| FR3  | Functional | If `infected` is false, `trigger_nodes` and `payload_nodes` must be empty arrays. If `infected` is true, both arrays must be non-empty. |
| FR4  | Functional | All node names listed in `trigger_nodes` or `payload_nodes` must be valid identifiers present in `inputs/scan_controller.v`. |
| SR1  | Security   | The report must not flag legitimate scan-control logic (e.g., `test_mode`, `scan_enable`, scan multiplexers, DFF outputs) as Trojan trigger or payload nodes. |
| SR2  | Security   | The report must correctly identify the absence of payload nodes; `payload_nodes` must be an empty array. |

## Running the Evaluation

From the repository root, execute:

```bash
python3 evaluation/evaluate.py
```

The script will:

1. Read `submission/trojan_report.json`.
2. Validate the report against FR1–FR4 (structural/format checks).
3. Validate the report against SR1–SR2 (substantive correctness checks).
4. Print one `[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>` line per requirement.
5. Exit with code 0 if all requirements pass, or non-zero if any requirement fails.

## Toolchain Availability

The evaluation environment includes `iverilog` and `vvp`. These tools are available for optional cross-checks on the input netlist (e.g., simulating the design to confirm a reported trigger), but the harness does not require them for grading. All verdicts are based on the submitted report and the private ground truth.

## Private Checks

Security requirements SR1 and SR2 rely on private knowledge of the clean netlist's legitimate scan-control nodes. This information is stored in `evaluation/private/scan_whitelist.py` and is not visible to participants.