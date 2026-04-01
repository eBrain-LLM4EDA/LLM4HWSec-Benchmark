# Task: Add Temporal Isolation to Bus Arbiter

Given `insecure.cpp`, a priority-based bus arbiter where secure traffic creates observable contention for non-secure masters.

## Objectives
1. **Audit** for resource isolation violations (CWE-1189) — timing interference between security domains.
2. **Harden** using time-division multiplexing (TDM):
   - Assign dedicated time slots to secure and non-secure masters
   - Eliminate cross-domain contention (no timing side channel)
   - Remove grant history from responses
   - Per-master response channels
   - Constant-time slot advancement
3. Ensure synthesis compatibility.

## Deliverables
- `secure.cpp` — hardened HLS C++ code
- `vulnerability_report.md`
