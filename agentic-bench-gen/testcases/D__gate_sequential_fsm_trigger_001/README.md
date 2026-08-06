# Gate-Level Trojan Detection: Sequential FSM Trigger

## Objective

Analyze the provided gate-level netlist (`controller_netlist.v`) and identify any suspicious sequential logic structures and their downstream effects. Submit a report listing all suspect nodes and their roles.

## Input Artifacts

- `controller_netlist.v` – A flat, synthesized gate-level Verilog netlist of a controller design. The design contains a finite state machine implemented with standard cells and D-type flip-flops.

## Task Description

The netlist may contain a Hardware Trojan. Your goal is to inspect the netlist and produce a report of suspect nodes. A suspect node is any net or cell instance that you believe is part of a Trojan trigger or payload mechanism.

You must perform your analysis on the provided netlist **without modifying it**. You may use any analysis technique (manual inspection, simulation, formal methods, etc.) as long as the final submission is a single JSON file.

## Expected Output

Create a file named `trojan_report.json` inside the `submission/` directory. The file must be valid JSON with the following structure:

```json
{
  "suspect_nodes": [
    {
      "node_name": "<exact hierarchical name of a net or cell instance>",
      "role": "<short label describing its suspected function>"
    }
  ]
}
```

- `suspect_nodes` must be an array of objects.
- Each object must contain exactly two string fields:
  - `node_name`: The exact hierarchical name of a net or cell instance from the netlist (e.g., `u_fsm/state_reg_0`).
  - `role`: A short label describing the suspected function of the node. Examples include `"trigger_logic"`, `"payload_gate"`, `"state_register"`, etc.

The report must be parseable by a standard JSON parser. An empty `suspect_nodes` array is a valid (but likely incorrect) submission.

## Constraints

- The netlist is a flat, synthesized gate-level Verilog file.
- The design contains a finite state machine implemented with standard cells and D-type flip-flops.
- You must not modify the provided netlist.

## Submission

Place your `trojan_report.json` file in the `submission/` directory. Only this file will be evaluated.