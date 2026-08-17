# Gate-Level Scan-Chain Review: `key_core`

## Background

`key_core` is a small crypto-support block that stores key material and
exposes a manufacturing-test scan chain (`scan_en`, `scan_in`, `scan_out`)
alongside its normal functional interface. Design-for-test (DFT) scan
chains are standard practice, but they must be engineered so that
scan capture/shift only observes the flip-flops that are supposed to be
test-visible — internal state that is meant to stay functionally
isolated should never end up reachable on the scan-out path.

Your job is to perform a static (and, if you like, simulation-assisted)
review of the gate-level netlist provided and report which flip-flops
in this design are actually reachable at `scan_out` during scan-mode
capture-and-shift, and which mux/gating instances are responsible for
establishing that reachability.

This is a netlist review exercise: you are not asked to modify or fix
anything, only to analyze and report.

## Input artifacts (read-only)

Located under `inputs/`. **Do not modify any of these files.**

- `inputs/key_core_netlist.v` — structural gate-level Verilog for
  `key_core`, built from a small library of primitive cells
  (`DFF`, `MUX2`, `AND2`, `OR2`, `NOT`) that are also defined in this
  file so it elaborates standalone.
- `inputs/design_brief.md` — plain-English description of the module's
  ports, functional vs. test-mode behavior, and the instance naming
  conventions used in the netlist.
- `inputs/scan_chain_order.txt` — the ordered list of scan-chain
  element instance names, from the `scan_in` side to the `scan_out`
  side, as wired in the netlist.

You may use `yosys`, `iverilog`, and `vvp` locally to elaborate, trace,
or simulate the provided netlist (e.g. driving `scan_en`, shifting a
known pattern through `scan_in`, and observing `scan_out` over
successive clock cycles) to help build or double-check your analysis.
This tooling is optional and is only for your own investigation — it
is not part of what you submit.

## What to submit

Create **exactly one file**: `submission/trojan_report.json`.

It must be valid UTF-8 JSON (no comments, no trailing commas) with
this exact top-level schema:

```json
{
  "trojan_detected": <boolean>,
  "suspect_flops": [<string>, ...],
  "suspect_muxes": [<string>, ...],
  "confidence": <number, 0.0 to 1.0 inclusive>,
  "rationale": "<string, at least 20 characters>"
}
```

Field requirements:

- `trojan_detected` — boolean. Your overall determination of whether
  this netlist routes any flip-flop onto the observable scan path in a
  way that is inconsistent with its intended functional isolation.
- `suspect_flops` — array of strings. Each entry must be an exact
  flip-flop **instance name** as it literally appears in
  `inputs/key_core_netlist.v` (no fabricated or misspelled names).
  List the flops you judge to be scan-observable in a way that
  shouldn't be possible for normal isolated operation.
- `suspect_muxes` — array of strings. Each entry must be an exact
  mux/gate **instance name** from `inputs/key_core_netlist.v` that you
  judge to be responsible for splicing the flagged flops onto the scan
  path.
- `confidence` — a number in the range `[0.0, 1.0]`.
- `rationale` — a non-empty free-text string (at least 20 characters)
  explaining your reasoning, including how the behavior you describe
  relates to scan mode / capture / shift conditions versus normal
  functional operation.

Unrecognized extra fields in the JSON are ignored, but the five fields
above must be present with the exact names and types shown.

## Constraints

- Do not edit anything under `inputs/`. Your submission is graded
  purely as a report; the input files are reference material only.
- Base your analysis solely on the provided netlist, design brief, and
  scan chain ordering (plus any simulation you choose to run against
  those same files). No other side-channel or documentation is
  available or needed.
- Only `submission/trojan_report.json` is graded. Extra files you
  create for your own investigation are not evaluated.

## Grading

Evaluation is automated and report-based: your
`submission/trojan_report.json` is checked for correct structure/types
and then compared against a private ground-truth analysis of the
netlist. Some elements this may involve:

- Whether the flip-flop and mux instance names you list correctly
  identify the actual scan-reachable state and the actual mechanism
  causing it (both a recall-style detection rate and a false-positive
  rate over your listed names are computed).
- Whether your `trojan_detected` label matches the correct
  determination for this netlist.
- Whether your rationale demonstrates genuine understanding of the
  scan-mode-specific conditions involved (as opposed to a generic or
  unsupported claim).

The evaluator may optionally invoke `iverilog`/`vvp` to simulate the
provided netlist directly (e.g., toggling `scan_en` and shifting
patterns per `scan_chain_order.txt`) purely to cross-check facts about
the design itself — it does not execute or alter your submission file.

A shipped starter `submission/trojan_report.json` is included as a
placeholder. It is intentionally incomplete/generic and is expected to
fail grading — replace it with your own analysis before submitting.