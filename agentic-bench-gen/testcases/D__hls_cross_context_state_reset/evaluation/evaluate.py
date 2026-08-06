import subprocess
import sys
import os
import tempfile

REQUIREMENTS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2"]

def main():
    # Paths relative to the repository root (where evaluate.py is invoked)
    submission_cpp = "inputs/stream_accumulator.cpp"
    harness_cpp = "evaluation/harness_main.cpp"
    header_h = "inputs/stream_accumulator.h"

    # Check that required files exist
    for f in [submission_cpp, harness_cpp, header_h]:
        if not os.path.isfile(f):
            print(f"[TEST] FAIL: SETUP: {f} not found")
            sys.exit(1)

    # Create a temporary directory for the build artifacts
    with tempfile.TemporaryDirectory() as tmpdir:
        binary = os.path.join(tmpdir, "harness")

        # Compile
        compile_cmd = [
            "g++", "-std=c++17", "-Wall", "-Werror",
            "-I", "inputs",
            "-o", binary,
            submission_cpp,
            harness_cpp
        ]
        try:
            proc = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
        except subprocess.TimeoutExpired:
            # Compilation timed out – treat as failure for all requirements
            for req in REQUIREMENTS:
                print(f"[TEST] FAIL: {req}: compile timed out")
            sys.exit(1)

        if proc.returncode != 0:
            # Compilation failed – emit FAIL for every requirement
            stderr_summary = proc.stderr.strip().split('\n')[-1] if proc.stderr.strip() else "unknown error"
            for req in REQUIREMENTS:
                print(f"[TEST] FAIL: {req}: compile failed: {stderr_summary}")
            sys.exit(1)

        # Compilation succeeded → FR1 passes
        print("[TEST] PASS: FR1")

        # Run the binary
        try:
            run_proc = subprocess.run(
                [binary],
                capture_output=True,
                text=True,
                timeout=10
            )
        except subprocess.TimeoutExpired:
            # Runtime timeout – fail remaining requirements
            for req in REQUIREMENTS[1:]:
                print(f"[TEST] FAIL: {req}: run timed out")
            sys.exit(1)

        if run_proc.returncode != 0:
            # Runtime crash – fail remaining requirements
            for req in REQUIREMENTS[1:]:
                print(f"[TEST] FAIL: {req}: run crashed with code {run_proc.returncode}")
            sys.exit(1)

        # Parse stdout for [TEST] markers
        output = run_proc.stdout
        results = {}
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("[TEST] PASS: "):
                req_id = line[len("[TEST] PASS: "):].strip()
                results[req_id] = "PASS"
            elif line.startswith("[TEST] FAIL: "):
                # Extract requirement id (up to the first colon after FAIL:)
                rest = line[len("[TEST] FAIL: "):]
                if ":" in rest:
                    req_id = rest.split(":", 1)[0].strip()
                else:
                    req_id = rest.strip()
                results[req_id] = "FAIL"

        # Check that every requirement (except FR1, already handled) was reported
        all_pass = True
        for req in REQUIREMENTS[1:]:
            if req not in results:
                print(f"[TEST] FAIL: {req}: no result reported by harness")
                all_pass = False
            elif results[req] != "PASS":
                # The harness already printed the FAIL line, but we need to ensure we exit 1
                all_pass = False

        if all_pass:
            sys.exit(0)
        else:
            sys.exit(1)

if __name__ == "__main__":
    main()