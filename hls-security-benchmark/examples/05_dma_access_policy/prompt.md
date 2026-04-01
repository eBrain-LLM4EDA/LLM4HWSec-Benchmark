# Task: Add Access Policy to DMA Controller

Given `insecure.cpp`, a DMA controller that allows unrestricted transfers between any memory regions.

## Objectives
1. **Audit** for access control violations (CWE-284) and debug mode bypass (CWE-1234).
2. **Harden**: add address range validation, channel-based authorization for secure MMIO regions, remove debug mode override, add bounds checking.
3. Ensure synthesis compatibility.

## Deliverables
- `secure.cpp` — hardened HLS C++ code
- `vulnerability_report.md`
