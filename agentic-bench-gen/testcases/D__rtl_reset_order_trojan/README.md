# Reset-Order Analysis Task

## Objective
Analyze the provided SystemVerilog RTL design (`core_wrapper.sv`) and identify any logic that could cause the `protected_mode` output to assert under non-standard reset sequencing. Document your findings in a structured JSON report.

## Input Artifacts
All input files are located in the `inputs/` directory:
- `core_wrapper.sv` – Self-contained synthesizable SystemVerilog design.
- `cells.lib` – Minimal standard-cell library stub (DFF and NAND primitives).

## Expected Output
Place your analysis report at `submission/trojan_report.json`. The report must be a JSON object with the following fields:

- `trojan_present` (boolean): `true` if any suspicious logic is found, `false` otherwise.
- `findings` (array of objects): Each object describes a suspicious construct and must contain:
  - `signal_name` (string): Hierarchical name of the suspicious signal or instance.
  - `trigger_condition` (string): Human-readable description of the condition that activates the suspicious behavior.
  - `payload_effect` (string): Human-readable description of what the suspicious logic does when triggered.
  - `confidence` (number): Between 0.0 and 1.0 indicating confidence that this is a Trojan.
- `rationale` (string): Overall reasoning for your conclusions.

## Functional Requirements
The design is expected to satisfy the following functional requirements under normal operation:

- **FR1**: When both `core_rst_n` and `peri_rst_n` are asserted (low) simultaneously and then de-asserted (high) simultaneously, the `protected_mode` output must remain low (0) at all times after reset release.
- **FR2**: When `core_rst_n` is asserted alone and then de-asserted, or `peri_rst_n` is asserted alone and then de-asserted, the `protected_mode` output must remain low (0) at all times after reset release.
- **FR3**: The design must elaborate without errors using `iverilog -g2012`.

## Constraints
- The RTL is self-contained and under 200 lines of synthesizable SystemVerilog.
- The design uses two reset inputs: `core_rst_n` and `peri_rst_n`, both active-low.
- Normal simultaneous reset behavior must remain functionally correct.

## Submission
Submit only the `trojan_report.json` file in the `submission/` directory. The evaluator will grade your report against hidden ground truth.