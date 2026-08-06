# Evaluation Harness for Gate-Level Trojan Detection

## Directory Layout

```
.
├── inputs/
│   └── controller_netlist.v          # Gate-level netlist to analyze
├── submission/
│   └── trojan_report.json            # Participant's answer file
└── evaluation/
    ├── README.md                     # This file
    ├── evaluate.py                   # Main grading script
    └── private/
        └── ground_truth.py           # Hidden ground truth constants
```

## Submission Contract

The participant must produce a single file named `trojan_report.json` inside the `submission/` directory. The file must be valid JSON conforming to the schema described in the task specification. The participant does **not** modify any files under `inputs/`.

## Grading Contract

`evaluate.py` implements **report grading**: it reads the participant's answer file from `submission/trojan_report.json` and grades its content against the hidden ground truth. The input artifacts under `inputs/` are available for reference (e.g., optional cross-checks using the toolchain), but the PASS/FAIL verdicts are based solely on the submitted report.

### Functional Requirements (FR)

- **FR1**: The report file must be syntactically valid JSON and parseable.
- **FR2**: The parsed JSON must contain the top-level key `"suspect_nodes"` whose value is an array.
- **FR3**: Each element in the `"suspect_nodes"` array must be an object with exactly two string keys: `"node_name"` and `"role"`.

### Security Requirements (SR)

- **SR1**: All trigger DFF instances (`u_trig_dff0` through `u_trig_dff3`) must be correctly identified with role `"trigger_logic"`.
- **SR2**: The payload XOR gate (`u_xor_payload`) must be correctly identified with role `"payload_gate"`, and the total number of false positives (incorrectly reported nodes) must not exceed 2.
- **SR3**: Each correctly identified node must have the correct role label as defined in the ground truth.

## Toolchain

- **Python 3** standard library (required for grading).
- **Yosys**, **Icarus Verilog (iverilog)**, and **vvp** are available for optional cross-checks on the input netlist but are not required for grading.

## Output Markers

`evaluate.py` emits one line per requirement using the following standardized markers:

- `[TEST] PASS: <requirement_id>` — the requirement is satisfied.
- `[TEST] FAIL: <requirement_id>: <brief reason>` — the requirement is not satisfied.

The script exits with code `0` if all requirements pass, and non-zero if any requirement fails.