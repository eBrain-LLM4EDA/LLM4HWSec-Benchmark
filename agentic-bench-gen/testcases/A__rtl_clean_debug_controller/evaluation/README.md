# Evaluation Harness for RTL Trojan Detection (Clean Debug Controller)

This directory contains the evaluation harness for the `rtl_clean_debug_controller` task. The harness grades a participant's submitted analysis report (`submission/trojan_report.json`) against the hidden ground truth.

## Entry Point

`evaluate.py` is the main grading script. It reads the submission file and emits `[TEST] PASS` or `[TEST] FAIL` markers for each requirement.

## Grading Contract

This task follows the **report_grading** evaluation mode. The participant does not modify the input RTL (`inputs/debug_controller.v`); they submit a separate answer file at `submission/trojan_report.json`. The harness grades the content of that answer file.

## Requirements

### Functional Requirements (FR)

- **FR1**: The submitted `trojan_report.json` must be valid JSON and parseable by a standard JSON parser.
- **FR2**: The report must contain the boolean field `"infected"` and the array field `"trojan_candidates"`.
- **FR3**: If `"infected"` is `true`, `"trojan_candidates"` must contain at least one object with non-empty `"signal_path"`, `"trigger_condition"`, and `"payload_effect"` strings.
- **FR4**: The `"rationale"` field must be a non-empty string explaining the analysis methodology and conclusion.

### Security Requirements (SR)

- **SR1**: The detector must not flag the documented `debug_enable` gated paths as Trojans. Any reported `trojan_candidate` whose `signal_path` involves `debug_enable` or its fanout is a false positive.
- **SR2**: The detector must correctly classify the design as clean (`infected=false` and `trojan_candidates` empty).

## Expected Behavior

- A correct submission (clean design, no Trojan) will pass all requirements.
- The shipped baseline submission (which may incorrectly report a Trojan or have malformed output) must fail at least one requirement.