# Gate-Level Trojan Detection — Evaluation

## What this evaluates

This harness grades a submitted analysis report against the gate-level
netlist supplied under `inputs/`. It does **not** grade or modify the
netlist itself — the netlist is a fixed, read-only reference artifact.
Your job as a participant is to analyze `inputs/mult8_netlist.v` (with
`inputs/port_list.txt` and `inputs/design_brief.md` as supporting
context) and produce an answer file at:

```
submission/trojan_report.json
```

## How to run

From the repository root:

```
python3 evaluation/evaluate.py
```

The script:

1. Confirms the fixed input artifacts (`inputs/mult8_netlist.v`,
   `inputs/port_list.txt`, `inputs/design_brief.md`) are present.
2. Loads and validates `submission/trojan_report.json`.
3. Parses the reference netlist to determine the actual gate
   composition and the set of valid gate instance names.
4. Checks the submitted report's structure and required fields
   (functional requirements FR1-FR4).
5. Checks the substantive correctness of the submitted findings against
   hidden ground truth (security requirements SR1-SR5), optionally
   cross-checking any reported trigger condition by compiling and
   simulating the real netlist with `iverilog`/`vvp`.

Each requirement produces exactly one line of output:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <reason>
```

The process exits with code `0` only if every requirement passes, and
non-zero otherwise.

## Toolchain requirement

`iverilog` and `vvp` must be available on `PATH` for full grading of
the trigger-condition cross-check (SR4). If they are missing, that
check will fail with a clear `SETUP`-independent reason (it is not
treated as an infrastructure failure, since the report is still
gradable/incomplete without a verifiable trigger condition).

## Required report schema

`submission/trojan_report.json` must be a single JSON object (no
markdown, no extra wrapping) with these top-level fields:

- `classification` (string): exactly `"clean"` or `"infected"`.
- `netlist_summary` (object):
  - `total_gates` (integer): total number of gate primitive instances
    in the netlist.
  - `gate_type_counts` (object): maps each primitive name (`and`, `or`,
    `nand`, `nor`, `not`, `xor`, `xnor`, `buf`) to its instance count in
    the netlist.
- `suspect_nodes` (array, required and non-empty only if
  `classification == "infected"`): each element is an object with:
  - `instance_name` (string): must exactly match a gate instance name
    that actually appears in `inputs/mult8_netlist.v`.
  - `role` (string): one of `"trigger"` or `"payload"`.
- `trigger_condition` (string, required only if `classification ==
  "infected"`): a description of the specific primary input assignment
  (bits of `a` and `b`) under which the reported trigger logic
  activates. This may be expressed either as a per-bit enumeration
  (e.g. `a[7]=1,a[6]=0,...,b[0]=1,...` covering all 8 bits of each
  variable) or as a compact literal (e.g. `a=8'b10110100`,
  `a=8'hb4`, `a=0xb4`, `a=180`). It must be consistent with what
  simulating the netlist actually shows.

`netlist_summary.total_gates` and `gate_type_counts` are checked
exactly against the real gate counts parsed from
`inputs/mult8_netlist.v` — these numbers do not depend on whether the
design is judged clean or infected.

## Notes

- A report claiming `classification == "clean"` with no suspect nodes
  and no trigger condition is a valid, well-formed report under the
  schema (FR1-FR4 do not require infection), but it will not be
  credited for the security requirements that require correctly
  identifying and localizing the actual anomaly present in this
  particular netlist.
- All grading is based on what is actually present/derivable from the
  submitted report and the reference netlist; no hidden gate names,
  trigger values, or vulnerability locations are disclosed by this
  harness or its output.