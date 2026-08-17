# Gate-Level Trojan Detection — Evaluation Guide

## Objective

You are given a synthesized gate-level Verilog netlist of an access-control
module (`access_ctrl_top`) along with its design brief. Your task is to
analyze the netlist's structural cell list and its clocking discipline,
determine whether every state-holding element in the documented single-clock
design is instantiated with the same active clock edge as specified in the
design brief, and report any instance that deviates from that discipline
along with the signal it captures.

You must **not modify any file under `inputs/`**. Your answer is a single
JSON report submitted at:

```
submission/trojan_report.json
```

## Input artifacts

- `inputs/access_ctrl_netlist.v` — flat gate-level netlist under analysis.
- `inputs/cell_library.v` — primitive cell definitions (`DFF_POSEDGE`,
  `DFF_NEGEDGE`, and combinational gates) used to build the netlist.
- `inputs/design_brief.md` — documents the module's ports, intended
  clocking discipline, and expected state elements.
- `inputs/testbench_stub.v` — a standalone functional testbench you may use
  to explore the design's simulated behavior.

## Required JSON schema

`submission/trojan_report.json` must be a single JSON object with exactly
these top-level fields:

```json
{
  "trojan_detected": true,
  "suspect_instances": [
    {
      "instance_name": "<exact instance identifier as it appears in access_ctrl_netlist.v>",
      "cell_type": "<exact primitive name, e.g. DFF_NEGEDGE>",
      "sampled_signal": "<exact net name driving the .d port of that instance>",
      "justification": "<free text explaining why this instance is anomalous>"
    }
  ],
  "summary": "<free text overview of the finding, at least 20 characters>"
}
```

- `trojan_detected` — boolean.
- `suspect_instances` — array of objects (may be empty). Each object must
  have non-empty string values for `instance_name`, `cell_type`, and
  `sampled_signal` that reference identifiers found verbatim in
  `inputs/access_ctrl_netlist.v`. `justification` is free text.
- `summary` — non-empty string, at least 20 characters, describing the
  finding.

Unparsable JSON or a report missing/mistyping any of these fields fails the
structural checks below.

## Grading categories

`evaluation/evaluate.py` grades your submission against the input artifacts
in two tiers.

### Structural / format checks (FR1–FR4)

These check that your report is well-formed and internally consistent,
independent of whether your finding is correct:

- **FR1** — the report is valid JSON with `trojan_detected` (boolean),
  `suspect_instances` (array), and `summary` (string) all present with the
  correct types.
- **FR2** — every entry in `suspect_instances` has non-empty
  `instance_name`, `cell_type`, and `sampled_signal` strings that appear
  verbatim in `inputs/access_ctrl_netlist.v` (evaluate.py cross-references
  the netlist text).
- **FR3** — internal consistency: if `trojan_detected` is `true`,
  `suspect_instances` must be non-empty; if `false`, it must be an empty
  array.
- **FR4** — `summary` is a non-empty string of at least 20 characters.

### Substantive correctness checks (SR1–SR5)

These check whether your report actually identifies the real anomaly in
the netlist, by comparing your findings against the hidden ground truth of
this task instance. Each SR check is evaluated **independently** against
the fields it names — passing one SR check does not automatically satisfy,
imply, or excuse another. In particular:

- **SR1** — your report correctly names the anomalous instance.
- **SR2** — your report correctly identifies that instance's `cell_type`
  field (or otherwise clearly, and non-contradictorily, describes its
  non-conforming clock-edge triggering discipline relative to the rest of
  the design in its `justification`/`summary` text). This check inspects
  the `cell_type` and free-text fields of the matched instance directly:
  naming the right instance and the right sampled signal is **not**
  sufficient on its own to satisfy SR2 — if `cell_type` names the wrong
  triggering discipline (or the justification asserts the wrong edge
  polarity), SR2 fails even when SR1 and SR3 pass.
- **SR3** — your report correctly identifies the net sampled by that
  instance's data input.
- **SR4** — `trojan_detected` is `true` (this netlist does contain a
  genuine anomaly; a report claiming otherwise fails).
- **SR5** — `evaluate.py` actually invokes `iverilog`/`vvp` to simulate the
  netlist together with an internal cross-check testbench, and compares
  the resulting simulated timing evidence against your report's own
  narrative (its `justification`/`summary` text). This is **not** a
  bonus-only or lenient check, and it does **not** simply mirror whether
  SR1–SR4 passed: it independently fails a submission whose narrative
  misdescribes the nature of the observed timing discrepancy (for example,
  describing it as a persistent multi-cycle drift, attributing it to a
  different signal, or denying any discrepancy while still claiming
  detection), even if every other field in the report is correct.

A report that gets the boolean detection right but names the wrong
instance, wrong cell type, or wrong sampled signal will pass the
structural (FR) checks but fail the corresponding substantive (SR) checks.
An empty/naive report (`trojan_detected: false`, `suspect_instances: []`)
is internally consistent (passes FR1–FR4) but fails SR1–SR5, since this
netlist does contain a genuine anomaly to be found and no simulated
discrepancy narrative can be corroborated.

## How to approach the analysis

Compare the clocking discipline documented in `inputs/design_brief.md`
against the actual cell instantiations in
`inputs/access_ctrl_netlist.v`. Look at which primitive
(`DFF_POSEDGE`/`DFF_NEGEDGE` from `inputs/cell_library.v`) each documented
state element actually uses, and identify any instance whose instantiated
primitive does not match the documented discipline. Note which net feeds
the `.d` port of that instance, since this determines what value is being
captured (potentially prematurely) relative to the rest of the pipeline.
Think carefully about *how* that mismatch manifests in time (e.g. at what
granularity relative to the clock period) so that your written
justification/summary accurately reflects the actual timing behavior, not
just the structural fact of a mismatched primitive. You may use
`inputs/testbench_stub.v` as a starting point for your own simulation-based
exploration if you wish to corroborate your findings before submitting.

## Running the grader locally

```
python3 evaluation/evaluate.py
```

Each requirement prints exactly one line:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <reason>
```

The process exits `0` only if every requirement passes.