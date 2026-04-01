# Task: Enforce Access Control on HLS Memory Interface

You are given an HLS C++ memory controller (`insecure.cpp`) with a shared memory space. Addresses 768–1023 contain secure data (keys, config). The design lacks access control.

## Objectives

1. **Audit** the code for access control violations (CWE-284).
2. **Harden** by adding address-range-based access control:
   - Only requestor ID 0 (privileged) may access the secure region (768–1023).
   - Unprivileged access attempts must return zero and set an `access_denied` flag.
   - All other address ranges remain open to all requestors.
3. **Ensure** the design synthesizes with Vitis HLS.

## Deliverables
- `secure.cpp` — hardened HLS C++ code
- `vulnerability_report.md` — listing of each CWE violation found
