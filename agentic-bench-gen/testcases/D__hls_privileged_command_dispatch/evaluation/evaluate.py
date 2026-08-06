import subprocess
import sys
import os
import tempfile
import shutil

REQUIREMENTS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]

def main():
    # Paths
    submission_cpp = "inputs/dispatcher.cpp"
    harness_cpp = "evaluation/harness_main.cpp"
    security_cpp = "evaluation/private/security_checks.cpp"
    
    # Check required files exist
    for f in [submission_cpp, harness_cpp, security_cpp]:
        if not os.path.isfile(f):
            print(f"[TEST] FAIL: SETUP: {f} not found")
            sys.exit(1)
    
    # Create a temporary directory for build artifacts
    tmpdir = tempfile.mkdtemp()
    binary = os.path.join(tmpdir, "harness")
    
    # Compile
    compile_cmd = [
        "g++", "-std=c++11", "-O0",
        "-o", binary,
        submission_cpp,
        harness_cpp,
        security_cpp
    ]
    
    try:
        proc = subprocess.run(
            compile_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30
        )
    except subprocess.TimeoutExpired:
        # Compile timeout
        for req in REQUIREMENTS:
            print(f"[TEST] FAIL: {req}: compile timed out")
        shutil.rmtree(tmpdir)
        sys.exit(1)
    
    if proc.returncode != 0:
        # Compile failed
        stderr = proc.stderr.decode(errors="replace")
        # Emit FAIL for every behavioral requirement
        for req in REQUIREMENTS:
            print(f"[TEST] FAIL: {req}: compile failed: {stderr[:200]}")
        shutil.rmtree(tmpdir)
        sys.exit(1)
    
    # Run the binary
    try:
        run_proc = subprocess.run(
            [binary],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10
        )
    except subprocess.TimeoutExpired:
        for req in REQUIREMENTS:
            print(f"[TEST] FAIL: {req}: run timed out")
        shutil.rmtree(tmpdir)
        sys.exit(1)
    
    stdout = run_proc.stdout.decode(errors="replace")
    
    # Parse output for [TEST] markers
    results = {}
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("[TEST] PASS: "):
            req_id = line[len("[TEST] PASS: "):].strip()
            results[req_id] = "PASS"
        elif line.startswith("[TEST] FAIL: "):
            # Extract requirement id (up to first colon)
            rest = line[len("[TEST] FAIL: "):]
            if ":" in rest:
                req_id = rest.split(":", 1)[0].strip()
            else:
                req_id = rest.strip()
            results[req_id] = "FAIL"
    
    # Ensure all requirements are accounted for
    all_pass = True
    for req in REQUIREMENTS:
        if req not in results:
            print(f"[TEST] FAIL: {req}: no result reported by harness")
            all_pass = False
        elif results[req] == "FAIL":
            all_pass = False
    
    # Cleanup
    shutil.rmtree(tmpdir)
    
    if all_pass:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()