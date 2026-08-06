# Evaluation Harness for stream_accumulator

## Overview

This directory contains a behavioral test harness for the `process_sample` function defined in `inputs/stream_accumulator.h`. The harness compiles and runs the submitted `inputs/stream_accumulator.cpp` together with `evaluation/harness_main.cpp`, then checks the output against the functional and security requirements specified in the task.

## Files

- `evaluation/README.md` – this file
- `evaluation/harness_main.cpp` – C++ test driver that calls `process_sample` with deterministic sequences and prints machine‑parseable `[TEST] PASS` / `[TEST] FAIL` lines
- `evaluation/evaluate.py` – Python entry point that orchestrates compilation, execution, and result parsing

## Requirements Tested

All checks are **behavioral** – they observe the return values of `process_sample` for fixed input sequences. No static source analysis is performed beyond the compiler’s own warnings/errors.

| Requirement | Description |
|-------------|-------------|
| FR1         | Compilation succeeds with `g++ -std=c++17 -Wall -Werror` |
| FR2         | Same‑context accumulation: `process_sample(0, 1, 0) → 1`, `(0, 2, 0) → 3`, `(0, 3, 0) → 6` |
| FR3         | Context change resets state: `process_sample(0, 5, 0) → 5`, then `(1, 10, 0) → 10` (fresh context) |
| FR4         | Explicit reset clears state: `process_sample(0, 5, 0) → 5`, then `(0, 7, 1) → 7` |
| SR1         | No cross‑context leakage: `process_sample(0, 42, 0) → 42`, then `(1, 7, 0) → 7` (not 49) |
| SR2         | Reset prevents inference of prior data: `process_sample(0, 99, 0) → 99`, then `(0, 1, 1) → 1` (not 100) |

## How to Run

From the repository root:

```bash
python3 evaluation/evaluate.py
```

`evaluate.py` will:

1. Compile `inputs/stream_accumulator.cpp` and `evaluation/harness_main.cpp` with `g++ -std=c++17 -Wall -Werror`.
2. Run the resulting binary with a timeout.
3. Parse the `[TEST] …` lines printed to stdout.
4. Exit with code `0` if every requirement passes, or `1` if any requirement fails (including compilation failure).

No arguments or environment variables are required.