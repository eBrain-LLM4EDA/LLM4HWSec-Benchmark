# Hardware Trojan Detection: Debug Controller Analysis

## Objective
Analyze the provided Verilog design (`debug_controller.v`) and determine whether it contains a hardware Trojan. The design implements a compact controller with disabled-by-default debug and diagnostic paths. Your task is to classify the design as **infected** (contains a Trojan) or **clean** (no Trojan), and provide supporting evidence.

## Input Artifact
- `inputs/debug_controller.v` – Synthesizable Verilog-2012 RTL of the debug controller.

## Submission
Place your analysis results in a single JSON file at:
```
submission/trojan_report.json
```

### JSON Format
The file must contain a JSON object with the following keys:

- `infected` (boolean): `true` if you believe the design contains a hardware Trojan, `false` otherwise.
- `trojan_candidates` (array of objects): Each object represents a suspected Trojan path and must contain:
  - `signal_path` (string): The signal or path suspected of being part of a Trojan.
  - `trigger_condition` (string): The condition that activates the suspected Trojan.
  - `payload_effect` (string): The malicious effect of the suspected Trojan.
  - `confidence` (number): A value between `0.0` and `1.0` indicating your confidence in this candidate.
  If `infected` is `false`, this array must be empty (`[]`).
- `rationale` (string): A non-empty explanation of your analysis methodology and conclusion.

### Example (clean design)
```json
{
  "infected": false,
  "trojan_candidates": [],
  "rationale": "After reviewing all signal paths, no undocumented or malicious functionality was found. The debug_enable signal gates all debug logic as documented."
}
```

## Toolchain
The following tools are available for optional cross-checks:
- Icarus Verilog (`iverilog`, `vvp`) for simulation
- Yosys for synthesis and netlist inspection

You are not required to use them, but they may help verify your analysis.

## Evaluation
Your submission will be graded on:
- Correct classification (`infected` field)
- Accuracy of reported Trojan candidates (if any)
- Quality of the rationale

A naive or empty submission will not pass. Provide a thorough, evidence-based analysis.