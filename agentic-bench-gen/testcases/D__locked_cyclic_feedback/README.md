# Cyclic Logic-Locking Key Recovery

## Objective

You are given a gate-level Verilog netlist that has been locked by inserting key-controlled feedback edges. These edges create combinational cycles when the wrong key is applied. Your task is to analyze the locked netlist, identify the key-controlled feedback gates, and recover the correct key that restores acyclic, functional behavior.

## Input Artifacts

All input files are located in the `inputs/` directory:

- **`locked_netlist.v`** – The cyclically locked gate-level netlist. It contains key inputs and feedback multiplexers that introduce cycles for incorrect key values.
- **`oracle.v`** – A combinational reference module with the same primary inputs and outputs as the locked netlist, but without any key inputs or cycles. It implements the correct function.
- **`hints.txt`** – A plain-text file providing public information about the locking scheme (key width, presence of cyclic locking, etc.).

## Expected Output

You must produce a single answer file at `submission/recovered_key.json`. This file should contain your recovered key and, optionally, the names of the feedback gates you identified.

### JSON Schema

```json
{
  "key": "<string of '0' and '1' characters>",
  "feedback_gates": ["<gate_name>", ...]
}
```

- **`key`** (required): A string consisting only of `'0'` and `'1'` characters. Its length must exactly match the key width stated in `hints.txt`.
- **`feedback_gates`** (optional): An array of strings, each naming a netlist gate that implements a key-controlled feedback edge. This field is for informational cross-check only and does not affect the primary pass/fail verdict.

## Toolchain

You may use the following tools to simulate and verify the netlist:

- **Icarus Verilog (`iverilog`)** – for compiling Verilog sources.
- **`vvp`** – the Icarus Verilog simulation runtime.

Example simulation flow:

```bash
# Compile the locked netlist and a testbench together
iverilog -g2012 -o sim.vvp locked_netlist.v tb.v

# Run the simulation
vvp sim.vvp
```

You can apply a candidate key by setting the key inputs in your testbench and checking whether the resulting circuit is cycle-free and functionally matches the oracle for all input combinations.

## Submission

Place your answer file at `submission/recovered_key.json`. The provided baseline submission contains an empty key and will be rejected by the evaluator. Replace it with your actual recovered key.