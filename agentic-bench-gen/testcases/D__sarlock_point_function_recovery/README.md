# SARLock Point-Function Key Recovery

## Objective

You are given a logic-locked combinational netlist that employs a **point-function locking scheme** (SARLock style). Your task is to analyze the netlist and a set of oracle vectors to:

1. **Recover the hidden key** – the 6-bit input pattern that triggers the lock.
2. **Localize the key comparator cone** – identify the nets in the netlist that implement the key comparison and corruption logic.

## Input Artifacts

All input files are located in the `inputs/` directory:

| File | Description |
|------|-------------|
| `locked_netlist.v` | Structural Verilog netlist of the locked circuit. |
| `oracle_vectors.json` | A small set of input-output pairs obtained from the locked circuit. |
| `locking_scheme_description.md` | High-level description of the locking scheme. |

## Background

In a point-function lock, a key comparator monitors the primary inputs of the circuit. The comparator implements an equality check against a secret key. Its output is used to corrupt exactly one functional output bit, but **only when the input pattern matches the key**. For all other inputs, the circuit behaves correctly.

Because the lock corrupts the output on at most one input pattern (the "protected" pattern), conventional SAT-based attacks that rely on many discriminating input patterns are ineffective. Instead, you must analyze the netlist structure and use the provided oracle vectors to deduce which input pattern causes the corruption.

## Available Toolchain

You may use the following tools to inspect and simulate the netlist:

- **Yosys** – for synthesis and netlist analysis.
- **Icarus Verilog (`iverilog`)** – for compilation.
- **VVP** – for simulation.

Example simulation flow:
```bash
iverilog -g2012 -o sim.vvp inputs/locked_netlist.v
vvp sim.vvp
```

## Submission Format

Place your answer in a single JSON file at:

```
submission/recovered_key.json
```

The file must contain a JSON object with the following fields:

```json
{
  "recovered_key": "<6-bit binary string, e.g. '101101'>",
  "key_gate_nets": ["<hierarchical net name>", ...]
}
```

- **`recovered_key`**: A non-empty string consisting only of the characters `'0'` and `'1'`, representing the 6 key bits.
- **`key_gate_nets`**: An array of strings, each being the hierarchical name of a net in `locked_netlist.v` that is part of the key comparator logic (XNOR gates, AND tree, and the final corruption XOR).

## Hints

- The comparator is built from XNOR gates followed by a tree of AND gates.
- The corruption XOR gate flips the least significant bit of the functional output when the comparator output is high.
- The oracle vectors include the protected input pattern – look for the one output that differs from the expected functional behavior.
- The netlist uses a hierarchical module named `lock_comp` that contains the comparator logic.