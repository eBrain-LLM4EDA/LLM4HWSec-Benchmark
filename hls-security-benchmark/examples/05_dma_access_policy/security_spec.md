# Security Specification: DMA Access Policy

## Applicable CWEs
- **CWE-284**: Improper Access Control
- **CWE-1234**: Hardware Internal or Debug Modes Allow Override of Locks

## Access Control Policy
| Channel | DRAM (0x8000_0000+) | Secure MMIO (0x4000_0000–0x4000_FFFF) |
|---|---|---|
| 0 (privileged) | Read/Write | Read/Write |
| 1, 2, 3 | Read/Write | DENIED |

## Required Properties
- No debug mode field or bypass mechanism
- Address bounds validation (overflow check)
- Access denial reported in status response
