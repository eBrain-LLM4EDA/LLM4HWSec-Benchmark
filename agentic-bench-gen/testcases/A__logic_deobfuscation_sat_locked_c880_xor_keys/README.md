# Logic Deobfuscation Challenge: Locked c880 Netlist

## Objective

You are given a gate-level combinational netlist, `locked_c880.v`, derived from
the ISCAS-85 `c880` benchmark. The design has been modified with logic locking:
an 8-bit key input bus, `keyIn[0:7]`, has been threaded through additional
gates inserted into the netlist. Only the correct key value causes the locked
circuit to reproduce the behavior of the original ("golden") circuit.

You also have a set of oracle input/output vectors captured from the golden
(correctly keyed) circuit: `oracle_vectors.txt`.

Your task is to analyze the netlist and the oracle vectors and determine, for
as many of the 8 key bits as you can:

1. **Which gate instance** in the netlist is controlled by that key bit
   (i.e., which gate has `keyIn[i]` as one of its inputs).
2. **What type of gate** implements that key input (e.g. `XOR`, `XNOR`,
   `MUX`, `BUF`, or `UNKNOWN` if you cannot tell).
3. **The most likely value** of that key bit (`0` or `1`) that is consistent
   with all of the supplied oracle vectors, when simulating the netlist with
   that key value.

Not every key bit may be recoverable from the oracle vectors given. If your
analysis cannot confidently determine a bit's value, you must report it as
unknown (`x`) rather than guessing. Guessing incorrectly is scored worse than
honestly reporting "unknown."

## Inputs

All input artifacts are under `inputs/` and must **not** be modified:

- `inputs/locked_c880.v` — the locked structural Verilog netlist. Fixed port
  list: primary inputs, primary outputs, and the `keyIn[0:7]` key bus. Gate
  instance names and net names in this file are the exact identifiers you
  should reference in your submission.
- `inputs/design_brief.md` — a short design note describing the locking
  scheme at a high level, including the key bus width and a note on the
  netlist's gate-naming convention.
- `inputs/oracle_vectors.txt` — a list of primary-input-vector /
  primary-output-vector pairs captured by exercising the correctly-keyed
  (golden) circuit. Use these as a black-box oracle: you do **not** have
  direct access to the golden netlist itself.

You may use any standard analysis technique: reading the netlist structurally
to find gates that take `keyIn` bits as an input, tracing fanout to determine
whether a given key-controlled net actually influences any primary output,
and/or simulating candidate key values against the netlist and comparing the
resulting outputs to the oracle vectors (a SAT-attack-style enumeration).

## Submission

Produce a single JSON file at:

```
submission/recovered_key.json
```

This is the only file that is graded. It must be valid JSON with exactly the
following top-level shape:

```json
{
  "key_width": <integer>,
  "recovered_key": "<string of length key_width over characters {0,1,x}>",
  "key_gates": [
    {
      "key_bit_index": <integer, 0..key_width-1>,
      "gate_name": "<string, must match a gate instance name in inputs/locked_c880.v>",
      "locked_signal": "<string, name of the internal net the key gate protects>",
      "gate_type": "XOR" | "XNOR" | "MUX" | "BUF" | "UNKNOWN",
      "inferred_value": "0" | "1" | "x"
    }
  ]
}
```

Field notes:

- `key_width` must equal the width of the `keyIn` bus as declared in
  `inputs/locked_c880.v`.
- `recovered_key` must have exactly `key_width` characters, one per key bit,
  ordered from `key[0]` to `key[key_width-1]`. Use `'0'` or `'1'` where you
  have determined the bit with confidence, and `'x'` where you have not.
- `key_gates` should list the gates you have identified as key-controlled.
  Each entry's `gate_name` must correspond to an actual instance name found
  in `inputs/locked_c880.v`, and `gate_type` must be one of the five listed
  values. `locked_signal` should name the internal net whose value the key
  gate gates/inverts.
- Do not simply list every gate in the netlist as a "key gate" — this is not
  genuine localization and will be penalized. Report only gates you have
  specific structural or behavioral evidence for.
- If you cannot determine a bit's value from the oracle vectors, report that
  bit as `'x'` in `recovered_key` (and/or `inferred_value: "x"` in the
  corresponding `key_gates` entry). Do not guess arbitrarily — an honest
  "unknown" is scored better than an incorrect guess.

## Grading

The evaluator reads `inputs/locked_c880.v`, `inputs/design_brief.md`, and
`inputs/oracle_vectors.txt` for reference and cross-checking, and may invoke
`iverilog`/`vvp` to simulate the netlist with a candidate key to confirm
findings. Only `submission/recovered_key.json` is graded against hidden
ground truth, on:

- correctness of the recovered key bits,
- accuracy of key-gate localization (correct gate names and gate types),
- how much of the key search space your analysis genuinely resolves,
- and whether your submission conforms to the schema above.

## Constraints

- Do not modify any file under `inputs/`. All of your findings go into the
  single submitted answer file described above.
- Your submission must be valid JSON and must conform exactly to the schema
  given above — extra top-level keys, wrong types, or wrong string lengths
  will cause validation to fail.

A starter/placeholder file already exists at `submission/recovered_key.json`.
It contains no analysis (all key bits unknown, no key gates identified) and
is provided only as a template showing the required shape — replace its
contents with your actual findings before submitting.