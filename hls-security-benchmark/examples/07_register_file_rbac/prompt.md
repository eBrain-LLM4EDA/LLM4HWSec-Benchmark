# Task: Implement Role-Based Access Control for HLS Register File

Given `insecure.cpp`, a register file that allows unrestricted access by any master to all registers.

## Objectives
1. **Audit** for access control (CWE-284) and debug interface (CWE-1191) vulnerabilities.
2. **Harden** by implementing:
   - Hardware privilege table (master_id → privilege level, not self-declared)
   - Per-register access policy (security config, key regs, status, debug/test, general)
   - Production mode lock for debug/test registers
   - Access denied feedback in response
3. Ensure synthesis compatibility.

## Access Policy
| Register | USER | SUPERVISOR | SECURE |
|----------|------|------------|--------|
| Security Config (0) | Denied | Read-only | Read/Write |
| Key Regs (1-4) | Denied | Denied | Read/Write |
| Status (5) | Read-only | Read-only | Read/Write |
| Debug/Test (62-63) | Denied | Denied | R/W (non-prod only) |
| General (6-61) | Read-only | Read/Write | Read/Write |

## Deliverables
- `secure.cpp` — hardened HLS C++ code
- `vulnerability_report.md`
