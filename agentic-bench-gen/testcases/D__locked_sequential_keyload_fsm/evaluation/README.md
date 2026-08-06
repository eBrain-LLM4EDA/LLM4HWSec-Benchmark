# Evaluation Harness for Sequential Lock with Key-Loaded Initial State

## Grading Contract

This evaluation follows the **report_grading** contract. The participant submits an answer file at `submission/recovered_key.json`. The harness reads the input artifacts under `inputs/` for reference (the locked netlist, oracle traces, and design brief) and grades the submitted answer file against hidden ground truth. The submission is not executed or modified; only its content is evaluated.

## Submission File

The expected submission is a single JSON file:

```
submission/recovered_key.json
```

It must contain a JSON object with two keys:

- `"key_sequence"`: a string of exactly four characters, each `'0'` or `'1'`, representing the recovered 4-bit key.
- `"lock_registers"`: a list of exactly four strings, each a valid hierarchical signal name present in `inputs/locked_fsm.v`, representing the DFFs that form the key-load shift register, in serial loading order.

## Requirements Checked

| ID   | Type     | Description |
|------|----------|-------------|
| FR1  | functional | Submission file exists and is valid JSON. |
| FR2  | functional | `key_sequence` field is a 4-bit string of `'0'`/`'1'`. |
| FR3  | functional | `lock_registers` field is a list of 4 valid hierarchical names found in the netlist. |
| SR1  | security   | Key sequence is not trivially extractable from the netlist via simple string search (fail-on-presence). |
| SR2  | security   | Behavioral cross-check: simulation confirms correct key enables functional mode and incorrect keys produce decoy behavior. |

## How to Run

Execute the evaluation script from the repository root:

```bash
python3 evaluation/evaluate.py
```

The script will:

1. Read `submission/recovered_key.json` and `inputs/locked_fsm.v`.
2. Perform format and content checks (FR1–FR3).
3. Perform a static fail-on-presence check on the netlist (SR1).
4. Optionally invoke `iverilog` and `vvp` to simulate the netlist with the submitted key and an incorrect key, verifying functional vs. decoy behavior (SR2). If the tools are not available, SR2 is skipped with a warning but does not cause a failure.

The script prints `[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>` for each requirement and exits with code 0 only if all requirements pass.

## Toolchain

- **Python 3** (required) – standard library only.
- **Icarus Verilog** (`iverilog`, `vvp`) – optional, used for SR2 cross-check simulation. If not installed, SR2 is not evaluated and a warning is printed.

## Hidden Ground Truth

The harness contains the correct key sequence and lock register names internally. These are never revealed to the participant. The baseline submission (`key_sequence="0000"`, `lock_registers=[]`) is guaranteed to fail.