# Evaluation Harness for Reset-Order-Triggered Privilege Trojan Detection

## Directory Layout

```
.
├── inputs/                  # Participant-facing input artifacts (read-only)
│   ├── core_wrapper.sv      # RTL design under analysis
│   └── cells.lib            # Standard-cell library stub
├── submission/              # Participant submission (graded)
│   └── trojan_report.json   # Structured Trojan analysis report
└── evaluation/              # Grading harness (this directory)
    ├── README.md            # This file
    ├── evaluate.py          # Main grading script
    ├── tb_trigger.v         # Testbench for reset-sequence simulation
    └── private/             # Private grading references
        └── ground_truth.json # Expected correct answer fields
```

## Grading Phases

The evaluation is split into two phases:

### Phase 1: Functional Requirement Checks (FR1–FR3)

These checks validate the **format and structure** of the submitted `trojan_report.json`:

- **FR1**: The report must contain the required top-level fields (`trojan_present`, `findings`, `rationale`), and each element of `findings` must include `signal_name`, `trigger_condition`, `payload_effect`, and `confidence`.
- **FR2**: The file must be valid JSON, and `trojan_present` must be a boolean.
- **FR3**: The input design (`inputs/core_wrapper.sv` + `inputs/cells.lib`) must elaborate correctly with `iverilog -g2012`. This is a sanity check on the provided artifacts, not on the submission itself.

### Phase 2: Security Requirement Checks (SR1–SR2)

These checks verify the **substantive correctness** of the submitted findings against the hidden ground truth. The harness:

1. Simulates the netlist using `evaluation/tb_trigger.v` with controlled reset-release sequences.
2. Observes `protected_mode` behavior to confirm the trigger condition (two-cycle gap between `peri_rst_n` and `core_rst_n` release) and payload persistence (sticky until simultaneous re-assertion).
3. Reads the submitted `trojan_report.json` and performs fuzzy matching of the reported `trigger_condition` and `payload_effect` against the ground-truth descriptions stored in `evaluation/private/ground_truth.json`.

- **SR1**: Confirms the report correctly identifies the reset-order trigger and describes the two-cycle gap.
- **SR2**: Confirms the report correctly identifies the payload (`protected_mode` assertion) and its sticky persistence.

## Running the Evaluation

From the repository root:

```bash
python3 evaluation/evaluate.py
```

The script expects `inputs/` and `submission/` to exist at the same level as `evaluation/`.

## PASS/FAIL Marker Format

Every requirement check emits exactly one line to stdout:

- `[TEST] PASS: <requirement_id>`
- `[TEST] FAIL: <requirement_id>: <brief reason>`

Infrastructure problems (missing files, harness errors) emit:

- `[TEST] FAIL: SETUP: <description>`

The script exits with code `0` if all requirements pass, and non-zero (`1`) if any requirement fails.

## Toolchain Dependencies

- **Python 3** (standard library only)
- **Icarus Verilog** (`iverilog`, `vvp`) – for design elaboration and simulation
- **GNU Make** or equivalent is not required; all compilation is done via `subprocess` calls within `evaluate.py`.