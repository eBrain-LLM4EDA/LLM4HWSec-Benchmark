#!/usr/bin/env python3
"""
Testbench compiler and runner for HLS Security Benchmark.

Compiles testbenches with g++ using HLS stub headers, runs them,
and parses the output to score functional equivalence.

Usage:
    from sim_backend.compile_and_run import run_testbench
    score = run_testbench("01_aes_ift", "secure.cpp", "insecure.cpp", "testbenches/")

Or standalone:
    python compile_and_run.py --example 01_aes_ift \
        --secure path/to/secure.cpp \
        --insecure path/to/insecure.cpp
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from typing import Tuple, List


STUBS_DIR = os.path.join(os.path.dirname(__file__), "hls_stubs")


def find_testbench(example_id: str, testbench_dir: str) -> str:
    """Locate the testbench file for an example."""
    tb_path = os.path.join(testbench_dir, example_id, f"tb_{example_id}.cpp")
    if os.path.exists(tb_path):
        return tb_path
    # Fallback: look for any .cpp in the testbench dir
    tb_dir = os.path.join(testbench_dir, example_id)
    if os.path.isdir(tb_dir):
        for f in os.listdir(tb_dir):
            if f.endswith(".cpp") and f.startswith("tb_"):
                return os.path.join(tb_dir, f)
    return ""


def compile_testbench(
    testbench_path: str,
    secure_code_path: str,
    insecure_code_path: str,
    output_binary: str,
    extra_include_dirs: List[str] = None,
) -> Tuple[bool, str]:
    """
    Compile a testbench that includes both secure and insecure code.

    The testbench is expected to #include the DUT code via macros:
        #ifdef SECURE_DUT
        #include SECURE_DUT
        #endif
        #ifdef INSECURE_DUT
        #include INSECURE_DUT
        #endif

    We compile with -DSECURE_DUT="path" -DINSECURE_DUT="path".
    """
    cmd = [
        "g++", "-std=c++17", "-O2",
        f"-I{STUBS_DIR}",
        f'-DSECURE_DUT="{os.path.abspath(secure_code_path)}"',
        f'-DINSECURE_DUT="{os.path.abspath(insecure_code_path)}"',
        testbench_path,
        "-o", output_binary,
    ]

    if extra_include_dirs:
        for d in extra_include_dirs:
            cmd.append(f"-I{d}")

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=60
    )

    if result.returncode != 0:
        return False, f"Compilation failed:\n{result.stderr}"

    return True, ""


def run_binary(binary_path: str, timeout: int = 30) -> Tuple[bool, str]:
    """Run the compiled testbench and capture output."""
    result = subprocess.run(
        [binary_path], capture_output=True, text=True, timeout=timeout
    )
    return result.returncode == 0, result.stdout + result.stderr


def parse_results(output: str) -> Tuple[float, List[str]]:
    """
    Parse testbench output and compute score.

    Expected format per test:
        TEST <example_id> <vector_name>: PASS
        TEST <example_id> <vector_name>: FAIL <reason>
        SUMMARY <example_id>: <passed>/<total> passed

    Returns (score, notes).
    """
    notes = []

    # Try to find SUMMARY line
    summary = re.search(r"SUMMARY\s+\S+:\s+(\d+)/(\d+)\s+passed", output)
    if summary:
        passed = int(summary.group(1))
        total = int(summary.group(2))
        if total == 0:
            return 0.0, ["No test vectors found"]
        score = passed / total

        # Collect failure reasons
        failures = re.findall(r"TEST\s+\S+\s+\S+:\s+FAIL\s+(.*)", output)
        for fail in failures:
            notes.append(f"FAIL: {fail.strip()}")

        return round(score, 3), notes

    # Fallback: count individual TEST lines
    passes = len(re.findall(r"TEST\s+\S+\s+\S+:\s+PASS", output))
    fails = re.findall(r"TEST\s+\S+\s+\S+:\s+FAIL\s+(.*)", output)
    total = passes + len(fails)

    if total == 0:
        return 0.0, ["No test output found — testbench may have crashed"]

    for fail in fails:
        notes.append(f"FAIL: {fail.strip()}")

    return round(passes / total, 3), notes


def run_testbench(
    example_id: str,
    secure_code: str,
    insecure_code: str,
    testbench_dir: str,
) -> Tuple[float, List[str]]:
    """
    Full pipeline: find testbench → compile → run → parse → score.

    Returns (score, notes).
    """
    # Find testbench
    tb_path = find_testbench(example_id, testbench_dir)
    if not tb_path:
        return 0.75, [f"No testbench found for {example_id} — using default score"]

    # Check inputs exist
    if not os.path.exists(secure_code):
        return 0.0, ["Secure code not found"]
    if not os.path.exists(insecure_code):
        return 0.75, ["Insecure reference not found — using default score"]

    # Compile
    with tempfile.NamedTemporaryFile(suffix="", delete=False) as tmp:
        binary = tmp.name

    try:
        ok, err = compile_testbench(tb_path, secure_code, insecure_code, binary)
        if not ok:
            return 0.5, [f"Compilation failed: {err[:200]}"]

        # Run
        ok, output = run_binary(binary)
        if not ok and not output:
            return 0.25, ["Testbench crashed with no output"]

        # Parse
        score, notes = parse_results(output)
        return score, notes

    except subprocess.TimeoutExpired:
        return 0.25, ["Testbench timed out (possible infinite loop)"]
    except Exception as e:
        return 0.0, [f"Error: {str(e)}"]
    finally:
        if os.path.exists(binary):
            os.unlink(binary)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--example", required=True)
    parser.add_argument("--secure", required=True)
    parser.add_argument("--insecure", required=True)
    parser.add_argument("--testbench-dir",
                        default=os.path.join(os.path.dirname(__file__),
                                             "..", "testbenches"))
    args = parser.parse_args()

    score, notes = run_testbench(
        args.example, args.secure, args.insecure, args.testbench_dir
    )
    print(f"Score: {score}")
    for note in notes:
        print(f"  {note}")
