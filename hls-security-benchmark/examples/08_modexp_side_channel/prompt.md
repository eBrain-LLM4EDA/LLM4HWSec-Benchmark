# Task: Eliminate Side-Channel Leakage in Modular Exponentiation

Given `insecure.cpp`, a square-and-multiply modular exponentiation that leaks exponent bits through timing.

## Objectives
1. **Audit** for timing/power side-channel vulnerabilities (CWE-208).
2. **Harden** using Montgomery ladder or equivalent constant-time algorithm:
   - Same number of operations per exponent bit regardless of bit value
   - No data-dependent branching on secret exponent
   - Branchless conditional swap (cswap)
3. Ensure synthesis compatibility.

## Deliverables
- `secure.cpp` — hardened HLS C++ code
- `vulnerability_report.md`
