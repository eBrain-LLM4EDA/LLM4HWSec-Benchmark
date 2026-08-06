# Evaluation Harness for HLS Privileged Command Dispatcher

This directory contains the evaluation harness that grades a hardened `dispatcher.cpp` submission.

## Structure

- **`evaluate.py`** — Main grading script. Compiles the submission with the test harness, executes the binary, and parses the output to determine pass/fail for each requirement.
- **`harness_main.cpp`** — Test harness `main()` that exercises the `dispatch()` function. It runs all functional and security checks and prints `[TEST] PASS/FAIL` markers.
- **`private/security_checks.cpp`** — Implements the security-specific test probes (SR1–SR4). Kept in a private directory to avoid revealing security intent to participants.

## Protocol

1. **Compile**: `evaluate.py` compiles `inputs/dispatcher.cpp` together with `evaluation/harness_main.cpp` and `evaluation/private/security_checks.cpp` using `g++ -std=c++11 -O0`.
2. **Execute**: The resulting binary is run with a timeout. Its standard output is captured.
3. **Grade**: The script parses the output for `[TEST] PASS: <id>` and `[TEST] FAIL: <id>: <reason>` lines. It aggregates results per requirement and exits with code 0 if all requirements pass, non-zero otherwise.

## Markers

All test outcomes are reported using the standardized markers:

- `[TEST] PASS: <requirement_id>`
- `[TEST] FAIL: <requirement_id>: <brief reason>`

These markers are the sole basis for grading.