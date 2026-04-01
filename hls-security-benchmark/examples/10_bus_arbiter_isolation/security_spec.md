# Security Specification: Bus Arbiter Temporal Isolation

## Applicable CWEs
- **CWE-1189**: Improper Isolation of Shared Resources on SoC

## Security Properties
- Secure and non-secure masters must operate in separate time slots (no contention)
- No master can infer another domain's traffic patterns via grant latency
- Grant history (which master was served) must not be exposed in responses
- Slot advancement must be constant-time (always advance, even if no request)
- Security domain of request must match slot assignment
