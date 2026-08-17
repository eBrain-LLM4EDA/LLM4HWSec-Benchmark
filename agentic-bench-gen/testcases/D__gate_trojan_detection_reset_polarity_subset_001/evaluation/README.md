# Gate-Level Trojan Detection — Evaluation

## What is graded

This task is a **report-grading** task, not a code-hardening task. You do **not**
edit anything under `inputs/`. Your deliverable is a single JSON answer file:

```
submission/trojan_report.json
```

`evaluate.py` reads the reference input artifacts:

- `inputs/gate_netlist.v` — structural gate-level netlist of the `top` module
- `inputs/design_brief.md` — intended functional/reset behavior of `top`
- `inputs/testbench_reset_trace.v` — a reset-exercising testbench for `top`

and grades the *content* of `submission/trojan_report.json` against the
hidden ground truth derived from the netlist's actual reset wiring structure.
It does not execute your submission as code; it parses it as JSON and checks
its fields against reference facts extracted from the netlist (and, for one
requirement, an optional gate-level simulation cross-check).

## Required report schema

`submission/trojan_report.json` must be a single JSON object with exactly
these four top-level fields (extra fields are ignored):

- `trojan_present` (boolean)
- `suspect_flops` (array of strings — instance names exactly as they appear
  in `inputs/gate_netlist.v`)
- `anomaly_description` (string, minimum 20 characters if `trojan_present`
  is `true`; may be `""` only if `trojan_present` is `false`)
- `reset_net_summary` (object mapping each distinct reset-driving net/signal
  name to an array of flip-flop instance names driven by that net)

See `public_spec.interface` in the task specification for the authoritative
schema description.

## Requirements checked

**Functional requirements (structure/format of the report):**

- `FR1` — the file parses as JSON and contains all four required fields with
  correct types.
- `FR2` — every name in `suspect_flops` is an actual flip-flop instance name
  found in `inputs/gate_netlist.v`.
- `FR3` — `reset_net_summary` accounts for every flip-flop instance in the
  netlist exactly once (no omissions, no double-counting) across its net
  groupings.
- `FR4` — `anomaly_description` length/emptiness is consistent with the
  value of `trojan_present`.

**Security requirements (substantive correctness of the findings):**

- `SR1` — `trojan_present` correctly reflects whether the reset distribution
  network in this netlist has an anomaly.
- `SR2` — `suspect_flops` is an exact match (as a set) to the true anomalous
  flip-flop set, determined by tracing each flip-flop's reset pin connection
  through the netlist.
- `SR3` — `anomaly_description` substantively characterizes the actual
  defect mechanism (checked via a keyword/semantic rubric for reset-polarity
  inversion language), not generic or unrelated wording.
- `SR4` — `reset_net_summary` structurally separates the anomalous flops
  from the rest of the design under distinct net keys, demonstrating actual
  netlist tracing rather than a lucky guess.
- `SR5` — (optional corroboration) `evaluate.py` may compile and simulate
  `inputs/gate_netlist.v` together with `evaluation/tb_cross_check.v` using
  `iverilog`/`vvp` to observe, from a reset trace, which flip-flops actually
  fail to clear to their documented reset value (logic 0) across a reset
  pulse. This is compared against the submitted `suspect_flops` set as a
  cross-check. `SR5` always prints its own `[TEST] PASS`/`[TEST] FAIL` line,
  but — consistent with its role as a bonus/consistency signal rather than
  a primary correctness gate — a `SR5` failure alone does not by itself
  cause the overall run to exit non-zero when all of `FR1`–`FR4` and
  `SR1`–`SR4` pass. `SR5` is still fully informative: it is reported, and
  it does gate the run when any of `FR1`–`FR4`/`SR1`–`SR4` are already
  failing (there is nothing to "protect" in that case since the run is
  already failing overall).

Every requirement above always emits exactly one line of the form:

```
[TEST] PASS: <requirement_id>
```
or
```
[TEST] FAIL: <requirement_id>: <reason>
```

`evaluate.py` exits `0` only if every *gating* requirement
(`FR1`–`FR4`, `SR1`–`SR4`) passes; `SR5` is reported for every run but does
not independently flip a run from passing to failing. If any gating
requirement fails, the run exits non-zero regardless of `SR5`.

## Notes

- Nothing in `inputs/` is modified or expected to be modified by the
  submission. `evaluate.py` opens `inputs/gate_netlist.v`,
  `inputs/design_brief.md`, and `inputs/testbench_reset_trace.v` strictly
  as reference material to derive netlist structure and ground-truth facts;
  it never writes to them.
- A missing `submission/trojan_report.json` is treated as a setup failure
  (`[TEST] FAIL: SETUP: ...`) and the run exits non-zero.
- The `iverilog`/`vvp` cross-check used for `SR5` is best-effort corroboration
  of the reported findings using a separate, fixed harness testbench
  (`evaluation/tb_cross_check.v`) that probes the canonical flip-flop
  instance roles described in `inputs/design_brief.md`. If the toolchain is
  unavailable or the simulation cannot be completed, this is reported as a
  failure of `SR5` specifically (not a `SETUP` failure), but — per the point
  above — does not by itself fail an otherwise-correct submission.
- This README intentionally does not reveal which specific flip-flops or
  nets constitute the anomaly in this particular netlist instance — that is
  exactly what your submitted report is expected to determine by analyzing
  `inputs/gate_netlist.v` and `inputs/design_brief.md` yourself.