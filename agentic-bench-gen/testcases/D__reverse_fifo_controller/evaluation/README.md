# Evaluation Harness for FIFO Controller Reverse Engineering Task

## Toolchain

The evaluation uses the following open-source tools, which must be available in the system PATH:

- **Icarus Verilog (`iverilog`)** – Verilog compiler for simulation.
- **vvp** – Icarus Verilog simulation runtime engine.
- **Yosys** – RTL synthesis tool (available but not required for behavioral grading; may be used for optional static checks).

## Testbench Structure

Two testbenches are provided:

1. **`evaluation/tb_fifo.v`** – Public functional testbench.  
   Instantiates the submitted `fifo_controller` module and drives a deterministic sequence of clock cycles covering all functional requirements (FR1–FR4) and edge cases (overflow, underflow, simultaneous operations, reset). Outputs are checked cycle-by-cycle against expected values derived solely from the `public_spec.interface` timing contract. Each requirement probe prints a `[TEST] PASS: <id>` or `[TEST] FAIL: <id>` marker to stdout.

2. **`evaluation/private/tb_security.v`** – Private security testbench (not visible to participants).  
   Instantiates the submitted module and runs a 1000-cycle random sequence (fixed seed) exercising all operation modes. The submission's outputs are compared cycle-accurately against a reference FIFO model that implements the exact behavior described in the public specification. This testbench verifies the hidden security requirement SR1.

## How evaluate.py Works

The `evaluation/evaluate.py` script is the main entry point for grading. It performs the following steps:

1. **Locate the submission** – Expects the participant's recovered RTL at `submission/recovered_rtl.v`. If the file is missing, it emits `[TEST] FAIL: SETUP: submission/recovered_rtl.v not found` and exits with code 1.

2. **Compile the functional testbench** – Runs:
   ```
   iverilog -g2012 -o <tmpdir>/sim_func.vvp submission/recovered_rtl.v evaluation/tb_fifo.v
   ```
   If compilation fails, it emits `[TEST] FAIL: <id>: compile failed: <error>` for every behaviorally-graded requirement and exits non-zero.

3. **Run the functional simulation** – Executes:
   ```
   vvp <tmpdir>/sim_func.vvp
   ```
   Captures stdout and parses the `[TEST] PASS/FAIL` markers for FR1–FR4.

4. **Compile and run the private security testbench** – Similarly compiles `evaluation/private/tb_security.v` with the submission, runs the simulation, and parses the SR1 marker.

5. **Aggregate results** – Collects all requirement verdicts. If any requirement fails, the script exits with code 1; otherwise it exits with code 0.

## Grading Philosophy

All grading is **behavioral**: the submission is judged solely on its cycle-accurate simulation output against the public interface contract. No static source-code analysis is used to determine a PASS (except for optional fail-on-presence vulnerability checks). This ensures that any correct implementation—regardless of coding style, naming conventions, or internal structure—will pass, while incorrect or incomplete implementations will fail.