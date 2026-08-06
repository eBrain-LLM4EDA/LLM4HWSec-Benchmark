# Gate-Level Trojan Detection: TMR Voter Wiring Audit

## Task

You are given a gate-level Verilog netlist implementing a Triple Modular
Redundancy (TMR) block: three small combinational replica modules feed a
majority voter that produces a single voted output. TMR is only effective if
each of the voter's three inputs genuinely originates from a distinct
replica's output net — that is the entire basis of its single-fault-masking
guarantee.

Your job is to **analyze the wiring of the netlist** (structurally, and
optionally by simulation) and determine whether that one-replica-per-voter-
input topology actually holds, or whether the wiring deviates from it in a
way that creates a hidden single point of failure. Report your findings in
the required JSON schema.

You do not need to modify any input file. You are only asked to analyze it
and produce an answer file.

## Inputs

All input artifacts live under `inputs/` and are read-only reference
material:

- `inputs/tmr_voter_netlist.v` — the structural Verilog netlist under test.
  It defines a top-level module together with its replica submodules, its
  voter submodule, and any helper/glue cells. It is self-contained and
  compiles standalone with `iverilog -g2012`.
- `inputs/fault_harness_tb.v` — a compact testbench that instantiates the
  netlist, drives a handful of representative input vectors, and provides a
  way to inject a single stuck-at fault into one replica at a time while
  observing the voted output. Use it (or write your own harness) to
  empirically probe whether a single-replica fault can flip the top-level
  output.
- `inputs/design_brief.md` — a plain-English functional description of the
  intended TMR design: the port list, the expected instance/net names, and
  the invariant that each voter input should be driven by a distinct
  replica's output net.

## Toolchain

The following tools are available in the evaluation environment for your own
self-checking, and `evaluate.py` may also use them to cross-check specific
claims in your report:

- `iverilog` / `vvp` — compile and simulate the netlist and testbench.
- `yosys` — structural inspection (e.g. fanout/driver tracing, `select`
  queries) if you want to confirm net connectivity programmatically.

You are free to trace the wiring by hand-reading the Verilog as well; no
particular tool is required.

## What to look for

Focus on the connectivity between the replica outputs and the voter's three
inputs, and on whether every net that is supposed to carry a replica's
output is actually used where it should be. A design that looks functionally
correct on ordinary test vectors can still have a structural wiring defect
that silently defeats fault masking — a single fault in the "wrong" replica
would then be able to influence a majority of the voter's inputs at once,
corrupting the top-level output. Nothing in the input files will tell you
directly whether such a defect exists or where; you must determine that from
the netlist and/or simulation evidence yourself.

## Output: `submission/trojan_report.json`

Your answer is a single JSON file at `submission/trojan_report.json`
(UTF-8, valid JSON, no trailing comments). It must contain exactly the
following six top-level fields:

| Field | Type | Description |
|---|---|---|
| `trojan_present` | boolean | `true` if you found a wiring anomaly that breaks single-fault masking, `false` otherwise. |
| `suspect_instances` | array of strings | Gate-level instance names, exactly as they appear in `inputs/tmr_voter_netlist.v`, implicated in the anomaly. If a spurious buffer/tap/wiring-alias cell exists, its exact instance name must be included here. |
| `suspect_nets` | array of strings | Net/wire names (as declared or referenced in the netlist) that carry the corrupted or duplicated signal, including any voter input net(s) that no longer originate from their intended replica. |
| `affected_output` | string | The name of the top-level output port (as declared in the module header) that can be corrupted by a single replica fault due to the anomaly. |
| `root_cause` | string, ≤500 characters | Free-text explanation of the defect — specifically, which replica's output ends up feeding which voter input incorrectly. |
| `confidence` | number | A value between `0.0` and `1.0` reflecting your confidence in the finding. This is recorded for analysis but does not by itself determine pass/fail. |

### Schema requirements (checked automatically)

- The file must parse as valid JSON with all six fields present and
  correctly typed.
- If `trojan_present` is `true`:
  - `suspect_instances` must be non-empty, and every entry must match an
    actual instance identifier declared in `inputs/tmr_voter_netlist.v`.
  - `suspect_nets` must be non-empty, and every entry must match an actual
    net/wire identifier declared or referenced in
    `inputs/tmr_voter_netlist.v`.
- `affected_output` must exactly match one of the top-level output port
  names declared in the module header of `inputs/tmr_voter_netlist.v`.

Beyond schema validity, your report is graded on whether it *substantively*
and *correctly* identifies the real wiring defect (the specific instance
responsible, the specific nets involved, and the specific vulnerable
top-level output) — not merely on whether the JSON is well-formed. A report
that only flags the voter or the replicas in general terms, without pointing
to the actual anomalous wiring/instance, will not be judged correct even if
`trojan_present` is `true`.

## Starter submission

`submission/trojan_report.json` currently ships as a naive placeholder
(`trojan_present: false`, empty suspect lists). This placeholder is a
starting template only — it does **not** represent a valid analysis and is
expected to fail grading. You must overwrite this file with your own
findings before submitting.

## Notes

- Do not modify any file under `inputs/`; they are reference material only.
- Your submission is exactly one file: `submission/trojan_report.json`.
- No hints about the specific location or naming of any defect are given
  beyond what you can derive from the input artifacts themselves.