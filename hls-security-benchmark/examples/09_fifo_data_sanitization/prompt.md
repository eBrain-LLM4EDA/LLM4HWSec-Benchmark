# Task: Add Data Sanitization to Shared FIFO Buffer

Given `insecure.cpp`, a shared FIFO that retains stale data across security context switches and resets.

## Objectives
1. **Audit** for data remanence (CWE-226) and uninitialized state (CWE-1271).
2. **Harden**: clear buffer on reset and context switch, zero popped entries.
3. Ensure synthesis compatibility.

## Deliverables
- `secure.cpp` — hardened HLS C++ code
- `vulnerability_report.md`
