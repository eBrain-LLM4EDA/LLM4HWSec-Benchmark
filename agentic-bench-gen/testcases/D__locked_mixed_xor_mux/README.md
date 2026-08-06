# Mixed XOR and MUX Lock Classification

## Objective

You are given a logic-locked Verilog netlist (`locked_netlist.v`) that contains exactly four lock gates. The locking scheme mixes two different styles: XOR/XNOR-based key gates and MUX-based key gates. Your task is to:

1. **Locate** all four lock gates in the netlist and identify their instance labels.
2. **Classify** each lock gate as one of:
   - `XOR` – an XOR key gate
   - `XNOR` – an XNOR key gate
   - `MUX_0` – a MUX-based key gate that passes the functional signal when the key bit is `0`
   - `MUX_1` – a MUX-based key gate that passes the functional signal when the key bit is `1`
3. **Recover** the complete 4-bit key that restores the correct circuit functionality.

## Input Artifacts

All inputs are located in the `inputs/` directory:

- `locked_netlist.v` – The locked Verilog netlist.
- `oracle_vectors.txt` – A set of input-output pairs for the circuit when driven with the correct key. Use these to verify your key recovery through simulation.
- `public_key_width.txt` – Contains the integer `4`, the width of the key.
- `design_brief.md` – A short description of the locked circuit and the oracle vector format.

## Constraints

- The netlist contains exactly four lock sites.
- The key width is provided in `inputs/public_key_width.txt`.
- You must not modify any of the input artifacts.

## Expected Output

Create a single JSON file at `submission/recovered_key.json` with the following structure:

```json
{
  "lock_gates": [
    {
      "gate_label": "<string>",
      "classification": "<XOR|XNOR|MUX_0|MUX_1>",
      "key_bit": <0 or 1>
    },
    ...
  ],
  "recovered_key": "<binary string of length 4>"
}
```

- `lock_gates` must be an array of exactly four objects, one per lock gate.
- `gate_label` is the instance name of the lock gate as it appears in the netlist.
- `classification` must be one of the four allowed strings.
- `key_bit` is the key value (0 or 1) that restores correct operation for that gate.
- `recovered_key` is a string of `'0'` and `'1'` characters whose length equals the value in `public_key_width.txt`. The order of bits should correspond to the key input indices (e.g., `key[0]` through `key[3]`).

The order of objects in `lock_gates` is arbitrary. The evaluator will grade your submission against the hidden ground truth.