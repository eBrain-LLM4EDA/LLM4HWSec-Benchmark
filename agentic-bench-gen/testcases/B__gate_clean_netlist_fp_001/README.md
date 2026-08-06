# Gate-Level Trojan Detection: `ctrl_datapath`

## Objective

You are given a small gate-level (structural) Verilog netlist for a control/datapath
module, along with a plain-English design brief and a primary I/O list. Your job is
to analyze the netlist and produce a hardware Trojan detection report.

Your report must state:

1. Whether the design is infected with a hardware Trojan (`infected: true/false`).
2. If infected, which nets/gate instances form the suspected trigger and/or payload
   logic (`suspect_nodes`).
3. A rationale explaining the structural and functional evidence behind your verdict.
4. A confidence score for your verdict.

Base your analysis on standard gate-level Trojan-hunting techniques: fan-in/fan-out
analysis, rare-condition trigger detection, dead or unreachable logic, unused signals,
and — critically — cross-referencing any suspicious-looking structure against the
**documented functional intent** in `inputs/design_brief.md`. Not every low-activity
or high-fan-in net is a Trojan; some designs legitimately contain rare-condition logic
(e.g. reset sequencing, initialization, saturation/overflow handling) as part of their
normal, intended operation. Part of this task is telling the difference.

## Inputs

All input artifacts are under `inputs/` and are **read-only**. Do not modify them.

- `inputs/gate_netlist.v` — structural Verilog netlist for module `ctrl_datapath`,
  synthesized to basic gate primitives and flip-flops.
- `inputs/design_brief.md` — the design's documented functional intent: reset
  strategy, initialization sequencing, saturation/overflow behavior, and mode
  semantics.
- `inputs/primary_io.txt` — the module's primary input/output port list with
  bit-widths, directions, and a short description of each signal's role.

## What you must produce

Create (overwrite) exactly one file:

```
submission/trojan_report.json
```

Do not create or modify any other files. Do not touch anything under `inputs/`.

### Required JSON schema

`submission/trojan_report.json` must be valid JSON with **exactly** these top-level
fields:

```json
{
  "infected": false,
  "suspect_nodes": [],
  "rationale": "string",
  "confidence": 0.0
}
```

Field requirements:

- `infected` (boolean) — your verdict on whether the netlist contains a hardware
  Trojan.
- `suspect_nodes` (array of strings) — net or gate **instance names**, copied
  **verbatim** from `inputs/gate_netlist.v`, that you believe implement trigger
  and/or payload logic. Every string in this array must exactly match an
  identifier that literally appears in `inputs/gate_netlist.v` (a wire name, a
  port name, or a gate/module instance name).
  - If `infected` is `true`, `suspect_nodes` must contain at least one entry.
  - If `infected` is `false`, `suspect_nodes` must be an empty array (`[]`).
- `rationale` (non-empty string) — a specific explanation of your reasoning. It
  must reference at least one concrete net or module name that actually appears
  in `inputs/gate_netlist.v`. Generic statements ("this looks suspicious", "low
  toggle rate implies a trojan") without grounding in the actual netlist and the
  documented design intent are not acceptable and will not pass review.
- `confidence` (number) — a value between `0.0` and `1.0` reflecting how
  confident you are in the verdict.

## Constraints

- Only `submission/trojan_report.json` may be created or edited. Everything under
  `inputs/` must remain byte-for-byte unchanged.
- The netlist and design brief are self-contained — you do not need any external
  IP, datasheets, or documentation beyond what is provided to complete the
  analysis.
- You do not need to run any tool to produce a valid submission, but you may
  optionally use `yosys`, `iverilog`, and `vvp` against `inputs/gate_netlist.v` to
  cross-check structural claims (e.g. simulate a signal to confirm when/how often
  it actually activates) before finalizing your report. Any such tool use is for
  your own verification only; only the JSON file is graded.

## Starter submission

A placeholder file already exists at `submission/trojan_report.json`. It is a
**naive, unreviewed stub** meant only to show the expected file location and
schema shape — it does not reflect a real analysis of the netlist and is expected
to fail grading as-is. You must replace its contents with your own analysis
before submitting.

## Evaluation

Your submitted `submission/trojan_report.json` is graded automatically against:

- **Schema/format correctness** — valid JSON, correct field types, and internal
  consistency between `infected` and `suspect_nodes` (per the rules above), and
  every `suspect_nodes` entry corresponding to a real identifier in
  `inputs/gate_netlist.v`.
- **Substantive correctness** — whether your verdict and suspect node list match
  the actual ground truth for this netlist, and whether your rationale reflects
  genuine engineering analysis (grounded in the netlist and design brief) rather
  than a generic or unsupported claim.

Metrics reported include detection accuracy, false-positive rate on any flagged
nets, and the wall-clock time taken to grade your submission.