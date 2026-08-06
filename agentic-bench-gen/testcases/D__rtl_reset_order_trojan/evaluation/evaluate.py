import json
import os
import subprocess
import sys
import tempfile
from difflib import SequenceMatcher

def emit(level, req_id, msg=None):
    if level == "PASS":
        print(f"[TEST] PASS: {req_id}")
    elif level == "FAIL":
        reason = f": {msg}" if msg else ""
        print(f"[TEST] FAIL: {req_id}{reason}")
    elif level == "SETUP":
        print(f"[TEST] FAIL: SETUP: {msg}")
        sys.exit(1)

def check_file_exists(path, req_id):
    if not os.path.isfile(path):
        emit("FAIL", req_id, f"{path} not found")
        return False
    return True

def load_json(path, req_id):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        emit("FAIL", req_id, f"cannot parse {path}: {e}")
        return None

def fuzzy_match(text, reference, threshold=0.6):
    """Return True if text and reference are sufficiently similar."""
    if not text or not reference:
        return False
    return SequenceMatcher(None, text.lower(), reference.lower()).ratio() >= threshold

def main():
    # Paths
    submission_path = "submission/trojan_report.json"
    design_path = "inputs/core_wrapper.sv"
    cells_path = "inputs/cells.lib"
    tb_path = "evaluation/tb_trigger.v"
    ground_truth_path = "evaluation/private/ground_truth.json"

    # Check required input files exist (setup)
    for path, desc in [(design_path, "design"), (cells_path, "cells lib"), (tb_path, "testbench")]:
        if not os.path.isfile(path):
            emit("SETUP", f"{desc} file {path} not found")

    # FR3: Elaboration check on input artifacts (not submission)
    with tempfile.TemporaryDirectory() as tmpdir:
        sim_out = os.path.join(tmpdir, "sim.vvp")
        cmd = ["iverilog", "-g2012", "-o", sim_out, design_path, cells_path]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
            emit("PASS", "FR3")
        except subprocess.CalledProcessError as e:
            emit("FAIL", "FR3", f"input design elaboration failed: {e.stderr.strip()}")
        except subprocess.TimeoutExpired:
            emit("FAIL", "FR3", "input design elaboration timed out")

    # FR1, FR2: Validate submission JSON structure
    if not check_file_exists(submission_path, "FR1"):
        # Also fail FR2 if file missing
        emit("FAIL", "FR2", f"{submission_path} not found")
        # Continue to SR checks? No, we need the report for SR checks.
        # But we must still run simulation for SR checks? The spec says we grade the submission.
        # If submission is missing, we cannot grade SR1/SR2 properly.
        # We'll emit FAIL for SR1/SR2 as well.
        emit("FAIL", "SR1", "submission missing, cannot verify trigger description")
        emit("FAIL", "SR2", "submission missing, cannot verify payload description")
        sys.exit(1)

    report = load_json(submission_path, "FR2")
    if report is None:
        # FR2 already emitted, also fail FR1 because structure invalid
        emit("FAIL", "FR1", "report not valid JSON")
        emit("FAIL", "SR1", "report unreadable")
        emit("FAIL", "SR2", "report unreadable")
        sys.exit(1)

    # FR2: trojan_present must be boolean
    if not isinstance(report.get("trojan_present"), bool):
        emit("FAIL", "FR2", "trojan_present is not a boolean")
    else:
        emit("PASS", "FR2")

    # FR1: Check top-level fields and findings structure
    fr1_ok = True
    required_top = ["trojan_present", "findings", "rationale"]
    for field in required_top:
        if field not in report:
            emit("FAIL", "FR1", f"missing top-level field '{field}'")
            fr1_ok = False
    if "findings" in report:
        if not isinstance(report["findings"], list):
            emit("FAIL", "FR1", "'findings' is not an array")
            fr1_ok = False
        else:
            required_finding_fields = ["signal_name", "trigger_condition", "payload_effect", "confidence"]
            for idx, finding in enumerate(report["findings"]):
                if not isinstance(finding, dict):
                    emit("FAIL", "FR1", f"findings[{idx}] is not an object")
                    fr1_ok = False
                    continue
                for field in required_finding_fields:
                    if field not in finding:
                        emit("FAIL", "FR1", f"findings[{idx}] missing field '{field}'")
                        fr1_ok = False
                if "confidence" in finding and not isinstance(finding["confidence"], (int, float)):
                    emit("FAIL", "FR1", f"findings[{idx}].confidence is not a number")
                    fr1_ok = False
    if fr1_ok:
        emit("PASS", "FR1")

    # Load ground truth for SR checks
    gt = load_json(ground_truth_path, "SETUP")
    if gt is None:
        emit("SETUP", "ground truth file missing or invalid")

    # SR1 and SR2: Simulate netlist to confirm trigger/payload, then cross-check report
    # Compile and run simulation
    with tempfile.TemporaryDirectory() as tmpdir:
        sim_out = os.path.join(tmpdir, "sim.vvp")
        compile_cmd = ["iverilog", "-g2012", "-o", sim_out, design_path, cells_path, tb_path]
        try:
            subprocess.run(compile_cmd, check=True, capture_output=True, text=True, timeout=30)
        except subprocess.CalledProcessError as e:
            emit("FAIL", "SR1", f"simulation compilation failed: {e.stderr.strip()}")
            emit("FAIL", "SR2", f"simulation compilation failed: {e.stderr.strip()}")
            sys.exit(1)
        except subprocess.TimeoutExpired:
            emit("FAIL", "SR1", "simulation compilation timed out")
            emit("FAIL", "SR2", "simulation compilation timed out")
            sys.exit(1)

        run_cmd = ["vvp", sim_out]
        try:
            result = subprocess.run(run_cmd, check=True, capture_output=True, text=True, timeout=30)
            sim_output = result.stdout
        except subprocess.CalledProcessError as e:
            emit("FAIL", "SR1", f"simulation run failed: {e.stderr.strip()}")
            emit("FAIL", "SR2", f"simulation run failed: {e.stderr.strip()}")
            sys.exit(1)
        except subprocess.TimeoutExpired:
            emit("FAIL", "SR1", "simulation timed out")
            emit("FAIL", "SR2", "simulation timed out")
            sys.exit(1)

    # Parse simulation probes
    # Expected format: [PROBE] <test_name> <cycle> <protected_mode_value>
    probes = {}
    for line in sim_output.splitlines():
        if line.startswith("[PROBE]"):
            parts = line.split()
            if len(parts) >= 4:
                test_name = parts[1]
                cycle = int(parts[2])
                value = int(parts[3])
                probes.setdefault(test_name, []).append((cycle, value))

    # Check trigger test (two-cycle gap)
    trigger_observed = False
    if "trigger_test" in probes:
        # The testbench should assert protected_mode at some cycle after the gap
        for cycle, val in probes["trigger_test"]:
            if val == 1:
                trigger_observed = True
                break

    # Check persistence test
    persistence_observed = False
    if "persistence_test" in probes:
        # After trigger, protected_mode should stay high until simultaneous reset
        # We'll check that it is 1 at some point and then 0 after simultaneous reset
        saw_one = False
        saw_zero_after = False
        for cycle, val in probes["persistence_test"]:
            if val == 1:
                saw_one = True
            elif saw_one and val == 0:
                saw_zero_after = True
        if saw_one and saw_zero_after:
            persistence_observed = True

    # Now cross-check report against ground truth
    # SR1: trigger condition description
    sr1_pass = False
    if report.get("trojan_present") and isinstance(report.get("findings"), list):
        for finding in report["findings"]:
            if not isinstance(finding, dict):
                continue
            trigger_desc = finding.get("trigger_condition", "")
            if fuzzy_match(trigger_desc, gt.get("trigger_condition", "")):
                if finding.get("confidence", 0) > 0.5:
                    sr1_pass = True
                    break
    if trigger_observed and sr1_pass:
        emit("PASS", "SR1")
    else:
        reason = ""
        if not trigger_observed:
            reason = "simulation did not observe trigger"
        elif not sr1_pass:
            reason = "report does not adequately describe trigger condition"
        emit("FAIL", "SR1", reason)

    # SR2: payload effect and persistence
    sr2_pass = False
    if report.get("trojan_present") and isinstance(report.get("findings"), list):
        for finding in report["findings"]:
            if not isinstance(finding, dict):
                continue
            payload_desc = finding.get("payload_effect", "")
            if fuzzy_match(payload_desc, gt.get("payload_effect", "")):
                if finding.get("confidence", 0) > 0.5:
                    sr2_pass = True
                    break
    if persistence_observed and sr2_pass:
        emit("PASS", "SR2")
    else:
        reason = ""
        if not persistence_observed:
            reason = "simulation did not observe payload persistence"
        elif not sr2_pass:
            reason = "report does not adequately describe payload effect/persistence"
        emit("FAIL", "SR2", reason)

    # Determine exit code
    # We need to check if any FAIL was emitted. We'll re-read our own output? Simpler: track failures.
    # Since we can't easily track across functions, we'll just exit based on a global flag.
    # But we already printed PASS/FAIL. We'll just exit 0 if we think all passed.
    # We'll check the conditions we know.
    all_passed = True
    # FR1, FR2, FR3 already emitted; we need to know if they passed.
    # We'll just assume they passed if we didn't exit early? Not reliable.
    # Better: collect results in a list.
    # Since we already printed, we'll just exit 0 if we think everything passed, else 1.
    # We'll set a flag.
    # Let's restructure slightly: we'll store results in a dict and print at end.
    # But the spec says emit as we go. We'll just track failures.
    # We'll use a global list.
    # For simplicity, we'll just exit 1 if any FAIL was printed. We can check by scanning our own output? Not possible.
    # We'll maintain a boolean.
    # We'll define a class or use global variable.
    # Since we are in a script, we can use a mutable list.
    # Let's do that.

if __name__ == "__main__":
    # We'll wrap main to track failures
    import io
    from contextlib import redirect_stdout

    f = io.StringIO()
    with redirect_stdout(f):
        try:
            main()
        except SystemExit as e:
            # main called sys.exit, capture output and re-raise
            output = f.getvalue()
            print(output, end="")
            sys.exit(e.code)
    output = f.getvalue()
    print(output, end="")
    # Check if any FAIL line
    if "[TEST] FAIL" in output:
        sys.exit(1)
    else:
        sys.exit(0)