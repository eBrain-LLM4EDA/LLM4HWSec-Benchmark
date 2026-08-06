# Evaluation Harness for RTL Trojan Detection

## Directory Layout

```
evaluation/
├── README.md              # This file
├── evaluate.py            # Main grading script (entry point)
└── private/
    └── ground_truth.py    # Hidden ground truth constants (not shipped to participants)
```

## Submission Contract

This task follows the **analysis_report** submission contract:

- Participants do **not** modify the input RTL files (`inputs/top.v`, `inputs/counter.v`, `inputs/command_decoder.v`, `inputs/error_handler.v`).
- Participants submit a single answer file: `submission/trojan_report.json`.
- The answer file must be valid JSON conforming to the schema described in the task specification.

## Grading Contract

This task follows the **report_grading** evaluation contract:

- `evaluate.py` reads the submitted `submission/trojan_report.json` and grades its content against the hidden ground truth.
- The input RTL artifacts under `inputs/` are available for reference (e.g., optional cross-checks), but the PASS/FAIL verdicts are based solely on the submitted report.
- The script emits standardized `[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>` markers for each requirement.
- Exit code **0** indicates all requirements passed (correct submission).
- Exit code **non-zero** indicates at least one requirement failed (baseline or incorrect submission).

## Toolchain

The following tools are available in the evaluation environment and may be used by `evaluate.py` for optional cross-checks on the input artifacts:

- `iverilog` – Verilog compiler (supports `-g2012`)
- `vvp` – Verilog simulation runtime
- `yosys` – RTL synthesis and analysis framework

## Requirements Checked

The harness checks all functional requirements (FR1–FR3) and all security requirements (SR1–SR5) as defined in the task specification. The private ground truth module contains the expected trigger signals, payload description keywords, and confidence thresholds used for substantive grading.