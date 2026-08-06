import os
import subprocess
import sys
import tempfile

def main():
    # Check for submission file
    submission_path = "submission/recovered_rtl.v"
    if not os.path.isfile(submission_path):
        print("[TEST] FAIL: SETUP: submission/recovered_rtl.v not found")
        sys.exit(1)

    # Check for required evaluation files
    tb_path = "evaluation/tb_mac_top.v"
    golden_path = "evaluation/mac_golden.v"
    if not os.path.isfile(tb_path):
        print("[TEST] FAIL: SETUP: evaluation/tb_mac_top.v not found")
        sys.exit(1)
    if not os.path.isfile(golden_path):
        print("[TEST] FAIL: SETUP: evaluation/mac_golden.v not found")
        sys.exit(1)

    # Create a temporary directory for compilation artifacts
    with tempfile.TemporaryDirectory() as tmpdir:
        vvp_output = os.path.join(tmpdir, "sim.vvp")

        # Compile with iverilog
        compile_cmd = [
            "iverilog", "-g2012",
            "-o", vvp_output,
            submission_path,
            tb_path,
            golden_path
        ]
        try:
            compile_result = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
        except subprocess.TimeoutExpired:
            print("[TEST] FAIL: FR1: compile timed out")
            print("[TEST] FAIL: FR2: compile timed out")
            print("[TEST] FAIL: FR3: compile timed out")
            print("[TEST] FAIL: FR4: compile timed out")
            print("[TEST] FAIL: SR1: compile timed out")
            print("[TEST] FAIL: SR2: compile timed out")
            sys.exit(1)

        if compile_result.returncode != 0:
            # Compilation failed
            err = compile_result.stderr.strip()
            # Extract a concise error summary (first few lines)
            lines = err.splitlines()
            summary = "; ".join(lines[:3]) if lines else "unknown error"
            print(f"[TEST] FAIL: FR1: compile failed: {summary}")
            print(f"[TEST] FAIL: FR2: compile failed: {summary}")
            print(f"[TEST] FAIL: FR3: compile failed: {summary}")
            print(f"[TEST] FAIL: FR4: compile failed: {summary}")
            print(f"[TEST] FAIL: SR1: compile failed: {summary}")
            print(f"[TEST] FAIL: SR2: compile failed: {summary}")
            sys.exit(1)

        # Compilation succeeded -> FR1 passes
        print("[TEST] PASS: FR1")

        # Run simulation
        run_cmd = ["vvp", vvp_output]
        try:
            run_result = subprocess.run(
                run_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
        except subprocess.TimeoutExpired:
            print("[TEST] FAIL: FR2: simulation timed out")
            print("[TEST] FAIL: FR3: simulation timed out")
            print("[TEST] FAIL: FR4: simulation timed out")
            print("[TEST] FAIL: SR1: simulation timed out")
            print("[TEST] FAIL: SR2: simulation timed out")
            sys.exit(1)

        # Parse testbench output
        output = run_result.stdout
        # Collect all [TEST] lines
        test_lines = [line.strip() for line in output.splitlines() if line.strip().startswith("[TEST]")]
        if not test_lines:
            # No markers found; simulation may have crashed silently
            print("[TEST] FAIL: FR2: no test markers in simulation output")
            print("[TEST] FAIL: FR3: no test markers in simulation output")
            print("[TEST] FAIL: FR4: no test markers in simulation output")
            print("[TEST] FAIL: SR1: no test markers in simulation output")
            print("[TEST] FAIL: SR2: no test markers in simulation output")
            sys.exit(1)

        # Print all markers (they are already formatted)
        for line in test_lines:
            print(line)

        # Determine overall pass/fail
        any_fail = any("FAIL" in line for line in test_lines)
        if any_fail:
            sys.exit(1)
        else:
            sys.exit(0)

if __name__ == "__main__":
    main()