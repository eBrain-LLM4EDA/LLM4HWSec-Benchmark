# Gate-Level Trojan Detection: Tamper-Counter Audit Module

## Task

You are given a gate-level structural Verilog netlist of a tamper-monitoring
audit subsystem (`inputs/audit_module_netlist.v`), along with a design brief
(`inputs/design_brief.md`) describing its intended functional and reset
behavior, and a navigational port/net reference (`inputs/port_map.txt`).

Your job is to analyze the netlist — structurally and/or by simulation with
the provided toolchain (`yosys`, `iverilog`, `vvp`) — and determine whether
any gate-level logic allows the `tamper_count` register bank to be cleared
through a path other than the documented synchronized global reset.

**You must not modify any files under `inputs/`.** Submit your findings as a
separate answer file.

## Submission

Place your answer at:

```
submission/trojan_report.json
```

This must be a single JSON object with **exactly** these six top-level
fields:

| Field                | Type            | Description                                                                 |
|----------------------|-----------------|-------------------------------------------------------------------------------|
| `trojan_present`     | boolean         | Whether an unauthorized clear path was found.                                 |
| `suspect_gates`      | array of string | Instance names of gate(s) implementing the unauthorized clear condition.      |
| `altered_net`        | string          | Name of the net carrying the unauthorized clear signal into the counter's async clear pin. |
| `affected_registers` | array of string | Instance names of the flip-flop bank(s) whose async clear pin is driven by `altered_net`. |
| `trigger_condition`  | string          | Boolean expression, in terms of `audit_top` primary input port names, describing when the unauthorized clear activates. |
| `justification`      | string          | Free-text explanation (max 2000 characters).                                  |

No other submission files are graded.

## Running the grader

```
python3 evaluation/evaluate.py
```

`evaluate.py`:

- Reads `inputs/audit_module_netlist.v`, `inputs/design_brief.md`, and
  `inputs/port_map.txt` **for reference only** — it does not grade anything
  in `inputs/`.
- Grades the content of `submission/trojan_report.json` against the netlist's
  actual structure.
- May optionally cross-check a reported `trigger_condition` by simulating
  `inputs/audit_module_netlist.v` with `iverilog`/`vvp`, but the primary
  verdict is computed by evaluating your reported expression as a boolean
  truth table.
- Prints one `[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>` line per
  requirement below, and exits `0` only if all of them pass.

## Requirements checked

**Functional / format requirements** (structure and well-formedness of
`trojan_report.json`, independent of whether your conclusions are correct):

- `FR1` — The file is valid JSON containing all six required fields with the
  correct types.
- `FR2` — Every instance name in `suspect_gates`/`affected_registers`, and
  the net name in `altered_net`, must correspond to an actual gate instance
  or net that exists in `inputs/audit_module_netlist.v`.
- `FR3` — If `trojan_present` is `true`, `trigger_condition` must be a
  syntactically valid boolean expression referencing only the primary input
  ports of `audit_top` (`clk`, `rst_n`, `maintenance_req`, `alarm`,
  `tamper_event`).
- `FR4` — `justification` must be non-empty and at most 2000 characters.

**Security requirements** (substantive correctness of your findings, judged
against the netlist's actual structure and behavior):

- `SR1` — `altered_net` must correctly identify the net that actually drives
  the asynchronous clear pins of the `tamper_count` register bank, and that
  net must not be the legitimate synchronized reset signal itself.
- `SR2` — `suspect_gates` must include the gate instance(s) that structurally
  implement the unauthorized clear condition and merge it into the reset
  path ahead of the counter's clear pins.
- `SR3` — `trigger_condition` must be logically equivalent, across the full
  truth table, to the actual condition under which the unauthorized clear
  activates, and must not depend on `rst_n` as a necessary condition.
- `SR4` — `trojan_present` must be reported as `true`.

All eight requirements (`FR1`–`FR4`, `SR1`–`SR4`) must `PASS` for a passing
grade. A report that merely satisfies the JSON schema without correctly
identifying the unauthorized clear path (e.g. an empty/naive
`trojan_present: false` report) will fail the `SR` checks and therefore fail
overall.