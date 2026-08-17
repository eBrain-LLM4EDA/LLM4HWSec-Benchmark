# Design Brief: Legacy PIN-Check Authentication Controller

## Context

This module implements the PIN-verification front end for a legacy
embedded access-control device (e.g., a door controller or equipment
lockbox). The device accepts an 8-bit numeric PIN from a keypad or
host interface and gates a downstream "unlock" action on successful
verification. The controller is implemented as a small synchronous
FSM and is intended to be simple, low-gate-count, and easy to
integrate into existing product firmware/hardware without requiring
external memory or a microcontroller.

## Functional requirements

1. **Reset behavior.** On assertion of the active-low synchronous
   reset (`rst_n = 0`), the controller returns to its idle state, the
   retry counter (`attempts_left`) is initialized to 3, and both
   `auth_ok` and `locked_out` are deasserted.

2. **PIN submission protocol.** The caller presents an 8-bit candidate
   PIN on `pin_in` and pulses `pin_valid` high for exactly one clock
   cycle to request verification. The controller is not required to
   accept a new submission while a previous one is still being
   processed; callers should wait for the outcome (via `auth_ok` or
   the updated `attempts_left`) before submitting again.

3. **Retry lockout policy.** The device allows up to 3 PIN attempts
   per reset cycle. Each time a submitted PIN fails to match the
   stored secret, the remaining-attempts count is reduced by one, and
   the current count is reported live on `attempts_left`. After the
   third consecutive incorrect attempt, the device enters a
   locked-out condition: `locked_out` is asserted and remains
   asserted, blocking all further authentication, until the device is
   reset.

4. **Successful authentication timing.** When a submitted PIN matches
   the stored secret and the device is not locked out, the controller
   asserts `auth_ok` for exactly one clock cycle, two cycles after the
   cycle in which `pin_valid` was asserted. This gives downstream
   logic (e.g., an unlock relay driver) a fixed, predictable latency
   to react to a successful check.

5. **Lockout suppresses success.** If the device is already locked
   out, submitting the correct PIN must not produce an `auth_ok`
   pulse. The only way to clear the locked-out condition and restore
   normal operation is a reset.

6. **Observability.** `attempts_left` is a live, registered output
   reflecting the current remaining-attempt budget at all times, so
   that host firmware can display the remaining-attempts count to the
   user (e.g., on a small LCD or LED indicator) without needing a
   separate query command.

## Non-goals

This brief covers steady-state, fault-free functional behavior only.
Environmental robustness, power sequencing, and physical tamper
resistance are addressed by other parts of the product's hardware
design and are out of scope for this controller's functional
specification.