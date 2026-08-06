# Logic Deobfuscation and SAT Attack Assistance

## Objective

Analyze the provided combinational netlist and determine whether it contains any key-gate logic inserted by a logic locking tool. If locking is present, recover the correct key bits and identify the key-gate instances. If the netlist is unlocked, report that no locking exists.

The netlist may contain ordinary control multiplexers and XOR gates that are part of the functional design. Your analysis must distinguish these from actual key-gate structures to avoid false positives.

## Input Artifacts

- `inputs/locked_netlist.v` – A structural Verilog netlist that may or may not contain logic locking.
- `inputs/locking_scheme.txt` – A description of the locking algorithm that was supposedly applied. This description may or may not match the actual netlist; rely on structural analysis of the netlist itself.

## Expected Output

Produce a single JSON file at `submission/recovered_key.json` with the following schema:

```json
{
  "locked": <boolean>,
  "key_bits": <string>,
  "key_gates": [<string>, ...]
}
```

- `locked` (boolean): `true` if the netlist contains key-gate logic, `false` otherwise.
- `key_bits` (string): If `locked` is `true`, a non-empty string of `'0'` and `'1'` characters representing the recovered key. If `locked` is `false`, this must be the empty string `""`.
- `key_gates` (array of strings): If `locked` is `true`, a non-empty list of instance names from the netlist that correspond to key gates. If `locked` is `false`, this must be an empty array `[]`.

### Example (unlocked design)

```json
{
  "locked": false,
  "key_bits": "",
  "key_gates": []
}
```

## Constraints

- The netlist is a structural Verilog file that can be simulated with `iverilog` and `vvp`.
- You must not modify the input artifacts.
- Your submission must be a single JSON file; no other files will be graded.