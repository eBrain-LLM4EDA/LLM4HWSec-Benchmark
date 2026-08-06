# Evaluation Harness for Mixed XOR and MUX Lock Classification

## Overview

This directory contains the evaluation harness for the `locked_mixed_xor_mux` task. The task requires participants to analyze a logic-locked netlist, locate all lock gates, classify each as XOR/XNOR or MUX-based, and recover the complete key. The participant submits a single answer file at `submission/recovered_key.json`.

## Evaluation Contract

This task follows the **report_grading** contract:

- The participant does **not** modify the input artifacts under `inputs/`.
- The participant produces a separate answer file at `submission/recovered_key.json`.
- `evaluate.py` reads the input artifacts for reference (e.g., `public_key_width.txt`, `oracle_vectors.txt`) and grades the submitted answer file against hidden ground truth.
- The toolchain (`iverilog`, `vvp`) is available for optional cross-checks on the input netlist, but the PASS/FAIL verdicts are based solely on the content of the submitted answer file.

## Files

| Path | Purpose |
|------|---------|
| `evaluation/evaluate.py` | Main grading script. Validates the submission format (FR1–FR3) and checks substantive correctness against hidden ground truth (SR1–SR2). |
| `evaluation/private/ground_truth.py` | Private module containing the hidden correct answers (lock gate labels, classifications, key bits, and full key string). Never exposed to participants. |
| `evaluation/README.md` | This file. |

## Requirements Graded

- **FR1**: Submission file exists, is valid JSON, and contains the required top-level keys.
- **FR2**: `recovered_key` is a binary string of the correct length (4).
- **FR3**: `lock_gates` array contains exactly four objects with valid fields.
- **SR1**: Each lock gate is correctly classified as XOR, XNOR, MUX_0, or MUX_1.
- **SR2**: The recovered key exactly matches the hidden correct key `0101`, and each gate's `key_bit` is correct.

## Usage

```bash
python3 evaluation/evaluate.py
```

Exit code 0 indicates all requirements passed; non-zero indicates at least one failure.