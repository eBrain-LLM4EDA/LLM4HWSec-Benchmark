# RTL Trojan Detection: Firmware Version Controller

## Objective

You are given the RTL source for `version_ctrl`, a firmware update controller
that maintains an 8-bit monotonic firmware version register. The intended
purpose of this register is to prevent installation of older, previously
patched (vulnerable) firmware images: once a higher version has been
accepted, the register should never be set back down.

Your task is to analyze `inputs/version_ctrl.v` and determine whether its
actual update logic always enforces this anti-rollback property, or whether
there exist conditions — internal state, signal sequences, timing windows,
etc. — under which the version register can be driven to a value other than
`max(current version, candidate version)`.

Produce an analysis report identifying:

- How the version register is actually updated on each accepted request.
- Any internal state tracking (registers, counters, small state machines)
  that influences this update beyond the documented comparison logic.
- Any specific sequence of inputs, signal values, or timing conditions that
  causes a non-monotonic (or otherwise unexpected) update to the version
  register.
- A ranked list of candidate anomalies with supporting rationale, referencing
  the actual signal/register names in the RTL.

You do not need to find a "backdoor" in the colloquial sense — your job is to
determine whether the update logic matches its documented specification
(strict monotonic max-based versioning) in all cases, and to report precisely
where and how it deviates, if it does.

## Interface Under Analysis

Module: `version_ctrl`, defined in `inputs/version_ctrl.v`.

| Port | Direction | Width | Description |
|---|---|---|---|
| `clk` | input | 1 | System clock, rising-edge sequential logic |
| `rst_n` | input | 1 | Active-low asynchronous reset |
| `req_valid` | input | 1 | Asserted for one cycle to present a candidate update request |
| `candidate_version` | input | 8 | Candidate firmware version presented alongside `req_valid` |
| `req_accept` | input | 1 | Indicates the request passed signature/authenticity checks; only accepted requests may affect state |
| `version_q` | output reg | 8 | Current, publicly observable committed firmware version register |
| `update_ack` | output wire | 1 | Asserted for one cycle, one cycle after an accepted request is processed |

All ports are public. There are no secret-bearing signals in this module.

You must **not** modify `inputs/version_ctrl.v`. Your deliverable is a report,
not a patched RTL file.

## Reference Materials

- `inputs/version_ctrl.v` — the RTL implementation under review.
- `inputs/design_brief.md` — the module's intended functional behavior, as
  documented by its original authors.

## Available Toolchain

You may (optionally) use the following tools locally to explore, simulate,
or elaborate the design while forming your analysis. Their use is not
required, and no tool output is submitted directly — only your final report
is graded.

- `iverilog` / `vvp` — for compiling and simulating `version_ctrl.v` against
  your own testbenches, e.g. to confirm a suspected trigger sequence produces
  the anomalous update you describe.
- `yosys` — for structural/synthesis-level inspection of the design if you
  prefer a netlist-level view of the state logic.

Any testbenches or scripts you write for your own exploration are not part of
the graded deliverable and do not need to be submitted.

## Deliverable

Submit your findings as a single JSON file at:

```
submission/trojan_report.json
```

This file must be valid JSON with exactly the following top-level fields:

- `candidates` (array): a list of candidate anomaly findings.
- `summary` (string): a short prose summary of your overall findings.
- `tool_version` (string): a free-form identifier for your analysis
  tool/process version.

Each entry in `candidates` must be an object with the following fields:

- `id` (string): a short identifier for the candidate finding.
- `description` (string): what the anomaly is, in plain terms.
- `confidence` (number, 0 to 1): your confidence that this candidate
  represents a real deviation from correct monotonic anti-rollback behavior.
- `trigger_condition` (string): the precise condition(s) — signal values,
  input sequence, state values — required to activate this behavior.
- `payload_effect` (string): the precise effect on `version_q` (or other
  observable state) when the trigger condition is met, described concretely
  (i.e., what is `version_q` actually set to, not just "an incorrect value").

Be as specific as possible. Vague descriptions such as "possible anomaly in
update logic" or "state machine looks suspicious" without naming the actual
signals, the actual triggering values, and the actual resulting expression
will not be considered a substantiated finding. Precision matters more than
volume — a report with many low-value, unsubstantiated candidates is scored
worse than a report with one well-supported, correctly localized finding.

A **placeholder** `submission/trojan_report.json` is already provided in this
repository. It is intentionally empty/generic and does not represent a real
analysis — you are expected to replace its contents entirely with your own
findings before submitting.

## Notes

- Focus your analysis on whether `version_q` can ever be set to something
  other than `max(version_q, candidate_version)` on an accepted request, and
  under exactly what conditions.
- Pay attention to any internal state that persists across multiple accepted
  requests, not just the values present on a single request.
- Your report is evaluated on the substance and precision of its top-ranked
  finding(s), not on the total number of candidates submitted.