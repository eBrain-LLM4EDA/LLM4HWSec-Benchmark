# Security Specification: Memory Access Control

## Applicable CWEs
- **CWE-284**: Improper Access Control

## Access Control Policy
| Requestor ID | Addresses 0–767 | Addresses 768–1023 |
|---|---|---|
| 0 (privileged) | Read/Write | Read/Write |
| 1, 2, 3 | Read/Write | DENIED |

## Required Behavior on Denial
- Return `rdata = 0` (not memory contents)
- Set `valid = false`
- Set `access_denied = true`
