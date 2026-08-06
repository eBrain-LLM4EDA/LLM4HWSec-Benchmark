# Gate-Level Trojan Detection: Evaluation Guide

## What you submit

A single file: `submission/trojan_report.json`

This is an **answer file**, not code. You do not modify anything under
`inputs/`. `evaluate.py` reads the input artifacts (`inputs/netlist.v`,
`inputs/design_brief.md`, `inputs/baseline_testbench.v`) for reference and
grades the content of your submitted JSON report.

## Required schema

Your `trojan_report.json` must be valid UTF-8 JSON with exactly these
top-level fields:

```json
{
  "design_name": "string",
  "is_trojan_detected": true,
  "suspect_nodes": ["net_name_1", "net_name_2"],
  "stage_labels": {
    "net_name_1": "counter",
    "net_name_2": "payload"
  },
  "summary": "A description of your analysis method, at least 20 characters long."
}
```

### Field requirements (FR1-FR4)

- **FR1 — Schema.** The report must be valid JSON with all four top-level
  fields present and correctly typed:
  - `design_name`: a string.
  - `is_trojan_detected`: a boolean (`true` or `false`).
  - `suspect_nodes`: an array of strings, where each string is an exact
    net/wire/gate-output name as it appears in `inputs/netlist.v`.
  - `stage_labels`: an object mapping net/wire names to a role. Each value
    must be exactly one of the following role strings:
    - `"counter"`
    - `"comparator"`
    - `"payload"`
    - `"datapath"`
    - `"io"`
  - `summary`: a non-empty string, at least 20 characters, describing your
    overall analysis method.

- **FR2 — Design name.** `design_name` must exactly match the module name
  declared in `inputs/netlist.v` (i.e. the identifier following the
  `module` keyword in the file's header).

- **FR3 — Valid node references.** Every entry in `suspect_nodes` and every
  key in `stage_labels` must be a real identifier found in
  `inputs/netlist.v` — that is, a name declared as an `input`, `output`,
  `wire`, or `reg`, or produced as the output of a gate instantiation or an
  `assign` statement. Bit-selected references (e.g. `foo[2]`) are matched
  against their base signal name (`foo`) if the base name is declared.
  Names that do not correspond to anything in the netlist will cause this
  check to fail.

- **FR4 — Summary.** The `summary` field must be present, must be a
  string, and must be at least 20 characters long.

## How grading works

`evaluate.py` is the sole entry point:

1. It first confirms `inputs/netlist.v` is present and readable (an
   infrastructure precondition — if missing, this is a setup failure
   outside your control).
2. It then requires `submission/trojan_report.json` to exist. A missing
   submission file fails immediately.
3. It parses your JSON and checks FR1-FR4 as described above.
4. It additionally checks a set of security requirements (SR1-SR4) that
   assess whether your report substantively and accurately identifies the
   design's true trigger/payload logic versus its legitimate documented
   datapath logic, and whether your report avoids excessive false-positive
   flagging of legitimate nodes. The specific hidden ground-truth node set,
   the coverage threshold, and the false-positive-rate threshold used for
   this substantive grading are **not** disclosed in this document — they
   are derived from a private ground-truth annotation of `inputs/netlist.v`
   that is not shipped to participants. Your job is to analyze the netlist
   and `inputs/design_brief.md` (the documented functional specification)
   carefully and report your genuine findings; do not attempt to reverse
   engineer grading internals.
5. For every requirement checked, `evaluate.py` prints exactly one line of
   the form:
   - `[TEST] PASS: <requirement_id>` or
   - `[TEST] FAIL: <requirement_id>: <reason>`
6. The process exits with code `0` only if every requirement passes;
   otherwise it exits non-zero.

## A note on style

Grading is based on the *substance* of your report content (which nodes
you name, how you label their roles, whether your conclusion is correct)
and on structural validity of the JSON — never on cosmetic conventions.
Any naming style, key ordering, or level of verbosity in your `summary`
is acceptable as long as the schema and substantive checks are satisfied.

## Toolchain availability

The grading environment has `yosys`, `iverilog`, and `vvp` available.
These tools may be used by `evaluate.py` for optional cross-checks against
`inputs/netlist.v` and `inputs/baseline_testbench.v` (for example,
simulating the netlist to confirm that a reported trigger condition
actually manifests in behavior). However, **PASS/FAIL verdicts are
determined by grading the content of your submitted
`submission/trojan_report.json`**, not by any side simulation outcome.