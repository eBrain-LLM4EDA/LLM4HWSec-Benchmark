# Gate-Level Clocking Discipline Audit — access_ctrl_top

## Overview

You are given a synthesized gate-level Verilog netlist for an access-control
module, `access_ctrl_top`, along with the design document that specifies its
intended behavior and its cell library. Your task is to audit the netlist
against the design brief and report any structural deviation from the
documented clocking discipline.

## Module under review

`access_ctrl_top` is a single-clock module with the following ports:

| Port        | Direction | Width | Description                                   |
|-------------|-----------|-------|------------------------------------------------|
| `clk`       | input     | 1     | System clock                                   |
| `rst_n`     | input     | 1     | Asynchronous active-low reset                  |
| `key_in`    | input     | 8     | Candidate access key                           |
| `req_valid` | input     | 1     | Access request strobe                          |
| `grant_out` | output    | 1     | Registered access-grant signal                 |

The module compares `key_in` against an internal reference value to derive
an internal permission signal, pipelines it through a small number of
flip-flops, and combines it with the request strobe to produce `grant_out`.

## Provided input artifacts (do not modify)

All files under `inputs/` are read-only reference material. **Do not modify
anything under `inputs/`.** Your analysis and answer must be produced as a
separate file under `submission/`.

- `inputs/access_ctrl_netlist.v` — the flat, gate-level netlist of
  `access_ctrl_top`, built entirely from primitives declared in
  `cell_library.v`.
- `inputs/cell_library.v` — the primitive cell library: two flip-flop
  primitives, `DFF_POSEDGE` and `DFF_NEGEDGE` (both with ports `.clk`, `.d`,
  `.q`, `.rst_n`), and standard combinational gates (`AND2`, `OR2`, `NAND2`,
  `NOR2`, `XOR2`, `INV`, `MUX2`).
- `inputs/design_brief.md` — the design specification. It documents the
  intended clocking discipline and signal flow for the module, and lists the
  state elements the designer expects the netlist to contain.
- `inputs/testbench_stub.v` — a standalone simulation testbench that
  instantiates `access_ctrl_top`, generates a clock and reset, drives a
  handful of representative stimulus vectors on `key_in`/`req_valid`, and
  dumps internal signals for observation. This is provided for reference; you
  are not required to run it, but you may use `iverilog`/`vvp` if you want to
  simulate the design while investigating.

## Your objective

The design brief states a single, simple clocking discipline: **every
state-holding element in this design is triggered on the positive edge of
`clk` (instantiated as `DFF_POSEDGE` from `cell_library.v`)**, with
asynchronous active-low reset.

Your job is to:

1. Enumerate every sequential (flip-flop) instance in
   `inputs/access_ctrl_netlist.v`.
2. Determine which cell type (`DFF_POSEDGE` or `DFF_NEGEDGE`) each instance
   actually uses.
3. Compare this against the clocking discipline documented in
   `inputs/design_brief.md`.
4. Identify any instance whose actual cell type does not match the
   documented discipline, and identify the net that instance samples on its
   `.d` port.
5. Report your findings.

You should treat this as a structural/static analysis task: read the
netlist text carefully, cross-reference it against the cell library and the
design brief, and do not assume that instance or signal names alone tell you
the whole story — verify against the actual cell type used in each
instantiation.

## Expected output

Write your findings to:

```
submission/trojan_report.json
```

This file must be a single JSON object with exactly these top-level fields:

```json
{
  "trojan_detected": <boolean>,
  "suspect_instances": [
    {
      "instance_name": "<exact instance identifier as it appears in the netlist>",
      "cell_type": "<exact primitive name, e.g. DFF_NEGEDGE>",
      "sampled_signal": "<exact net name driving that instance's .d port>",
      "justification": "<free text explaining why this instance is flagged>"
    }
  ],
  "summary": "<free text overview of the finding, at least 20 characters>"
}
```

### Structural requirements checked on your submission

- **FR1 — Valid schema.** The file must be valid JSON containing exactly the
  top-level fields `trojan_detected` (boolean), `suspect_instances` (array),
  and `summary` (string). Missing or mistyped fields will fail this check.
- **FR2 — Verbatim references.** Every `instance_name`, `cell_type`, and
  `sampled_signal` value inside each `suspect_instances` entry must be a
  non-empty string, and must exactly match an identifier that actually
  appears in `inputs/access_ctrl_netlist.v`. Do not paraphrase or guess
  identifier spellings.
- **FR3 — Internal consistency.** If `trojan_detected` is `true`,
  `suspect_instances` must contain at least one entry. If `trojan_detected`
  is `false`, `suspect_instances` must be an empty array. A report that
  contradicts itself (e.g. claims no trojan but lists suspects, or vice
  versa) will fail this check.
- **FR4 — Summary length.** `summary` must be a non-empty string of at least
  20 characters that describes the finding in prose.

Beyond these structural rules, your submission is graded on whether the
content you report is actually correct — i.e. whether you identified the
right instance, the right (unexpected) cell type, and the right sampled
signal, with a coherent justification. A structurally valid but empty or
generic report (for example, one that simply says nothing was found) will
not be considered a correct finding.

## Workflow

1. Read `inputs/design_brief.md` to understand the intended clocking
   discipline and expected state elements.
2. Read `inputs/cell_library.v` to understand the two flip-flop primitives
   and how they differ.
3. Read `inputs/access_ctrl_netlist.v` line by line and note the cell type
   used for every sequential instance.
4. Cross-check each instance's actual cell type against the documented
   discipline.
5. For any mismatch, note the instance name, its actual cell type, and the
   net connected to its `.d` port.
6. Write your conclusions to `submission/trojan_report.json` following the
   schema above.

Good luck.