# Logic Deobfuscation and SAT Attack Assistance — Evaluation

## Overview

This task asks you to analyze a locked, gate-level combinational netlist
(`inputs/locked_c880.v`) together with a set of input/output oracle vectors
(`inputs/oracle_vectors.txt`) captured from the correctly-keyed (golden)
circuit, and to produce a single JSON answer file describing what you were
able to determine about the design's key-controlled gates and activation
key.

Background on the design and the general locking style used is provided in
`inputs/design_brief.md`. You do **not** have access to the golden
(unlocked) netlist itself — only the locked netlist and the oracle vectors.

## What you submit

A single file:

```
submission/recovered_key.json
```

No other files are read for grading. Do not modify anything under
`inputs/`.

## Required schema

`submission/recovered_key.json` must parse as JSON with exactly this
top-level shape:

```json
{
  "key_width": <integer>,
  "recovered_key": "<string of length key_width over the characters 0, 1, x>",
  "key_gates": [
    {
      "key_bit_index": <integer, 0..key_width-1>,
      "gate_name": "<string; must match a gate instance name that exists in inputs/locked_c880.v>",
      "locked_signal": "<string; name of the internal net protected by this key gate>",
      "gate_type": "XOR" | "XNOR" | "MUX" | "BUF" | "UNKNOWN",
      "inferred_value": "0" | "1" | "x"
    }
  ]
}
```

Field notes:

- `key_width`: the number of bits on the netlist's key input bus. This can
  be read directly from the port declaration in `inputs/locked_c880.v`.
- `recovered_key`: your best-effort recovered key string, ordered from bit
  0 to bit `key_width - 1`. Use `x` for any bit position you cannot
  determine with confidence from the supplied oracle vectors — do not
  guess arbitrarily. Some bits may genuinely be undeterminable from the
  given oracle vector set; reporting them as `x` is expected and
  appropriate in that case.
- `key_gates`: your list of identified key-controlled gate instances. Each
  `gate_name` must correspond to an actual instance name present in
  `inputs/locked_c880.v`. `gate_type` must be one of the five listed
  values. Report only the gates you have genuine evidence for — do not
  simply enumerate every gate in the netlist.

## Running the evaluator locally

From the repository root:

```
python3 evaluation/evaluate.py
```

The evaluator will:

1. Read `inputs/locked_c880.v`, `inputs/design_brief.md`, and
   `inputs/oracle_vectors.txt` for reference and cross-checking purposes
   (it does not grade these files; they are fixed inputs for your
   analysis).
2. Read and grade `submission/recovered_key.json`.
3. Print one line per checked requirement, either:
   - `[TEST] PASS: <requirement_id>`, or
   - `[TEST] FAIL: <requirement_id>: <reason>`
4. Exit with status code `0` only if every requirement passes; otherwise
   exit non-zero.

The evaluator may invoke `iverilog`/`vvp`/`yosys` internally to simulate or
structurally analyze `inputs/locked_c880.v` as part of cross-checking your
submission. This is done purely for grading purposes; you are not required
to run any simulator yourself, although doing so (or using `yosys` for
structural analysis) may help you produce a more accurate answer.

## Tips

- A submission that reports every bit as `x` and an empty `key_gates` list
  is the trivial/naive baseline and will not pass — it demonstrates no
  analysis.
- A submission that lists every gate in the netlist as a "key gate" is
  also not acceptable — it demonstrates guessing/brute enumeration rather
  than genuine localization.
- Focus on gates whose inputs are wired directly to a bit of the `keyIn`
  bus, and use the oracle vectors to determine, where possible, the
  correct value of each such bit.
- Not every key bit is necessarily recoverable from a finite set of oracle
  vectors; `inputs/design_brief.md` discusses why some bits may remain
  indeterminate regardless of how many vectors are examined.