# Logic Deobfuscation Evaluation Harness

## Purpose

This harness grades a submitted key-recovery answer for a MUX-locked
combinational netlist. It analyzes the provided input artifacts for
reference only; the actual grading target is the answer file you submit
under `submission/`.

## Input artifacts (read-only, for your reference)

- `inputs/locked_netlist.v` — the locked, gate-level structural Verilog
  netlist. Every key-controlled multiplexer instance name contains the
  substring `keymux`. The bundled `key` input port width (N) is declared in
  this file's module port list.
- `inputs/locking_description.md` — describes the MUX-locking mechanism and
  states the total number of inserted key gates.
- `inputs/primary_io_list.txt` — lists all primary input/output port names
  of `locked_netlist.v` for reference.

## What you submit

A single file: `submission/recovered_key.json`

## Required JSON schema

```json
{
  "key_bits": "<string of 0/1 chars, length N>",
  "key_gates": [
    {
      "instance_name": "<string>",
      "key_bit_index": <int>,
      "resolved_value": 0
    }
  ],
  "notes": "<string, may be empty>"
}
```

- `key_bits` must be a string of exactly `N` characters, each `'0'` or
  `'1'`, where `N` is the width of the `key` input port declared in
  `inputs/locked_netlist.v`.
- `key_gates` must be a JSON array. Each element must have:
  - `instance_name` (non-empty string) — must name a MUX instance present
    in `inputs/locked_netlist.v` whose identifier contains `keymux`.
  - `key_bit_index` (non-negative integer) — the bit position of `key[i]`
    driving that instance's select input.
  - `resolved_value` (`0` or `1`) — the key bit value that causes that
    multiplexer to forward the input reproducing the netlist's intended
    (correct) combinational behavior.
- The number of entries in `key_gates` must equal the number of
  `keymux`-named instances actually present in `inputs/locked_netlist.v`
  (this count is also stated in `inputs/locking_description.md`).
- The file must be strict, valid JSON: no trailing commas, no comments.
- `notes` must be present as a top-level string field (it may be empty)
  summarizing your analysis method.

## Running the evaluator

From the task root:

```
python3 evaluation/evaluate.py
```

The evaluator will:

1. Verify all required input artifacts and the submission file exist
   (missing files produce a `SETUP` failure).
2. Validate `submission/recovered_key.json` against the schema above
   (requirements FR1–FR4).
3. Score the substantive correctness of your findings against the
   ground-truth key and locus set for this netlist, computing:
   - `key_recovery_rate` — fraction of true lock bit positions where your
     `key_bits` matches the correct key value.
   - `key_gate_localization_accuracy` — F1 score comparing your submitted
     `(instance_name, key_bit_index)` pairs in `key_gates` against the true
     lock loci.

## Pass/fail criteria

A submission **PASSes** only if:

- It satisfies the JSON schema requirements (FR1–FR4), **and**
- `key_recovery_rate >= 0.9`, **and**
- `key_gate_localization_accuracy >= 0.9`.

Any schema violation, an empty/malformed `key_gates` array, or falling
below either threshold results in a **FAIL**. Each checked requirement
prints exactly one line of the form:

```
[TEST] PASS: <requirement_id>
```

or

```
[TEST] FAIL: <requirement_id>: <reason>
```

The process exits with code `0` only if every check passes; otherwise it
exits non-zero.

## Tips

- Use `grep -n keymux inputs/locked_netlist.v` to enumerate all candidate
  lock sites — no prior knowledge of the specific locking scheme is
  required to find them.
- Trace each multiplexer's two data inputs back through the netlist to
  determine which one reproduces the circuit's intended function and which
  is the corrupted decoy; the key bit value selecting the correct
  (functional) input is the value you should report as `resolved_value`
  for that instance.
- You may use `yosys`, `iverilog`, and `vvp` (available in this
  environment) to simulate `inputs/locked_netlist.v` with a candidate key
  and compare its behavior against your own reconstructed reference, but
  final grading is based solely on the contents of your submitted
  `recovered_key.json`.