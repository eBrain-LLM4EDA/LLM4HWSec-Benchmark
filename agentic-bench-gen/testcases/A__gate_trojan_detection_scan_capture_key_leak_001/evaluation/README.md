# Gate-Level Trojan Detection: `key_core` Scan Chain Analysis

## Objective

Analyze the supplied gate-level netlist of `key_core`, a small key-storage
block with an integrated manufacturing-test scan chain. Determine whether
any flip-flops in the design are reachable on the scan-observable path
(`scan_out`) during scan-mode shift/capture in a way that is inconsistent
with the design's intended functional isolation, and identify the specific
multiplexer instances responsible for establishing that reachability.

Refer to `inputs/design_brief.md` for the intended functional/test-mode
behavior and confidentiality expectations of the design, `inputs/key_core_netlist.v`
for the structural netlist itself, and `inputs/scan_chain_order.txt` for the
documented scan-chain element ordering.

## What you submit

A single file:

```
submission/trojan_report.json
```

Do not modify anything under `inputs/`. Only the submission file above is
graded.

## Required schema

`submission/trojan_report.json` must be valid UTF-8 JSON (no trailing
comments) containing exactly the following top-level fields:

```json
{
  "trojan_detected": true,
  "suspect_flops": ["<instance_name>", "..."],
  "suspect_muxes": ["<instance_name>", "..."],
  "confidence": 0.0,
  "rationale": "<free text>"
}
```

Field requirements:

- **`trojan_detected`** — boolean. Must be JSON `true` or `false` (not a
  string, not `0`/`1`).
- **`suspect_flops`** — array of strings. Each string must be the exact
  instance name of a flip-flop cell as it appears in
  `inputs/key_core_netlist.v` that you judge to be scan-observable in a
  way inconsistent with normal isolated operation.
- **`suspect_muxes`** — array of strings. Each string must be the exact
  instance name of a multiplexer/gating cell in
  `inputs/key_core_netlist.v` that you judge is responsible for splicing
  those flops onto the scan path.
- **`confidence`** — a number in the inclusive range `[0.0, 1.0]`.
- **`rationale`** — a non-empty string of at least 20 characters
  explaining the reasoning behind the reported findings.

Field names, casing, and types above are exact and mandatory.
Unrecognized extra top-level fields are ignored by the grader.

## Instance name grounding

Every entry listed in `suspect_flops` and `suspect_muxes` must correspond
to an actual instance name that appears in `inputs/key_core_netlist.v`.
Fabricated, misspelled, or nonexistent instance names will cause the
submission to fail structural validation, regardless of how plausible
they sound. Matching is case-insensitive, but the instance must genuinely
exist in the netlist text.

## How the report is graded

The grader (`evaluation/evaluate.py`) performs two categories of checks:

1. **Structural/format checks** — is the JSON well-formed, are all five
   required fields present with the correct types, do all listed
   instance names actually exist in the netlist, is `confidence` in
   range, and is `rationale` long enough to be substantive.

2. **Substantive correctness checks** — your findings are compared
   against a hidden ground truth derived from the actual netlist
   structure:
   - `suspect_flops` must correctly identify at least 3 of the 4 true
     scan-observable key-holding flip-flops.
   - `suspect_muxes` must correctly identify at least 3 of the 4 true
     multiplexer instances that splice those flops onto the scan chain.
   - `trojan_detected` must be reported as `true` for this netlist.
   - `rationale` must demonstrate that the identified leak is
     specifically tied to scan-mode operation. Concretely, the
     rationale must assert that the exposure is **conditional on
     `scan_en` being asserted** — i.e. that the leak path is absent or
     inactive during normal functional operation (`scan_en=0`) and
     only becomes observable when scan mode is active (referencing
     `scan_en`, scan mode, capture, or shift). A rationale that is only
     generic boilerplate (e.g. simply stating no issue was found, or a
     template sentence with no scan-mode-specific reasoning) will not
     satisfy this check.

     Additionally, the rationale must **not** characterize the leak as
     a **permanent, always-on, or constant wiring/connectivity defect
     that is independent of any control signal** (for example,
     describing the key flops as "always" reachable at `scan_out`,
     "stuck" onto the scan path, or exposed "regardless of any control
     signal" or "unrelated to any test-mode signal"). Such phrasing
     mischaracterizes the mechanism as a static bug rather than a
     scan-mode-gated exposure, and will cause this check to fail **even
     if** scan-mode keywords (`scan_en`, `capture`, `shift`, etc.) also
     appear elsewhere in the same rationale — the two claims are
     contradictory, and the grader treats a rationale that makes both
     claims as not substantively correct.

A submission that reports no findings (`trojan_detected: false`, empty
`suspect_flops`/`suspect_muxes`, and a generic rationale) is expected to
fail grading — this design does contain a scan-related exposure that a
correct analysis should identify.

## Optional toolchain cross-check

`evaluate.py` may optionally invoke `iverilog`/`vvp` to simulate
`inputs/key_core_netlist.v` (driving `scan_en`, `scan_in`, and observing
`scan_out` per the ordering in `inputs/scan_chain_order.txt`) purely as an
internal cross-check used by the evaluator to corroborate its own ground
truth. This simulation does not read or depend on your submission file in
any way, is not required for your submission to pass, and its
availability or absence on the grading machine does not affect how your
submission is scored.

## Reminders

- Do not edit any file under `inputs/`.
- Base your findings on static/behavioral analysis of the provided
  netlist and design brief, optionally corroborated by your own
  simulation using the available toolchain (`yosys`, `iverilog`, `vvp`)
  against the provided artifacts.
- Only `submission/trojan_report.json` is read by the grader as your
  answer; no other submission files are considered.