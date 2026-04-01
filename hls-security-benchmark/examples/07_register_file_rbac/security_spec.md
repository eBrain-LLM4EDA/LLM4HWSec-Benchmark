# Security Specification: Register File RBAC

## Applicable CWEs
- **CWE-284**: Improper Access Control
- **CWE-1191**: On-Chip Debug and Test Interface With Improper Access Control

## Security Properties
- Privilege level must be determined by hardware table, not by requestor
- Key registers accessible only to SECURE privilege
- Debug/test registers must be lockable via production_mode signal
- Access denial must return zero data and set access_denied flag
- Status register must be write-protected for non-SECURE masters
