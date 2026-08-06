#!/usr/bin/env python3
"""
evaluate.py - Grader for hls_dma_range_overflow_001

Compiles inputs/dma_validate.cpp with evaluation/harness_main.cpp, then runs
the resulting binary against a battery of known-answer functional vectors
(FR1-FR4) and security vectors (SR1-SR4), comparing the observed return
value against a Python-computed ground truth using exact (unbounded)
integer arithmetic.
"""

import os
import subprocess
import sys
import tempfile

UINT32_MAX = 0xFFFFFFFF

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]


def ground_truth(base, length, region_start, region_size):
    """Exact containment predicate using Python's unbounded integers.

    Valid iff:
      length != 0
      AND base >= region_start
      AND base + length <= region_start + region_size
    """
    if length == 0:
        return 0
    if base < region_start:
        return 0
    if base + length > region_start + region_size:
        return 0
    return 1


def build_vectors():
    """Return dict requirement_id -> list of (base, length, region_start, region_size)."""
    vectors = {}

    # Functional requirements (fixed known-answer vectors from public_spec)
    vectors["FR1"] = [(0x1000, 0x100, 0x1000, 0x200)]
    vectors["FR2"] = [(0x1000, 0x300, 0x1000, 0x200)]
    vectors["FR3"] = [(0x0FF0, 0x20, 0x1000, 0x200)]
    vectors["FR4"] = [(0x1100, 0x0, 0x1000, 0x200)]

    # SR1: base + length (true value) exceeds UINT32_MAX
    vectors["SR1"] = [
        (0xFFFFFFF0, 0x20, 0x0, 0xFFFFFFFF),
        (0xFFFFFFFF, 0x1, 0x0, 0xFFFFFFFF),
        (0xF0000000, 0x20000000, 0x0, 0xFFFFFFFF),
    ]

    # SR2: base+length overflows uint32_t and wraps to a value spuriously
    # <= region_start+region_size under naive 32-bit arithmetic, but the
    # true (unbounded) end lies outside the region.
    vectors["SR2"] = [
        (0xFFFFFFF0, 0x30, 0xF0000000, 0x10000000),
        (0xFFFFFFF8, 0x10, 0x00000000, 0x00000010),
        (0xFFFFFFFE, 0x4, 0x00000000, 0x00000004),
    ]

    # SR3: zero-length transfers must always be rejected, regardless of
    # base/region alignment (including base == region_start).
    vectors["SR3"] = [
        (0x1000, 0x0, 0x1000, 0x200),
        (0x0, 0x0, 0x0, 0x0),
        (0x0, 0x0, 0x0, 0x100),
        (0xFFFFFFFF, 0x0, 0x0, 0xFFFFFFFF),
    ]

    # SR4: partial containment - base before region_start with end inside;
    # base inside region but end exceeds region bound; region_start+region_size
    # itself overflows uint32_t.
    vectors["SR4"] = [
        (0x0FF0, 0x20, 0x1000, 0x200),          # base before region_start
        (0x1000, 0x300, 0x1000, 0x200),          # end exceeds region bound
        (0xF0000000, 0x10, 0xF0000000, 0x20000000),  # region_start+region_size overflows 32-bit, base valid & fully contained
        (0xFFFFFFF0, 0x30, 0xF0000000, 0x20000000),  # region_start+region_size overflows 32-bit, request extends past true end
    ]

    return vectors


def compile_harness(build_dir):
    cpp_file = "inputs/dma_validate.cpp"
    harness_file = "evaluation/harness_main.cpp"
    out_bin = os.path.join(build_dir, "harness")

    cmd = ["g++", "-std=c++17", "-O0", "-o", out_bin, cpp_file, harness_file]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60
        )
    except subprocess.TimeoutExpired:
        return None, "compile timed out"

    if proc.returncode != 0:
        stderr_lines = proc.stderr.strip().splitlines()
        first_line = stderr_lines[0] if stderr_lines else "unknown compile error"
        return None, first_line

    return out_bin, None


def run_vector(binary, vector, timeout=5):
    base, length, region_start, region_size = vector
    args = [binary, str(base), str(length), str(region_start), str(region_size)]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "run timed out"

    if proc.returncode != 0:
        return None, "run crashed (exit code %d)" % proc.returncode

    out = proc.stdout.strip()
    try:
        value = int(out.splitlines()[0].strip())
    except (ValueError, IndexError):
        return None, "run produced no parseable integer output (got %r)" % out

    return value, None


def main():
    inputs_cpp = "inputs/dma_validate.cpp"
    inputs_brief = "inputs/design_brief.md"

    overall_pass = True

    if not os.path.isfile(inputs_cpp):
        for rid in REQUIREMENT_IDS:
            print("[TEST] FAIL: SETUP: %s not found" % inputs_cpp)
        sys.exit(1)

    if not os.path.isfile(inputs_brief):
        for rid in REQUIREMENT_IDS:
            print("[TEST] FAIL: SETUP: %s not found" % inputs_brief)
        sys.exit(1)

    vectors = build_vectors()

    with tempfile.TemporaryDirectory() as build_dir:
        binary, compile_err = compile_harness(build_dir)

        if binary is None:
            for rid in REQUIREMENT_IDS:
                print("[TEST] FAIL: %s: compile failed: %s" % (rid, compile_err))
            sys.exit(1)

        for rid in REQUIREMENT_IDS:
            vecs = vectors[rid]
            rid_pass = True
            fail_reason = None

            for vec in vecs:
                base, length, region_start, region_size = vec
                expected = ground_truth(base, length, region_start, region_size)
                observed, run_err = run_vector(binary, vec)

                if observed is None:
                    rid_pass = False
                    fail_reason = (
                        "run crashed/timed out on vector base=0x%X length=0x%X "
                        "region_start=0x%X region_size=0x%X (%s)"
                        % (base, length, region_start, region_size, run_err)
                    )
                    break

                if observed != expected:
                    rid_pass = False
                    fail_reason = (
                        "vector base=0x%X length=0x%X region_start=0x%X region_size=0x%X "
                        "expected=%d got=%d"
                        % (base, length, region_start, region_size, expected, observed)
                    )
                    break

            if rid_pass:
                print("[TEST] PASS: %s" % rid)
            else:
                print("[TEST] FAIL: %s: %s" % (rid, fail_reason))
                overall_pass = False

    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()