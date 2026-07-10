# MUX-Locked Netlist: Key-Gate Identification

## Objective

You are given a gate-level combinational Verilog netlist that has been
logic-locked by inserting several key-controlled 2-to-1 multiplexers at
internal wire locations. Each inserted multiplexer has two data inputs and a
select input driven by a dedicated bit of the bundled `key` input port. Your
task is to analyze the netlist and determine, for **every** key-controlled
multiplexer:

1. Its instance name.
2. Which bit of the `key` port drives its select line (`key_bit_index`).
3. Which value of that key bit (`0` or `1`) makes the multiplexer forward the
   input that reproduces the netlist's intended, correct combinational
   behavior (`resolved_value`).

Report your findings as a single JSON answer file. You are not asked to edit
or resynthesize the netlist — only to analyze it and submit your findings.

## Input Artifacts

All input artifacts live under `inputs/` and are read-only reference
material. Do not modify them; only `submission/recovered_key.json` is graded.

- `inputs/locked_netlist.v` — The locked, structural Verilog netlist. It is
  fully self-contained (only basic gate primitives such as `and`, `or`,
  `xor`, `not`, `nand`, `nor`, wired together to build any multiplexers) and
  can be elaborated/simulated directly with `iverilog`/`vvp` without any
  external libraries. It declares a single module with primary inputs,
  primary outputs, and one bundled input port named `key` of width `N`. Every
  key-controlled multiplexer instance in the file has an instance name that
  contains the substring `keymux`, so you can locate candidate loci with a
  simple `grep -i keymux inputs/locked_netlist.v`. This netlist contains
  exactly 4 such instances, named `u_keymux0`, `u_keymux1`, `u_keymux2`, and
  `u_keymux3`.
- `inputs/locking_description.md` — States the total number of inserted key
  gates and describes the general MUX-locking mechanism used, including the
  exact select polarity of the inserted multiplexers. It does **not** reveal
  which instance corresponds to which key bit, or which key value unlocks
  each gate — that is what you must determine.
- `inputs/primary_io_list.txt` — A plain-text listing of every primary input
  and output port name of `locked_netlist.v`, plus the declared width of the
  `key` port, for quick reference.

## Multiplexer Semantics

Every inserted locking multiplexer implements the standard 2:1 mux function,
built entirely from basic gate primitives (there is no behavioral `mux`
construct anywhere in the file):

```
Y = (S & B) | (~S & A)
```

where `S` is the select line (driven by one bit of `key`), `A` and `B` are
the two data inputs, and `Y` is the multiplexer's output. Under this
formula:

- `S = 0` selects input **A**.
- `S = 1` selects input **B**.

For each locus, exactly one of `A` or `B` is the signal that reproduces the
netlist's intended, correct combinational behavior; the other is a
corrupted/decoy variant. The `resolved_value` you report for a given
multiplexer must be the key bit value (`0` selects `A`, `1` selects `B`)
that causes that multiplexer to forward its correct-behavior input. Getting
this polarity backwards will cause every non-trivial locus to be scored as
wrong, so be careful to trace, for each instance, which input is `A` and
which is `B` as connected in the module instantiation.

## What You Submit

Submit exactly one file:

```
submission/recovered_key.json
```

This file must be valid UTF-8 JSON (standard JSON only — no comments, no
trailing commas) and must conform to the following schema:

```json
{
  "key_bits": "<string of 0/1 characters, length N>",
  "key_gates": [
    {
      "instance_name": "<string, must match a keymux instance name in locked_netlist.v>",
      "key_bit_index": 0,
      "resolved_value": 0
    }
  ],
  "notes": "<string, may be empty; summarize your analysis method>"
}
```

Field requirements:

- **`key_bits`**: a string of exactly `N` characters, each `0` or `1`, where
  `N` is the width of the `key` input port declared in the module header of
  `inputs/locked_netlist.v` (i.e. `key[N-1:0]`). For this netlist, `N = 4`,
  so `key_bits` must be exactly 4 characters long, e.g. `"1011"`. Bit `i` of
  this string is your recovered value for `key[i]`.
- **`key_gates`**: a JSON array with one entry per key-controlled
  multiplexer instance that actually exists in `inputs/locked_netlist.v`.
  The number of entries must equal the total number of keymux instances
  present in the netlist (this count is stated in
  `inputs/locking_description.md`; for this netlist there are exactly 4
  such instances: `u_keymux0`, `u_keymux1`, `u_keymux2`, `u_keymux3`). Each
  entry must include:
  - `instance_name` — the exact instance name of the multiplexer as it
    appears in `inputs/locked_netlist.v`.
  - `key_bit_index` — the index (0-indexed, in `0..N-1`) into `key_bits` /
    the `key` port that drives this multiplexer's select line.
  - `resolved_value` — `0` or `1`: the key bit value that causes this
    multiplexer to forward the input producing correct circuit behavior,
    under the `S=0 selects A, S=1 selects B` convention described above.
- **`notes`**: a string (may be empty) briefly describing how you performed
  the analysis (e.g. structural inspection, truth-table comparison,
  simulation-based testing, etc.).

## How Grading Works

An evaluator reads `inputs/locked_netlist.v`, `inputs/locking_description.md`,
and `inputs/primary_io_list.txt` for reference, and grades the content of
`submission/recovered_key.json` against a hidden ground-truth key and
hidden ground-truth list of keymux loci. Grading considers:

- Whether your `key_bits` matches the correct key value at every true lock
  bit position.
- Whether your `key_gates` array correctly identifies every true keymux
  instance and its `key_bit_index` (precision and recall over
  `instance_name` + `key_bit_index` pairs).
- Whether `submission/recovered_key.json` is valid JSON and satisfies the
  schema described above.

Only the contents of `submission/recovered_key.json` are graded — you do not
need to submit any modified netlist or additional files.

## Suggested Approach

1. Start by locating candidate lock sites:
   ```
   grep -n keymux inputs/locked_netlist.v
   ```
2. Trace the gate-level structure feeding each `keymux`-named instance to
   understand which two candidate signals it selects between, and which
   input (`A` or `B`) corresponds to the functionally correct signal versus
   a corrupted/decoy signal.
3. Determine which bit of the `key` port feeds each multiplexer's select
   line by tracing the port connections back to the module's `key` input.
4. Apply the mux polarity from the "Multiplexer Semantics" section above
   (`S=0` selects `A`, `S=1` selects `B`) to convert your A-vs-B
   determination into the correct `resolved_value` for each locus.
5. Optionally, use `iverilog`/`vvp` (and/or `yosys`) to simulate
   `inputs/locked_netlist.v` under different key hypotheses and compare
   resulting output behavior across input vectors to help confirm which
   key value at each locus yields consistent, correct-looking behavior.
6. Assemble your findings into `submission/recovered_key.json` following
   the schema above, replacing the shipped placeholder file.

## Starting Point

A placeholder `submission/recovered_key.json` is included in this
repository as a structural example of the expected file format. It is
**not** a correct answer — it uses an all-zero key guess and an empty
`key_gates` list, and is expected to fail grading. Replace it with your own
analysis results.