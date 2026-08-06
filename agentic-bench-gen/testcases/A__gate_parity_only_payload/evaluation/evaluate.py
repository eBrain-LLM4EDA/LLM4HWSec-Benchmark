#!/usr/bin/env python3
"""evaluate.py – grades submission/trojan_report.json for gate_parity_only_payload."""

import os
import subprocess
import sys

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "SR1", "SR2"]
RESULTS = []


def emit(rid, passed, reason=""):
    """Record and print a single requirement verdict."""
    if passed:
        line = f"[TEST] PASS: {rid}"
    else:
        line = f"[TEST] FAIL: {rid}: {reason}"
    print(line)
    RESULTS.append((rid, passed))


def run_checker(script_path):
    """Run a checker script and return (passed, reason)."""
    try:
        proc = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        # Look for the [TEST] marker in stdout
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("[TEST] PASS:") or line.startswith("[TEST] FAIL:"):
                # Parse the verdict
                if line.startswith("[TEST] PASS:"):
                    return True, ""
                else:
                    # Extract reason after the requirement id
                    parts = line.split(":", 2)
                    reason = parts[2].strip() if len(parts) > 2 else "checker failed"
                    return False, reason

        # If no marker found, treat as failure
        return False, f"no [TEST] marker in output: {stdout[:200]}"
    except subprocess.TimeoutExpired:
        return False, "checker timed out"
    except Exception as exc:
        return False, f"checker execution error: {exc}"


def main():
    # Run FR checkers
    fr_checkers = [
        ("FR1", os.path.join("evaluation", "tests", "check_fr1.py")),
        ("FR2", os.path.join("evaluation", "tests", "check_fr2.py")),
        ("FR3", os.path.join("evaluation", "tests", "check_fr3.py")),
    ]
    for rid, script in fr_checkers:
        passed, reason = run_checker(script)
        emit(rid, passed, reason)

    # Run SR checkers
    sr_checkers = [
        ("SR1", os.path.join("evaluation", "tests", "private", "check_sr1.py")),
        ("SR2", os.path.join("evaluation", "tests", "private", "check_sr2.py")),
    ]
    for rid, script in sr_checkers:
        passed, reason = run_checker(script)
        emit(rid, passed, reason)

    # Ensure every requirement emitted a verdict
    for rid in REQUIREMENT_IDS:
        if not any(r[0] == rid for r in RESULTS):
            emit(rid, False, "no verdict emitted (internal error)")

    all_pass = all(passed for _, passed in RESULTS)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()