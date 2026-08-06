# Fault Analysis of a Dual-Counter Timeout Module

## Objective

You are given the RTL design of a dual-counter timeout module. The module uses two separate counters that are monitored by comparison logic, and a timeout signal is asserted after a configured number of cycles.

Your task is to analyze the design together with the provided fault model and determine whether a single fault on a common control signal can defeat both counters simultaneously. If such a common-mode failure point exists, identify the specific net or register that represents this vulnerability and explain the mechanism by which the fault causes both counters to fail.

## Input Artifacts

All input files are located under the `inputs/` directory. **Do not modify these files.**

- `timeout_module.v` – Synthesizable Verilog RTL of the dual-counter timeout module.
- `fault_model.txt` – Description of the single-bit transient fault model to use for the analysis.
- `design_brief.md` – Functional overview of the timeout module, including port descriptions and intended behavior.

## Submission

Create a single JSON file named `vulnerability_report.json` and place it in the `submission/` directory. The file must follow this schema:

```json
{
  "common_mode_node": "<string identifier of the net or register>",
  "failure_mechanism": "<string explanation of how faulting this node defeats both counters>"
}
```

Both fields are required and must be non-empty strings. The `common_mode_node` must be a precise hierarchical name matching the RTL source.

## Constraints

- You may read and analyze the input artifacts, but you must not modify them.
- Your submission consists solely of the `vulnerability_report.json` file.
- The analysis should be based on the provided fault model and the RTL implementation.