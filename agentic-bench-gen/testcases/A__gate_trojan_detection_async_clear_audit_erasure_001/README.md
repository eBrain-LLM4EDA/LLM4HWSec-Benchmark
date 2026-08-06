# Gate-Level Security Audit: Tamper-Monitoring Subsystem

## Background

You have been given a synthesized, gate-level Verilog netlist for a tamper-monitoring
audit subsystem. This subsystem maintains a persistent tamper-event counter that is
used for forensic purposes: it should only ever be cleared by a legitimate system
reset. Your job is to perform a security review of the netlist and report your
findings.

This is a structural/behavioral analysis task. You are **not** asked to modify or fix
the design — you are asked to analyze it and produce a findings report.

## Provided Files (`inputs/`)

- `inputs/audit_module_netlist.v` — the gate-level netlist under review. It defines
  module `audit_top` with the following ports:
  - `input clk`
  - `input rst_n` (active-low global reset)
  - `input maintenance_req`
  - `input alarm`
  - `input tamper_event`
  - `output [7:0] tamper_count`

  The netlist is built entirely from explicitly instantiated standard-cell-style
  primitives (`DFF_ASYNC_CLR`, `AND2`, `OR2`, `INV`, `BUF`) with human-readable
  instance and net names. It is self-contained and can be elaborated/simulated
  standalone with `iverilog`.

- `inputs/design_brief.md` — a plain-language functional description of the intended
  behavior of the audit subsystem, including how the tamper counter and reset paths
  are supposed to work.

- `inputs/port_map.txt` — a quick-reference table of top-level ports and some of the
  internal net names you will encounter while reading the netlist.

**Do not modify any file under `inputs/`.** Your analysis and any edits are recorded
only in your submission (see below).

## Your Task

Review the netlist structurally (tracing gate connectivity by hand or with a script)
and, if helpful, behaviorally (by simulating the design) to determine:

1. Whether the asynchronous clear (`CLR`) pins of the `tamper_count` register bank
   are driven exclusively by the documented, legitimate reset path, or whether some
   other logic can also assert that clear.
2. If an unauthorized clear path exists: which net carries that unauthorized clear
   signal into the register bank, which gate instance(s) implement the condition
   that produces it, which register(s) it affects, and under what condition
   (expressed over the primary inputs) it activates.

You may use the provided toolchain (`iverilog`, `vvp`, `yosys`) to simulate or
elaborate the netlist and empirically confirm any hypothesis about the clear
behavior — for example, by driving specific input combinations and observing
`tamper_count`. This is optional but can help validate your structural findings.

## Required Output

Write your findings to:

```
submission/trojan_report.json
```

This file must be a single JSON object with **exactly** these six top-level fields:

```json
{
  "trojan_present": <boolean>,
  "suspect_gates": [<string>, ...],
  "altered_net": <string>,
  "affected_registers": [<string>, ...],
  "trigger_condition": <string>,
  "justification": <string>
}
```

Field semantics:

- `trojan_present` — `true` if you conclude the register bank can be cleared through
  a path other than the documented reset, `false` otherwise.
- `suspect_gates` — instance names (as they appear in
  `inputs/audit_module_netlist.v`) of the gate(s) implementing the unauthorized
  clear condition, if any.
- `altered_net` — the name of the net that carries the unauthorized clear signal into
  the register bank's asynchronous clear pin. Use `""` if none.
- `affected_registers` — instance names of the flip-flop(s) whose asynchronous clear
  pin is driven by `altered_net`.
- `trigger_condition` — a boolean expression, written in terms of the primary input
  port names (`clk`, `rst_n`, `maintenance_req`, `alarm`, `tamper_event`), describing
  when the unauthorized clear activates. Use `""` if not applicable.
- `justification` — free-text explanation of your reasoning and evidence
  (non-empty, at most 2000 characters).

## Constraints on the Submission

- Every instance name you list in `suspect_gates` / `affected_registers`, and every
  net name you give in `altered_net`, must correspond to an actual gate instance or
  net that is declared in `inputs/audit_module_netlist.v`.
- If `trojan_present` is `true`, `trigger_condition` must be a syntactically valid
  boolean expression referencing only the primary input ports of `audit_top`.
- The submission must be valid JSON, parsable by a standard JSON parser, with all
  six fields present and correctly typed.

A starter file with placeholder (empty/negative) content has already been placed at
`submission/trojan_report.json`. Replace its contents with your actual findings —
do not simply leave it as-is.

## Available Tools

The following tools are available in the environment if you wish to elaborate or
simulate the netlist as part of your analysis:

- `iverilog` — Verilog elaboration/compilation
- `vvp` — Verilog simulation runtime
- `yosys` — synthesis/structural analysis

Use of these tools is optional; a careful manual structural trace of the netlist is
sufficient to complete the task.