# Evaluation Harness for Pipelined Saturating MAC Recovery

## Overview

This directory contains the evaluation harness for the hardware reverse engineering task "Recover a pipelined signed saturating MAC". The harness compiles the participant's submitted RTL (`submission/recovered_rtl.v`) together with a testbench and a golden reference model, runs a cycle-accurate simulation using Icarus Verilog, and grades the submission against the functional and security requirements defined in the task specification.

## Files

| File | Purpose |
|------|---------|
| `evaluate.py` | Main entry point. Orchestrates compilation, simulation, and result parsing. |
| `tb_mac_top.v` | Top-level testbench. Instantiates the submission's `mac_top` module and the golden reference model `mac_golden`. Drives test vectors, compares outputs cycle-by-cycle, and prints `[TEST] PASS/FAIL` markers. |
| `mac_golden.v` | Behavioral golden reference model implementing `sat20(acc + signed(a)*signed(b))` with exactly two-cycle latency, matching the public interface timing contract. |
| `README.md` | This file. |

## Testbench Structure

The testbench (`tb_mac_top.v`) performs the following:

1. **Clock and reset generation**: Produces a free-running clock and an active-low asynchronous reset sequence.
2. **Stimulus application**: Drives `a`, `b`, and `valid_in` with a fixed sequence of test vectors covering:
   - Reset behavior (FR2)
   - Basic arithmetic (FR3)
   - Positive and negative saturation (FR4)
   - Timing invariance under varying data patterns (SR1)
   - Exhaustive corner-case signed values (SR2)
3. **Golden comparison**: Instantiates `mac_golden` which computes the expected `result` and `result_valid` cycle-by-cycle. The testbench compares the submission's outputs against the golden model on every clock edge after reset release.
4. **Result reporting**: Prints `[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>` for each requirement.

## How to Run

Execute the evaluation script from the repository root:

```bash
python3 evaluation/evaluate.py
```

The script will:

1. Verify that `submission/recovered_rtl.v` exists.
2. Compile the submission together with `evaluation/tb_mac_top.v` and `evaluation/mac_golden.v` using `iverilog -g2012`.
3. Run the simulation with `vvp`.
4. Parse the printed `[TEST]` markers and emit a final summary.
5. Exit with code 0 if all requirements pass, or non-zero if any fail.

## Toolchain

- **Icarus Verilog** (`iverilog`, `vvp`): Used for compilation and simulation.
- **Python 3**: Standard library only; invokes the toolchain via `subprocess`.

## Notes

- The golden model is derived solely from the public specification and is independent of any particular implementation style.
- The harness does not inspect the submission's source code for structural patterns; all grading is based on observed simulation behavior.
- Compilation failures, simulation timeouts, and missing submission files are reported as `[TEST] FAIL` for the relevant requirements.