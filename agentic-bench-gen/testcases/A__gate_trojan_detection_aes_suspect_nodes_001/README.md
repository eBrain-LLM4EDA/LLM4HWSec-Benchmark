# Gate-Level Trojan Suspect-Node Localization — AES-like Netlist

## Overview

You are given a small gate-level Verilog netlist, a design brief, and a port map
describing a synthesized combinational datapath block, `aes_sub_datapath`. This
block was delivered as a flattened gate-level netlist from a third-party vendor
for integration into a larger AES-like pipeline.

Your job is to review the netlist structurally and functionally, decide whether
it appears to be infected with a hardware Trojan, and, if so, identify the
specific gate/wire instance names that form the suspicious trigger and payload
logic. You will produce a single JSON analysis report.

## Inputs (read-only)

All input artifacts live under `inputs/` and **must not be modified**:

- `inputs/aes_sub_netlist.v` — the gate-level netlist for module `aes_sub_datapath`,
  built entirely from simple gate primitives (`and`, `or`, `xor`, `not`, `nand`,
  `nor`) and continuous `assign` statements. No proprietary or encrypted cells.
- `inputs/design_brief.md` — a short engineering description of the block's
  intended function and its ports.
- `inputs/port_map.json` — the exact port list (name, direction, width) for
  `aes_sub_datapath`, matching the netlist.

The netlist and design brief are self-contained: everything you need to reason
about intended behavior versus actual structure is in these three files. You
are welcome to use `yosys`, `iverilog`, and `vvp` (all available in the
environment) to synthesize, elaborate, or simulate the netlist as a
cross-check, but this is optional — you can complete the analysis purely by
reading the netlist.

## What to submit

Write your analysis to:

```
submission/trojan_report.json
```

Do not edit anything under `inputs/`. Only the contents of
`submission/trojan_report.json` are graded.

The file must be a single JSON object (not wrapped in an array) with **at
least** the following top-level keys:

| Key                        | Type              | Requirement |
|----------------------------|-------------------|-------------|
| `infected`                 | boolean           | `true` if you conclude the netlist contains a Trojan, `false` otherwise. |
| `suspect_nodes`             | array of strings | Exact gate/wire **instance names** as they appear in `inputs/aes_sub_netlist.v`. |
| `rationale`                 | string            | Non-empty explanation of *why* you reached your conclusion. |
| `primary_output_affected`   | string            | The name of the primary output port (from `inputs/port_map.json`) that your reported payload logic drives, or `""` if `infected` is `false`. |

Extra keys are permitted and will be ignored by the grader.

### Functional constraints your report must satisfy

1. **Valid JSON, correct top-level shape.** `infected` must be a boolean,
   `suspect_nodes` must be an array of strings, and `rationale` must be a
   non-empty string.
2. **Every suspect node must be real.** Each string in `suspect_nodes` must
   correspond to an actual instance name declared in
   `inputs/aes_sub_netlist.v` — i.e. it must match (as a substring/exact
   identifier) a gate or module instantiation identifier that really appears
   in that file. Do not invent instance names.
3. **Consistency between `infected` and `suspect_nodes`.** If `infected` is
   `true`, `suspect_nodes` must contain at least 2 entries. If `infected` is
   `false`, `suspect_nodes` must be an empty array.
4. **`primary_output_affected` must be a real port.** It must exactly match
   one of the output port names listed in `inputs/port_map.json`, or be the
   empty string `""` if `infected` is `false`.

Your rationale should reference the actual instance names / signal names you
identify and explain, in concrete terms, what structural or functional
property led you to flag them (e.g. an unusual gating condition that is only
satisfied for a rare combination of internal bits, an extra gate spliced onto
an output path that has no role in the block's documented function, etc.).
Generic or boilerplate rationales that don't engage with the specific netlist
will not be considered a satisfactory analysis.

## Suggested workflow

1. Read `inputs/design_brief.md` to understand the intended function of
   `aes_sub_datapath` and its ports (cross-reference `inputs/port_map.json`).
2. Read `inputs/aes_sub_netlist.v` and trace, gate by gate, how each primary
   output bit is produced from the primary inputs.
3. Look for logic that doesn't fit the documented function: gates that only
   rarely evaluate to a meaningful value, extra gates spliced onto an output
   path, or wires that combine many unrelated internal signals in a way that
   has no obvious role in the intended datapath behavior.
4. Optionally, use `iverilog`/`vvp` to simulate the netlist over a range of
   input vectors (including rare/edge-case bit patterns) to see whether any
   output deviates from what the design brief describes, or use `yosys` to
   inspect the synthesized structure.
5. Write your conclusions to `submission/trojan_report.json`.

## Example skeleton (structure only — not a real answer)

This example illustrates the **shape** of a valid submission. The values
below are placeholders and are not the correct answer for this netlist.

```json
{
  "infected": true,
  "suspect_nodes": ["instance_name_1", "instance_name_2"],
  "rationale": "Explain here, referencing specific instance/signal names, why the flagged gates form a rare-condition trigger and payload that deviates from the documented function.",
  "primary_output_affected": "some_output_port_name"
}
```

A starter (intentionally naive) `submission/trojan_report.json` is already
present in this repository. It is not a correct analysis — replace it with
your own findings before submitting.