# Task: Isolate Key Schedule from User Data Path

Given `insecure.cpp`, a crypto engine that shares a single buffer for key expansion and user data processing.

## Objectives
1. **Audit** for resource isolation violations (CWE-1189).
2. **Harden** by separating key schedule storage from data processing buffers, adding explicit zeroization of key material, and preventing cross-domain buffer access.
3. Ensure synthesis compatibility.

## Deliverables
- `secure.cpp` — hardened HLS C++ code
- `vulnerability_report.md`
