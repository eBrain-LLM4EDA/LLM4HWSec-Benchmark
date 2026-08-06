# Gate-Level Trojan Detection — Parity Data Path

## Objective

You are given a gate-level Verilog netlist (`design.v`) and a simulation testbench (`design_tb.v`). The circuit implements a simple data path with a parity generator and a parity‑error output. Your task is to **analyze the netlist** and determine whether it contains any malicious modification (a hardware Trojan) that could interfere with the parity‑error signal.

## What you must submit

Create a single file at `submission/trojan_report.json` with the following structure:

```json
{
  "label": "Trojan" | "Trojan-Free",
  "suspect_nodes": ["node_name_1", "node_name_2", "..."]
}
```

- **`label`** – a string, either `"Trojan"` or `"Trojan-Free"`.
- **`suspect_nodes`** – an array of strings. Each string must be a valid hierarchical node name that exists in `design.v`. If you believe the netlist is Trojan‑free, you may leave this array empty.

## Provided artifacts

| File | Description |
|------|-------------|
| `inputs/design.v` | Gate‑level netlist (primitive gates only: `and`, `or`, `not`, `nand`, `nor`, `xor`, `xnor`, `buf`). |
| `inputs/design_tb.v` | Testbench that exercises the data path and parity logic. |
| `inputs/design_brief.md` | Functional description of the intended circuit behaviour. |

## How to proceed

1. Read `inputs/design_brief.md` to understand what the circuit is supposed to do.
2. Examine `inputs/design.v` carefully. Look for any logic that does not belong to a standard parity‑generation / parity‑checking structure.
3. You may simulate the design with the provided testbench (using `iverilog` and `vvp`) and add your own test vectors to probe suspicious behaviour.
4. Record your findings in `submission/trojan_report.json`.

## Evaluation

Your report will be graded automatically against hidden ground truth. The evaluation considers:

- Whether the `label` is correct.
- Whether the `suspect_nodes` list correctly identifies gates involved in the Trojan (if any).

A naive or empty report (e.g., `"Trojan-Free"` with an empty `suspect_nodes` list) will **not** pass.

## Constraints

- Do **not** modify the input artifacts (`design.v`, `design_tb.v`, `design_brief.md`). Only your `submission/trojan_report.json` is graded.
- The netlist uses only primitive gates and a flat hierarchy. All instance names are legal Verilog identifiers.