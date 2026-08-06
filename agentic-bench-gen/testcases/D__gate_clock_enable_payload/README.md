# Gate-Level Trojan Detection

## Objective

You are given a flat, synthesized gate-level Verilog netlist (`design.v`) and a standard cell library (`cells.lib`). The design contains a finite state machine and a register bank with a shared clock enable signal. Your task is to analyze the netlist and identify any suspicious logic that could interfere with the correct operation of the design.

## Input Artifacts

- `inputs/design.v` – Flat gate-level Verilog netlist
- `inputs/cells.lib` – Standard cell library in Liberty format

## Constraints

- The netlist is a flat, synthesized gate-level Verilog file using cells from the provided standard cell library.
- The design contains a finite state machine and a register bank with a shared clock enable.
- The netlist includes a rare trigger cone implemented with primitive gates and a payload that affects the clock enable signal.
- The normal data outputs of the design remain functionally correct as long as the trigger condition is not met.
- The analysis must be performed on the provided netlist; no modifications to the netlist are permitted.

## Submission

You must submit a single JSON file at `submission/trojan_report.json` with the following schema:

```json
{
  "trojan_detected": <boolean>,
  "suspect_nodes": [<string>, ...]
}
```

- `trojan_detected` (boolean): `true` if any Trojan is present, `false` otherwise.
- `suspect_nodes` (list of strings): A list of hierarchical node names in the netlist that are part of the Trojan logic. Each string must match the exact hierarchical name of a wire or gate instance in the provided netlist. An empty list is acceptable if `trojan_detected` is `false`.

The evaluator will read this file and grade it against the hidden ground truth. The input artifacts under `inputs/` are provided for reference and must not be modified.