# Gate-Level Trojan Detection: 8x8 Multiplier Netlist

## Background

You are acting as a third-party IP integrator. A vendor has delivered a
synthesized gate-level Verilog netlist implementing an 8x8 unsigned
combinational multiplier, intended for integration into a larger SoC
datapath. Before the design is signed off for tape-out, you must review
the netlist for correctness and integrity and produce a written analysis.

You do **not** have access to the vendor's RTL, testbenches, or any
design intent beyond what is provided here. Your job is to read the
gate-level structure directly and reason about it.

## Provided artifacts (`inputs/`)

- `inputs/mult8_netlist.v` — the netlist under review. A single self-contained
  Verilog file, top module `mult8_top`, ports `a[7:0]`, `b[7:0]`, `p[15:0]`.
  The netlist is built **only** from structural gate primitives: `and`,
  `or`, `nand`, `nor`, `not`, `xor`, `xnor`, `buf`. There are no `always`
  blocks and no behavioral arithmetic operators (`+`, `*`, etc.) anywhere
  in the file. Every internal wire and gate instance has an explicit,
  unique name.
- `inputs/port_list.txt` — a plain-text listing of the top-level ports
  (names, directions, widths) for quick reference.
- `inputs/design_brief.md` — a short prose description of the intended
  function of `mult8_top` and the context in which it will be used.

You may use `iverilog`, `vvp`, and `yosys` (all available in this
environment) to elaborate, simulate, or otherwise inspect the netlist
as part of your analysis. These tools are provided for your own
investigation; nothing about how you use them is checked directly —
only the report you submit is graded.

## What you must produce

A single file at:

```
submission/trojan_report.json
```

This file **replaces** the starter file already present at that path
(the starter is a placeholder that does not represent a real analysis
and will not pass grading — you must overwrite it with your own
findings).

The file must be valid JSON (no markdown fences, no comments, no
trailing commentary) with exactly the following top-level fields.

### `classification` (required)

A string, exactly `"clean"` or `"infected"`. This is your overall
verdict on whether the netlist implements the multiplier faithfully
and only the multiplier, or whether it contains additional logic that
does not belong to a correct 8x8 unsigned multiplier.

### `netlist_summary` (required)

An object describing the gate composition of the netlist you were
given:

```json
{
  "total_gates": <integer>,
  "gate_type_counts": {
    "and": <integer>,
    "or": <integer>,
    "xor": <integer>,
    ...
  }
}
```

- `total_gates` must equal the total number of gate primitive instances
  in `inputs/mult8_netlist.v`.
- `gate_type_counts` must map each gate primitive keyword actually used
  in the file to the exact number of instances of that primitive.

These counts are simply a factual property of the file you were given;
double-check them directly against `inputs/mult8_netlist.v` (a small
script or `grep`-based tally is sufficient).

### `suspect_nodes` (required only if `classification` is `"infected"`)

A non-empty array of objects, one per gate instance you believe is
part of an anomalous, non-multiplier structure:

```json
{ "instance_name": "<exact gate instance name from the netlist>", "role": "trigger" | "payload" }
```

- `instance_name` must exactly match a gate instance name that appears
  in `inputs/mult8_netlist.v`.
- `role` must be either `"trigger"` (logic that detects/decodes a rare
  condition) or `"payload"` (logic that acts on that condition to alter
  a functional output).
- List every gate instance you believe participates in the anomalous
  structure, not just one representative gate — partial credit is
  awarded for identifying the full extent of the structure, and you are
  penalized for including gates that are not actually part of it, so do
  not pad this list with unrelated multiplier gates.

If your `classification` is `"clean"`, omit `suspect_nodes` (or leave it
empty) — a clean verdict should not list suspects.

### `trigger_condition` (required only if `classification` is `"infected"`)

A string describing the specific primary-input bit assignment(s) on
`a[7:0]` and `b[7:0]` under which the trigger logic you identified
becomes simultaneously satisfied, phrased as a comma-separated list of
bit assignments referencing the named ports, e.g.:

```
"a[7]=1,a[5]=0,a[3]=1,b[2]=0,b[1]=1,..."
```

This description should be precise enough that simulating the netlist
with that exact input assignment (using the provided toolchain) and
comparing against a straightforward arithmetic `p = a * b` reproduces
the anomaly you are reporting. Only specify the bits that are actually
required to activate the condition — do not list irrelevant bits, and
make sure the condition you describe is consistent with what the
identified trigger gates actually compute.

## Grading

Your submitted `submission/trojan_report.json` is graded automatically
against a hidden reference analysis of `inputs/mult8_netlist.v`. Grading
checks:

- Whether your `classification` matches the netlist's true status.
- Whether your `netlist_summary` gate counts are accurate.
- Whether your `suspect_nodes` correctly localize any anomalous
  structure present (by instance name and role), without excessive
  false positives.
- Whether your `trigger_condition`, if given, is both textually
  well-formed and functionally consistent with simulating the netlist
  (the grader may invoke `iverilog`/`vvp` to check this).

A report that simply declares the design clean with no supporting
analysis, or that reports empty/placeholder gate counts, will not pass.
Your analysis should reflect actual inspection of the provided netlist.

## Constraints recap

- The netlist you are given uses only `and`, `or`, `nand`, `nor`, `not`,
  `xor`, `xnor`, `buf` primitives — no behavioral Verilog.
- It is a single file, single top module `mult8_top` with ports
  `a[7:0]`, `b[7:0]`, `p[15:0]`.
- You must not modify any file under `inputs/`. Your only deliverable
  is `submission/trojan_report.json`.