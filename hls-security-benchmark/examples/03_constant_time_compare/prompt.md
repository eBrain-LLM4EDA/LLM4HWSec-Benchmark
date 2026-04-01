# Task: Eliminate Timing Side Channel in Token Comparison

Given `insecure.cpp`, an HLS token comparator with a timing side channel.

## Objectives
1. **Audit** for timing side-channel vulnerabilities (CWE-208).
2. **Harden** to constant-time: fixed iteration count, no early exit, no data-dependent branching.
3. Ensure HLS synthesis produces fixed-latency pipeline.

## Deliverables
- `secure.cpp` — hardened HLS C++ code
- `vulnerability_report.md`
