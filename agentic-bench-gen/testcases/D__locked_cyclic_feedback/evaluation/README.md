# Evaluation Harness for Cyclic Logic-Locking Cone Localization

## Directory Layout

```
evaluation/
├── README.md          # This file
├── evaluate.py        # Main grading script (entry point)
├── tb_check.v         # Verilog testbench template for functional equivalence check
└── private/
    └── ground_truth.py # Hidden ground truth constants (not shipped to participants)
```

## Submission Contract

This task follows an **analysis_report** submission contract. The participant does **not** modify the input artifacts (`inputs/locked_netlist.v`, `inputs/oracle.v`, `inputs/hints.txt`). Instead, they submit a single answer file:

```
submission/recovered_key.json
```

The file must be valid JSON with the following schema:
- Required field `"key"`: a string of `'0'` and `'1'` characters representing the recovered key bits. Its length must match the key width stated in `inputs/hints.txt`.
- Optional field `"feedback_gates"`: an array of strings naming the netlist gates that implement key-controlled feedback edges.

## Evaluation Entry Point

`evaluate.py` is the sole entry point for grading. It:
1. Reads the participant's answer from `submission/recovered_key.json`.
2. Reads the input artifacts from `inputs/` for reference.
3. Performs all checks (functional and security) and emits `[TEST] PASS` or `[TEST] FAIL` markers for each requirement.
4. Exits with code `0` if all requirements pass, non-zero otherwise.

## Toolchain Dependencies

- Python 3 (standard library only)
- Icarus Verilog (`iverilog`, `vvp`)

These are used for optional simulation-based cross-checks on the input netlist and oracle.

## Requirements Checked

| ID   | Type       | Description (summary) |
|------|------------|------------------------|
| FR1  | Functional | `recovered_key.json` is valid, parseable JSON. |
| FR2  | Functional | The `"key"` field is present, is a string of correct length (per `hints.txt`), and contains only `'0'` and `'1'`. |
| FR3  | Functional | When the submitted key is applied to `locked_netlist.v`, the resulting circuit is combinational and functionally equivalent to `oracle.v` for all input combinations (verified via iverilog simulation). |
| SR1  | Security   | The submitted key exactly matches the hidden ground truth key. |
| SR2  | Security   | If the optional `"feedback_gates"` field is provided, it must exactly match the hidden ground truth feedback gate names. |

Ground truth values are stored in `evaluation/private/ground_truth.py` and are **not** revealed to participants.