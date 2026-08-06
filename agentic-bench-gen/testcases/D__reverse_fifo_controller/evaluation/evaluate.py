import os
import sys
import subprocess
import tempfile
import re
import shutil

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1"]
SUBMISSION_FILE = "submission/recovered_rtl.v"
FUNC_TB = "evaluation/tb_fifo.v"
SEC_TB = "evaluation/private/tb_security.v"

def run_cmd(cmd, timeout=30):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s: {' '.join(cmd)}"

def parse_markers(stdout):
    results = {}
    for line in stdout.splitlines():
        m = re.match(r'\[TEST\]\s+(PASS|FAIL):\s+(\w+)', line)
        if m:
            verdict = m.group(1)
            req_id = m.group(2)
            if req_id in REQUIREMENT_IDS:
                results[req_id] = verdict
    return results

def main():
    # Check submission file exists
    if not os.path.isfile(SUBMISSION_FILE):
        print(f"[TEST] FAIL: SETUP: {SUBMISSION_FILE} not found")
        sys.exit(1)

    # Create temporary directory for compiled sims
    tmpdir = tempfile.mkdtemp(prefix="fifo_eval_")
    func_vvp = os.path.join(tmpdir, "sim_func.vvp")
    sec_vvp = os.path.join(tmpdir, "sim_sec.vvp")

    all_results = {}

    # --- Functional testbench ---
    if not os.path.isfile(FUNC_TB):
        print(f"[TEST] FAIL: SETUP: {FUNC_TB} not found")
        shutil.rmtree(tmpdir)
        sys.exit(1)

    ret, out, err = run_cmd(["iverilog", "-g2012", "-o", func_vvp, SUBMISSION_FILE, FUNC_TB])
    if ret != 0:
        # Compile failed: fail all functional requirements
        for rid in ["FR1", "FR2", "FR3", "FR4"]:
            print(f"[TEST] FAIL: {rid}: compile failed: {err.strip()}")
        # Still try security? No, exit early.
        shutil.rmtree(tmpdir)
        sys.exit(1)

    ret, out, err = run_cmd(["vvp", func_vvp])
    if ret != 0:
        for rid in ["FR1", "FR2", "FR3", "FR4"]:
            print(f"[TEST] FAIL: {rid}: simulation crashed or timed out: {err.strip()}")
        shutil.rmtree(tmpdir)
        sys.exit(1)

    func_results = parse_markers(out)
    for rid in ["FR1", "FR2", "FR3", "FR4"]:
        verdict = func_results.get(rid, "FAIL")
        reason = "" if verdict == "PASS" else " (missing marker)"
        print(f"[TEST] {verdict}: {rid}{reason}")
        all_results[rid] = verdict

    # --- Security testbench ---
    if not os.path.isfile(SEC_TB):
        print(f"[TEST] FAIL: SETUP: {SEC_TB} not found")
        shutil.rmtree(tmpdir)
        sys.exit(1)

    ret, out, err = run_cmd(["iverilog", "-g2012", "-o", sec_vvp, SUBMISSION_FILE, SEC_TB])
    if ret != 0:
        print(f"[TEST] FAIL: SR1: compile failed: {err.strip()}")
        all_results["SR1"] = "FAIL"
    else:
        ret, out, err = run_cmd(["vvp", sec_vvp])
        if ret != 0:
            print(f"[TEST] FAIL: SR1: simulation crashed or timed out: {err.strip()}")
            all_results["SR1"] = "FAIL"
        else:
            sec_results = parse_markers(out)
            verdict = sec_results.get("SR1", "FAIL")
            reason = "" if verdict == "PASS" else " (missing marker)"
            print(f"[TEST] {verdict}: SR1{reason}")
            all_results["SR1"] = verdict

    shutil.rmtree(tmpdir)

    # Determine exit code
    if any(v == "FAIL" for v in all_results.values()):
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()