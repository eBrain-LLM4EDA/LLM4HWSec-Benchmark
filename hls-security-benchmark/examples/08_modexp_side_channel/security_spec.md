# Security Specification: Modular Exponentiation

## Applicable CWEs
- **CWE-208**: Observable Timing Discrepancy

## Security Properties
- Identical number of multiplications per loop iteration regardless of exponent bit
- No conditional branches on secret exponent value
- Conditional swap must be branchless (XOR-mask or mux-based)
- Fixed loop iteration count (always 256 iterations)
