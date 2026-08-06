# Evaluation Harness for Dual-Counter Timeout Module Vulnerability Analysis

## Directory Layout

```
.
├── inputs/                  # Provided design artifacts (read-only)
│   ├── timeout_module.v     # RTL source of the dual-counter timeout module
│   ├── fault_model.txt      # Description of the single-bit transient fault model
│   └── design_brief.md      # Functional specification and architecture overview
├── submission/              # Participant submission directory
│   └── vulnerability_report.json   # Answer file to be graded
└── evaluation/              # Evaluation harness (this directory)
    ├── README.md            # This file
    └── evaluate.py          # Main grading script
```

## Submission Contract

The participant must analyze the provided RTL design and fault model, then produce a single answer file:

- **Path:** `submission/vulnerability_report.json`
- **Format:** Valid JSON with the following schema:
  ```json
  {
    "common_mode_node": "<string identifier of the net or register>",
    "failure_mechanism": "<string explanation of how faulting this node defeats both counters>"
  }
  ```
- Both fields are required and must be non-empty strings.
- The `common_mode_node` must be a precise hierarchical name matching the RTL source.
- The participant does **not** modify any files under `inputs/`.

## Evaluation Contract

`evaluate.py` grades the submitted answer file against hidden ground truth. It does **not** execute or simulate the RTL; it only inspects the content of `submission/vulnerability_report.json`.

The script:
1. Checks that the submission file exists and is valid JSON.
2. Verifies that required fields are present and non-empty.
3. Compares the reported `common_mode_node` against the expected shared enable signal (accepting both bare and hierarchical names).
4. Assesses the `failure_mechanism` description for semantic correctness.

Each check produces a deterministic `[TEST] PASS` or `[TEST] FAIL` marker on stdout. The script exits with code 0 only if all checks pass.

## Toolchain

- **Python 3** (standard library only) – no external packages required.
- No RTL simulation or synthesis tools are invoked during grading.

## Requirements

| ID   | Type       | Description (summary) |
|------|------------|------------------------|
| FR1  | Functional | Submission file exists and is valid JSON. |
| FR2  | Functional | `common_mode_node` field is present and non-empty. |
| FR3  | Functional | `failure_mechanism` field is present and non-empty. |
| SR1  | Security   | `common_mode_node` matches the shared enable signal (bare or hierarchical name). |
| SR2  | Security   | `failure_mechanism` correctly explains how a fault on the shared enable defeats both counters and prevents timeout. |

*Note: The exact expected values for SR1 and SR2 are not disclosed here; they are derived from the hidden ground truth.*