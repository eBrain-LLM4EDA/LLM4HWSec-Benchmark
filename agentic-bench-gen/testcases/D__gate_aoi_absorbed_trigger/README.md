# Gate-Level Trojan Detection: AOI-Absorbed Trigger

## Objective

You are given a flat, gate-level Verilog netlist (`design.v`) and a small technology library (`cells.lib`). The netlist implements a digital design with a single-bit output `control_out`. Your task is to analyze the netlist and identify any logic that could cause the `control_out` signal to flip under a specific, rare input condition.

Specifically, you must locate:

- **Trigger logic**: cells and nets that implement a rare condition (e.g., a specific combination of internal states and inputs).
- **Payload logic**: cells and nets that directly drive the `control_out` signal in response to the trigger.

## Input Artifacts

All input files are located in the `inputs/` directory:

- `design.v` – Flat gate-level Verilog netlist. The design uses only the cell types defined in `cells.lib`.
- `cells.lib` – Technology library defining the available cell models: `AOI21`, `OAI22`, `INV`, `XOR`, and `DFF`.

## Constraints

- The netlist is a flat, gate-level Verilog file (no hierarchy beyond the top-level module).
- The cell vocabulary is limited to `AOI21`, `OAI22`, `INV`, `XOR`, and `DFF`.
- `control_out` is a single-bit output of the top-level module.
- All instance names and net names are legal Verilog identifiers (no slashes or brackets).

## Submission Format

You must produce a single JSON file at `submission/trojan_report.json`. The file must contain a JSON object with the following required fields:

- `"trigger_cells"` – array of strings: instance names of cells that implement the trigger condition.
- `"trigger_nets"` – array of strings: names of nets that carry the trigger signal.
- `"payload_cells"` – array of strings: instance names of cells that implement the payload effect.
- `"payload_nets"` – array of strings: names of nets that carry the payload effect.

All four arrays must be **non-empty**. Each reported cell instance name and net name must exist in the provided netlist (`design.v`).

### Example

```json
{
  "trigger_cells": ["u_aoi_1", "u_oai_2"],
  "trigger_nets": ["n_trigger_internal"],
  "payload_cells": ["u_xor_1"],
  "payload_nets": ["n_payload_out"]
}
```

## Evaluation

Your submission will be graded against a hidden ground truth. The evaluation metrics include:

- **Detection rate**: proportion of correctly identified trigger and payload components.
- **False positive rate**: proportion of incorrectly reported components.
- **Inference latency**: time taken to grade your submission.

A valid submission that correctly identifies the Trojan logic will achieve a high detection rate and low false positive rate. An empty or obviously incorrect submission will fail.

## Getting Started

1. Examine `design.v` and `cells.lib` to understand the netlist structure.
2. Trace the logic driving `control_out` and look for rare-condition circuitry.
3. Identify the cells and nets involved in the trigger and payload.
4. Create `submission/trojan_report.json` with your findings.

Good luck!