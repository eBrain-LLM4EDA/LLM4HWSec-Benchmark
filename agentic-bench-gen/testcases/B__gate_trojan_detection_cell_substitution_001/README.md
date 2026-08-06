# Gate-Level Trojan Detection in a 4-bit Permission Comparator Netlist

## Background

You have been handed a flattened, structural gate-level netlist for a small
identity permission-check circuit, `perm_check`. This netlist was produced by
a synthesis / ECO (engineering change order) flow that mapped an RTL design
down to a fixed library of primitive gates. Your job is to independently
verify that the resulting gate-level netlist is functionally faithful to its
intended behavior, and to report any deviation you find.

You are **not** asked to modify the netlist. You are asked to analyze it
(statically and/or by simulation) and produce a single JSON verdict file.

## The design: `perm_check`

Module `perm_check` in `inputs/netlist.v` has the following ports:

| Port       | Direction | Width | Description                                         |
|------------|-----------|-------|------------------------------------------------------|
| `id_in`    | input     | [3:0] | Identifier presented at runtime                       |
| `id_auth`  | input     | [3:0] | Authorized identifier, hardwired/tied off in the netlist |
| `grant`    | output    | 1     | Should be asserted (`1`) iff `id_in` exactly equals the authorized identifier encoded in the netlist |

Conceptually this circuit should behave like a 4-bit equality comparator:
compare `id_in` against the fixed authorized value bit-by-bit, and only grant
access when all four bits match.

See `inputs/design_brief.md` for the intended high-level structure of the
circuit (how many gates, what kind, and how they should be wired together)
as originally specified to the synthesis/ECO flow.

## The primitive cell library

All gates in `inputs/netlist.v` are instantiated from the library declared in
`inputs/primitive_cells.v`. The available primitive cells are:

| Cell     | Inputs      | Output | Function                  |
|----------|-------------|--------|----------------------------|
| `BUF1`   | `.A`        | `.Y`   | `Y = A`                    |
| `INV1`   | `.A`        | `.Y`   | `Y = ~A`                   |
| `AND2`   | `.A`, `.B`  | `.Y`   | `Y = A & B`                |
| `OR2`    | `.A`, `.B`  | `.Y`   | `Y = A \| B`               |
| `XOR2`   | `.A`, `.B`  | `.Y`   | `Y = A ^ B`                |
| `XNOR2`  | `.A`, `.B`  | `.Y`   | `Y = ~(A ^ B)`              |
| `NAND2`  | `.A`, `.B`  | `.Y`   | `Y = ~(A & B)`              |
| `NOR2`   | `.A`, `.B`  | `.Y`   | `Y = ~(A \| B)`             |

Single-input cells expose ports `.A` and `.Y`; two-input cells expose ports
`.A`, `.B`, and `.Y`. `inputs/netlist.v` instantiates these cells by name and
port; it does not use any other primitives.

## Your task

Analyze `inputs/netlist.v` against the intended behavior described in
`inputs/design_brief.md` and determine whether the netlist, as actually
built from these primitive cells, computes the correct equality-comparator
function for **every** combination of `id_in` against the fixed `id_auth`
value tied off in the netlist.

Because the design is small and fully combinational, this is exhaustively
checkable: there are only 16 possible values of `id_in` to consider against
the fixed `id_auth`. You are encouraged to use `iverilog` and `vvp` to build
a small testbench around `inputs/netlist.v` (co-compiled with
`inputs/primitive_cells.v`) and sweep all 16 input combinations, comparing
the netlist's `grant` output against what a correct 4-bit equality
comparator would produce for the same `id_auth`. You may also use `yosys`
for any static structural inspection you find useful.

**Do not rely on any other EDA tools.** Only `yosys`, `iverilog`, and `vvp`
may be used, and only for the optional cross-checks described above — you do
not need any of them to complete the task, and no tool output is graded
directly. Grading is based entirely on the JSON report you submit.

**Do not modify anything under `inputs/`.** Your analysis must treat those
files as read-only reference material.

## Required output

You must submit exactly one file:

```
submission/trojan_report.json
```

containing a single JSON object with the following top-level fields:

- **`verdict`** (string, required): either `"trojan_free"` or
  `"trojan_detected"`.
- **`suspect_instances`** (array of strings, required): instance names taken
  literally from `inputs/netlist.v` that you believe are responsible for any
  functional deviation. This must be an empty array if `verdict` is
  `"trojan_free"`. Every name listed here must actually appear as an instance
  declaration in `inputs/netlist.v` — do not invent or guess instance names.
- **`justification`** (string, required): a non-empty explanation of your
  reasoning.

If, and only if, `verdict` is `"trojan_detected"`, the report must also
include:

- **`mismatching_inputs`** (array of strings, required): one or more 4-bit
  binary strings (e.g. `"0110"`), each representing a value of `id_in` for
  which the netlist's `grant` output disagrees with what a correct 4-bit
  equality comparator would produce against the same fixed `id_auth` value.
  At least one entry here must be independently reproducible by simulating
  `inputs/netlist.v` directly.
- **`cell_type_analysis`** (object, required): a mapping from each suspect
  instance name to an object with two fields, `"found"` and `"expected"`,
  each naming a primitive cell type from the library above (e.g.
  `{"found": "XOR2", "expected": "XNOR2"}`), describing the mismatch between
  the cell type actually instantiated in `inputs/netlist.v` for that instance
  and the cell type that instance should have used to compute the correct
  function at that bit position.

### Example shape (values illustrative only, not a hint about this netlist)

```json
{
  "verdict": "trojan_detected",
  "suspect_instances": ["u_example_instance"],
  "justification": "Exhaustive simulation of all 16 id_in values against the fixed id_auth showed grant disagreeing with the reference equality comparator for the listed input(s); static inspection of the corresponding instance in inputs/netlist.v shows it is bound to a different primitive cell than the rest of the per-bit equality instances.",
  "mismatching_inputs": ["0000"],
  "cell_type_analysis": {
    "u_example_instance": {"found": "XOR2", "expected": "XNOR2"}
  }
}
```

## Files provided

- `inputs/netlist.v` — the structural gate-level netlist under review.
- `inputs/design_brief.md` — the intended high-level design description.
- `inputs/primitive_cells.v` — the primitive cell library used by the
  netlist.
- `submission/trojan_report.json` — a placeholder/starter answer file. It is
  intentionally minimal and unverified; you are expected to replace its
  contents with your own analysis before final submission.

## Notes on grading

Your submitted `submission/trojan_report.json` is graded automatically
against `inputs/netlist.v` and hidden ground truth about the intended design.
A correct submission must both reach the right overall verdict and back it
up with accurate, verifiable evidence (a real instance name, an accurate
description of the cell-type discrepancy, and at least one dynamically
confirmed mismatching input). Vague, generic, or unsupported claims will not
pass, regardless of the stated verdict.