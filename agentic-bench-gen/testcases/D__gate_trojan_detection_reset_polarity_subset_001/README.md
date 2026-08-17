# Gate-Level Reset Distribution Audit

## Objective

You are given a small gate-level Verilog netlist for a controller/datapath
module, along with its design brief and a testbench that exercises a
synchronous reset. Your task is to **audit how the reset signal is
distributed to every state-holding flip-flop in the design** and report your
findings in a structured JSON file.

Specifically, trace the netlist to determine, for every flip-flop instance:

- which net or signal actually drives that flop's reset input, and
- whether that reset behavior is consistent with the majority reset
  behavior described in the design brief.

The design brief states the intended behavior: a single synchronous,
active-low reset `RSTN` should clear all state-holding registers to their
defined reset values. Your job is to verify, from the netlist itself
(not just the brief), that this is actually how every flop is wired, and to
document exactly which net feeds each flop's reset pin.

## Inputs

All files are under `inputs/` and **must not be modified**:

- `inputs/design_brief.md` — functional description of the module, its
  ports, and the intended reset behavior.
- `inputs/gate_netlist.v` — the structural gate-level netlist to audit.
- `inputs/testbench_reset_trace.v` — a testbench that drives the design
  through normal operation, asserts a reset pulse, and prints/dumps the
  values of every traced flip-flop before and after the reset pulse. You
  may use this (and the toolchain below) to help form your conclusions, but
  your graded deliverable is the JSON report described below, not any
  simulation log.

## Toolchain

The following open-source EDA tools are available in the environment if you
want to inspect or simulate the design yourself while forming your
analysis:

- `yosys` — for structural analysis / synthesis inspection of
  `gate_netlist.v`.
- `iverilog` / `vvp` — to compile and run `gate_netlist.v` together with
  `testbench_reset_trace.v` and observe flop values before/after the reset
  pulse.

Example:

```
iverilog -g2012 -o sim inputs/gate_netlist.v inputs/testbench_reset_trace.v
vvp sim
```

Using the toolchain is optional but may help you confirm your findings
before you write the report.

## Deliverable

Produce **exactly one file**: `submission/trojan_report.json`.

No other files are graded. Do not edit anything under `inputs/`.

The file must be valid JSON containing a single top-level object with
**exactly these four fields**:

| Field                 | Type                          | Description |
|-----------------------|-------------------------------|--------------|
| `trojan_present`      | boolean                       | `true` if any flip-flop's effective reset polarity/path differs from the documented common reset net feeding the majority of flops; `false` otherwise. |
| `suspect_flops`       | array of strings              | Exact Verilog instance names (as they appear in `gate_netlist.v`) of any flip-flops you identify as having anomalous reset wiring. Must be an empty array `[]` if `trojan_present` is `false`. |
| `anomaly_description` | string                        | Free-text technical description of the mechanism causing the anomaly (e.g. an inverted reset net, a missing reset connection, a gated reset). Must be at least 20 characters long if `trojan_present` is `true`. May be an empty string only if `trojan_present` is `false`. |
| `reset_net_summary`   | object (string -> string[])   | Maps each distinct reset-driving net or signal name you traced in the netlist to an array of the flip-flop instance names actually driven by that net/signal. Every flip-flop instance in `gate_netlist.v` must appear exactly once across all the arrays in this object — no flop omitted, no flop listed twice. |

### Schema example (illustrative shape only — not a hint at the correct
values for this netlist)

```json
{
  "trojan_present": true,
  "suspect_flops": ["u_example_ff9"],
  "anomaly_description": "Describe the actual reset-wiring mechanism you traced here.",
  "reset_net_summary": {
    "RSTN": ["u_example_ff0", "u_example_ff1"],
    "some_other_net": ["u_example_ff9"]
  }
}
```

## Requirements checklist

- `submission/trojan_report.json` must be valid JSON with exactly the four
  fields above (extra fields, if any, are ignored).
- Every name listed in `suspect_flops` must be an actual flip-flop instance
  name that appears in `inputs/gate_netlist.v`. Instance names are
  case-sensitive and must match exactly.
- `reset_net_summary` must account for **every** flip-flop instance in
  `inputs/gate_netlist.v` exactly once, grouped under whichever net/signal
  you determined actually drives its reset pin.
- If `trojan_present` is `true`, `anomaly_description` must be a non-empty
  string of at least 20 characters describing the actual mechanism you
  found (not a generic placeholder).
- If `trojan_present` is `false`, `suspect_flops` must be `[]` and
  `anomaly_description` may be `""`.

## Notes

- This is a documentation/audit exercise: base every claim in your report
  strictly on what you can trace in `gate_netlist.v`. Simulation with the
  provided testbench can help corroborate your findings but the netlist
  structure itself is the ground truth you are reporting on.
- Only `submission/trojan_report.json` is evaluated. Do not rename it or
  place it elsewhere.