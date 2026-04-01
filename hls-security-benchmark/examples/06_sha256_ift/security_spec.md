# Security Specification: SHA-256 HMAC IFT

## Applicable CWEs
- **CWE-200**: Exposure of Sensitive Information

## Security Properties
- HMAC key labeled SECRET; message labeled PUBLIC
- Taint must propagate through XOR, ADD, shift, and compression operations
- No SECRET-labeled data on any output except authorized HMAC output
- Message schedule must be cleared after computation
- No diagnostic or debug output ports
