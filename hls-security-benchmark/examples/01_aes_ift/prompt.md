# Task: Add Information Flow Tracking to AES-128 HLS Kernel

You are given an HLS C++ implementation of a simplified AES-128 encryption kernel (`insecure.cpp`). The design contains security vulnerabilities related to information leakage.

## Objectives

1. **Audit** the code and produce a vulnerability report identifying all information flow violations.
2. **Harden** the code by:
   - Adding taint/label tracking so that secret key material is distinguished from public data.
   - Ensuring taint labels propagate correctly through all operations (XOR, S-box lookup, shifts).
   - Removing any ports or paths that leak secret-labeled data to unauthorized outputs.
   - Adding a declassification check for the ciphertext output.
3. **Ensure** the hardened code is synthesizable with Xilinx Vitis HLS.

## Security Specification

- The `key` input is labeled SECRET.
- The `plaintext` input is labeled PUBLIC.
- No SECRET-labeled data may appear on any output port without explicit, authorized declassification.
- Debug or diagnostic ports exposing key-derived values must be removed.

## Deliverables

- `secure.cpp` — hardened HLS C++ code
- `vulnerability_report.md` — listing of each CWE violation found
