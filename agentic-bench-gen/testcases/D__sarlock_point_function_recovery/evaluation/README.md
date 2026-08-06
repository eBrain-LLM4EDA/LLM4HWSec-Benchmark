# Evaluation Harness for SARLock Point-Function Key Recovery

## Overview

This directory contains the evaluation harness for the `sarlock_point_function_recovery` task. The harness grades a participant's submitted answer file (`submission/recovered_key.json`) against hidden ground truth. The evaluation is purely report-based: the submission is an analysis report, not executable code.

## Entry Point

`evaluation/evaluate.py` is the main grading script. It:

1. Reads the participant's submission from `submission/recovered_key.json`.
2. Reads the input artifacts (`inputs/locked_netlist.v`, `inputs/oracle_vectors.json`, `inputs/locking_scheme_description.md`) for reference and validation.
3. Checks the submission against all functional and security requirements.
4. Emits `[TEST] PASS` or `[TEST] FAIL` markers for each requirement.
5. Exits with code 0 if all requirements pass, non-zero otherwise.

## Requirements

| ID   | Type       | Description                                                                 |
|------|------------|-----------------------------------------------------------------------------|
| FR1  | Functional | The submission file is valid JSON and parseable by a standard JSON parser.  |
| FR2  | Functional | The `recovered_key` field is a non-empty string consisting only of '0' and '1'. |
| FR3  | Functional | The `key_gate_nets` field is an array of strings, each a valid net name present in `locked_netlist.v`. |
| SR1  | Security   | The submitted `recovered_key` exactly matches the hidden key.               |
| SR2  | Security   | The submitted `key_gate_nets` contains all ground-truth key-gate nets.      |

## Toolchain Availability

The evaluation environment includes `yosys`, `iverilog`, and `vvp`. These tools are available for optional cross-checks on the input artifacts (e.g., simulating the netlist to confirm a reported trigger), but the PASS/FAIL verdicts are based solely on the content of the submitted answer file.

## Private Ground Truth

Hidden constants (correct key and ground-truth net names) are stored in `evaluation/private/ground_truth.py` and are not accessible to participants.