import os
import sys
import subprocess
import tempfile
import re

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1"]
BEHAVIORAL_IDS = ["FR1", "FR2", "FR3", "SR1"]

def main():
    # Check that submission file exists
    submission_path = "submission/recovered_rtl.v"
    if not os.path.isfile(submission_path):
        print(f"[TEST] FAIL: SETUP: {submission_path} not found")
        sys.exit(1)

    # Check that testbench exists
    tb_path = "evaluation/tb_crc16.v"
    if not os.path.isfile(tb_path):
        print(f"[TEST] FAIL: SETUP: {tb_path} not found")
        sys.exit(1)

    # Create temporary directory for build artifacts
    with tempfile.TemporaryDirectory() as tmpdir:
        sim_vvp = os.path.join(tmpdir, "sim.vvp")

        # Compile
        compile_cmd = [
            "iverilog", "-g2012", "-o", sim_vvp,
            submission_path,
            tb_path
        ]
        try:
            proc = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
        except subprocess.TimeoutExpired:
            # Compile timeout -> treat as compile failure
            for rid in BEHAVIORAL_IDS:
                print(f"[TEST] FAIL: {rid}: compile timed out")
            print("[TEST] FAIL: FR4: compile timed out")
            sys.exit(1)

        compile_failed = proc.returncode != 0
        compile_stderr = proc.stderr.strip()

        if compile_failed:
            # FR4 fails explicitly
            print(f"[TEST] FAIL: FR4: compile failed: {compile_stderr[:200]}")
            # All behavioral requirements fail due to compile error
            for rid in BEHAVIORAL_IDS:
                print(f"[TEST] FAIL: {rid}: compile failed: {compile_stderr[:200]}")
            sys.exit(1)
        else:
            # FR4 passes
            print("[TEST] PASS: FR4")

        # Run simulation
        run_cmd = ["vvp", sim_vvp]
        try:
            proc = subprocess.run(
                run_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
        except subprocess.TimeoutExpired:
            for rid in BEHAVIORAL_IDS:
                print(f"[TEST] FAIL: {rid}: simulation timed out")
            sys.exit(1)

        sim_stdout = proc.stdout
        sim_stderr = proc.stderr

        # Parse markers from simulation output
        markers = {}
        for line in sim_stdout.splitlines():
            match = re.match(r'\[TEST\]\s+(PASS|FAIL):\s+(\S+)', line)
            if match:
                verdict = match.group(1)
                req_id = match.group(2)
                markers[req_id] = line.strip()

        # Emit final verdicts for all requirements
        all_pass = True
        for rid in REQUIREMENT_IDS:
            if rid == "FR4":
                # Already handled above
                continue
            if rid in markers:
                print(markers[rid])
                if markers[rid].startswith("[TEST] FAIL"):
                    all_pass = False
            else:
                # Missing marker -> treat as failure
                print(f"[TEST] FAIL: {rid}: no marker found in simulation output")
                all_pass = False

        if all_pass:
            sys.exit(0)
        else:
            sys.exit(1)

if __name__ == "__main__":
    main()