# Evaluation Harness for Side-Channel and Fault Analysis Task

## Directory Layout

```
.
├── inputs/                          # Provided input artifacts (read-only)
│   ├── masked_sbox.v                # RTL design under analysis
│   └── leakage_model.txt            # Leakage model description
├── submission/                      # Participant submission area
│   └── vulnerability_report.json    # Answer file to be graded
└── evaluation/                      # Grading infrastructure
    ├── README.md                    # This file
    ├── evaluate.py                  # Main grading script
    └── private/                     # Private grading data (not shipped)
        └── ground_truth.py          # Hidden ground-truth constants
```

## Submission Contract

This is an **analysis_report** task. The participant does **not** modify the input artifacts. Instead, they submit a single answer file:

- **Path:** `submission/vulnerability_report.json`
- **Format:** A JSON object with three required string fields:
  - `recombination_net` — hierarchical name of the net where shares recombine
  - `recombination_register` — hierarchical name of the register capturing the recombined value
  - `leakage_type` — description of the leakage mechanism

## Grading Contract

The evaluation follows the **report_grading** contract. `evaluate.py` reads the input artifacts for reference and grades the submitted answer file against hidden ground truth. The toolchain (`iverilog`, `vvp`, `yosys`) is available for optional cross-checks, but verdicts are based solely on the submitted report content.

## Metrics

The task defines three binary metrics, each mapped to one or more requirements:

| Metric                  | Description                                                                 | Requirements |
|-------------------------|-----------------------------------------------------------------------------|--------------|
| `leakage_detection_accuracy` | 1.0 if the exact recombination net and register are correctly identified    | SR1, SR2     |
| `fault_coverage`        | 1.0 if the report identifies the flawed register without false positives    | SR3          |
| `hardening_precision`   | 1.0 if the suggested leakage type matches the ground truth                  | (informational) |

## Requirements Checked

`evaluate.py` verifies the following requirements and emits `[TEST] PASS` or `[TEST] FAIL` markers for each:

- **FR1:** The submission file is valid, parseable JSON.
- **FR2:** The JSON contains the three required fields with non-empty string values.
- **FR3:** The reported net and register identifiers exist in the provided RTL netlist.
- **SR1:** The reported recombination net matches the true leakage point.
- **SR2:** The reported recombination register matches the true storage element.
- **SR3:** The reported identifiers do not correspond to any benign share registers or nets.

A correct submission passes all requirements; the provided baseline submission is expected to fail at least one requirement.