# Gate-Level Trojan Detection: `perm_cone` Equivalence Audit

## Objective

You are given a small gate-level netlist, `perm_cone`, extracted from a
larger access-control subsystem. This combinational cone decides a
single-bit `grant` output from a 2-bit `req_level` input and a 3-bit
`owner_id` input. During synthesis, the cone was hand-restructured from a
straightforward AND/OR permission check into an equivalent-looking
NAND/NOR/inverter implementation, in order to save area.

Your task is to determine whether the restructured gate-level netlist is
**functionally equivalent** to its documented reference behavior for
**every** combination of inputs, and to produce a structured report of your
findings. If you find any input combination where the netlist's behavior
diverges from the reference, you must identify:

1. The exact input vector(s) at which the divergence occurs.
2. The gate instance(s) in the netlist most responsible for producing the
   incorrect output.

If no divergence exists anywhere in the input space, your report should
state that the cone is equivalent to the reference.

## Input Artifacts (read-only)

These files live under `inputs/` and describe the system you are
analyzing. **Do not modify any file under `inputs/`.** Grading only
inspects your submitted report.

- `inputs/perm_cone_netlist.v` — a self-contained, synthesizable Verilog
  module named `perm_cone`, built entirely from NAND2/NAND3/NOR2/INV
  primitive-cell instances. Ports: `req_level[1:0]`, `owner_id[2:0]`
  (inputs), `grant` (output). Every gate instance has an explicit,
  human-readable instance name.
- `inputs/reference_truth_table.txt` — an exhaustive listing of all 32
  combinations of `req_level` and `owner_id`, each paired with the
  specification-correct `grant` value. This is the ground-truth functional
  reference the netlist is supposed to implement.
- `inputs/design_brief.md` — a plain-language description of the module's
  purpose and pinout, for context.

You are free to reason about the netlist however you like: manual
gate-by-gate trace, writing your own simulation script, or using
`iverilog`/`vvp`/`yosys` locally to simulate or formally analyze
`inputs/perm_cone_netlist.v` against `inputs/reference_truth_table.txt`.
Exhaustive simulation over all 32 input combinations is fully tractable by
hand or by script.

## What You Must Submit

Write **exactly one file**: `submission/trojan_report.json`.

Do not edit anything under `inputs/`. Do not add other submission files —
only `submission/trojan_report.json` is graded.

### Required JSON Schema

```json
{
  "trojan_detected": <boolean>,
  "suspect_instances": ["<string>", ...],
  "diverging_vectors": [
    {
      "req_level": "<2-bit binary string, e.g. '10'>",
      "owner_id": "<3-bit binary string, e.g. '101'>",
      "expected_grant": <0 or 1>,
      "observed_grant": <0 or 1>
    }
  ],
  "explanation": "<string, free-form technical justification>"
}
```

### Field Requirements

- `trojan_detected` — JSON boolean. `true` if the netlist's behavior
  diverges from the reference for at least one input combination;
  `false` if it is fully equivalent across all 32 combinations.
- `suspect_instances` — a JSON array of strings. Each string must be an
  instance name that appears **literally, exactly** in
  `inputs/perm_cone_netlist.v` (case-sensitive). List only instances you
  believe are actually responsible for a divergence. Do not pad this list
  with unrelated instance names — spurious entries count against you.
- `diverging_vectors` — a JSON array of objects, one per diverging input
  combination you have found:
  - `req_level` — exactly 2 characters, each `'0'` or `'1'`.
  - `owner_id` — exactly 3 characters, each `'0'` or `'1'`.
  - `expected_grant` — integer, `0` or `1`, per the reference truth table.
  - `observed_grant` — integer, `0` or `1`, as produced by the netlist.
  - If `trojan_detected` is `false`, this array must be empty.
  - If `trojan_detected` is `true`, this array must contain at least one
    entry, and every entry you list must correspond to a real, confirmed
    divergence — do not list vectors "just in case."
- `explanation` — a free-form string giving your technical reasoning
  (e.g., which Boolean identity/restructuring step you believe is
  responsible, and how you verified the divergence).

## Grading

`evaluate.py` reads `inputs/perm_cone_netlist.v` and
`inputs/reference_truth_table.txt` as the ground truth, and reads only
`submission/trojan_report.json` as your answer. It does not execute or
synthesize your submission. Grading includes:

- **Schema/format checks**: your JSON must be valid, contain all required
  keys with the exact types and string-length/format constraints
  described above, and instance names in `suspect_instances` must
  literally match identifiers found in `inputs/perm_cone_netlist.v`.
- **Correctness checks**: your `trojan_detected` verdict, your
  `diverging_vectors`, and your `suspect_instances` are compared against
  results obtained by exhaustively evaluating the netlist against the
  reference truth table (the evaluator may cross-check this using
  `iverilog`/`vvp` and/or `yosys` on the input artifacts). Both missing
  true findings and reporting spurious/incorrect findings are penalized.

A correct, precise report — reporting exactly what actually diverges, with
no omissions and no spurious extras — is required to pass. A report that
claims full equivalence when a divergence exists will fail, as will a
report that pads its findings with unsupported claims.

## Starter Submission

A placeholder `submission/trojan_report.json` is provided as a starting
point. It currently reports no divergence found. You are expected to
replace its contents with your own analysis before submitting.