# Security Specification: Constant-Time Comparison

## Applicable CWEs
- **CWE-208**: Observable Timing Discrepancy

## Security Properties
- Execution time must be independent of input data values
- All TOKEN_LEN bytes must always be compared (no early exit)
- No data-dependent branching on secret reference values
- HLS synthesis must produce fixed-latency pipeline (use UNROLL or fixed-trip-count loop)
