# Task: Add Taint Tracking to SHA-256 HMAC Engine

Given `insecure.cpp`, an HMAC-SHA256 engine that leaks key-derived internal state.

## Objectives
1. **Audit** for information leakage (CWE-200).
2. **Harden** with taint-tracked word types through the compression function, remove diagnostic port, clear message schedule after use.
3. Ensure synthesis compatibility.

## Deliverables
- `secure.cpp` — hardened HLS C++ code
- `vulnerability_report.md`
