# Design Brief: Tamper-Monitoring Audit Subsystem

## Purpose

The tamper-monitoring audit subsystem provides a persistent, forensic record of
tamper events observed by the surrounding system. Its core function is to
increment a counter, `tamper_count`, once for each detected tamper event, and
to retain that count reliably across normal system operation so that it can be
inspected later (e.g., during a maintenance or audit cycle) to determine how
many tamper events have occurred since the last legitimate reset.

Because the counter is used for forensic/audit purposes, its value is expected
to persist across all normal operating conditions and to be cleared **only**
as part of an intentional, documented system reset — never as a side effect of
routine operational signaling.

## Top-Level Interface

The subsystem is implemented as a single top-level module, `audit_top`, with
the following ports:

| Port              | Direction | Width | Description                                          |
|-------------------|-----------|-------|-------------------------------------------------------|
| `clk`             | input     | 1     | System clock. All internal state is clocked from this signal. |
| `rst_n`           | input     | 1     | Active-low global system reset.                       |
| `maintenance_req` | input     | 1     | Asserted by the maintenance interface when a maintenance operation is being requested. |
| `alarm`           | input     | 1     | Asserted when the system alarm condition is active.   |
| `tamper_event`    | input     | 1     | Pulsed high for one or more clock cycles each time a tamper event is detected upstream of this module. |
| `tamper_count`    | output    | 8     | Running count of tamper events observed since the last reset. |

## Counting Behavior

On each clock edge at which `tamper_event` is asserted, `tamper_count`
increments by one. The counter wraps around after reaching its maximum value
(255) and resumes counting from zero. No other input combination should cause
the counter value to change other than through the reset behavior described
below.

## Reset Behavior

The subsystem uses a single, global active-low reset, `rst_n`, which is
brought into the internal clock domain through a standard reset synchronizer
(an inverter/buffer stage that converts the external active-low reset into an
internal active-high, synchronized reset signal used by the register logic).

The intended behavior is:

- While `rst_n` is deasserted (logic 0), `tamper_count` is held at zero.
- Once `rst_n` is asserted (logic 1) and has propagated through the
  synchronizer, `tamper_count` resumes normal counting behavior from zero.
- No signal other than the synchronized form of `rst_n` should be capable of
  clearing `tamper_count`. In particular, the counter's cleared state should
  never depend on any combination of `maintenance_req` and `alarm`.

This reset behavior is intended to guarantee that the recorded tamper history
is only ever discarded through an explicit, system-level reset event, and not
as an incidental consequence of ordinary maintenance or alarm signaling.

## Maintenance and Alarm Signals

`maintenance_req` and `alarm` are independent operational signals used
elsewhere in the broader system:

- `maintenance_req` indicates that a maintenance technician or automated
  maintenance controller has requested access to service-related
  functionality. It is asserted during routine, expected maintenance windows
  and is not related to the reset tree.
- `alarm` reflects the current state of the system's alarm monitoring logic,
  independent of maintenance activity. It may be asserted due to a wide range
  of operating conditions unrelated to tamper detection or reset.

These two signals are expected to be used by other parts of the larger system
(outside the scope of this subsystem) for maintenance-mode gating and alarm
annunciation, respectively. Within the audit subsystem itself, they are not
part of the documented reset or clear path for `tamper_count`; the only signal
that should participate in clearing the counter is the synchronized form of
`rst_n`.

## Summary of Expected Behavior

1. `tamper_count` increments once per clock cycle in which `tamper_event` is
   asserted, wrapping at 255.
2. `tamper_count` is held at zero whenever `rst_n` is deasserted (via the
   internal reset synchronizer), and resumes counting once `rst_n` is
   reasserted.
3. `maintenance_req` and `alarm`, individually or in any combination, have no
   effect on the value or clearing of `tamper_count`.
4. The `audit_top` interface exposes only the ports listed above; internal
   implementation details (synchronizer stages, counter register
   implementation, etc.) are not part of the external contract but may be
   inspected in the accompanying netlist for verification purposes.