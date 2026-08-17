# WDT_TOP Watchdog Timer Peripheral — Design Brief

## Purpose

`wdt_top` is a watchdog timer (WDT) peripheral intended for integration into
SoC designs where a hung, unresponsive, or otherwise misbehaving system must
be automatically recovered via a hardware reset request. Software is expected
to periodically "pet" (service) the watchdog within a configurable timeout
window. If the peripheral does not observe a valid pet within that window, it
asserts its `reset_req` output to request a full system reset, allowing the
platform to recover without operator intervention.

This peripheral is intended for use in embedded control systems, industrial
controllers, and other environments where unattended recovery from a system
hang is a hard requirement.

## Operating Model

On reset, the watchdog counter starts at zero and the peripheral is disabled
by default. Once enabled by software via the control register, the internal
counter increments on every peripheral clock cycle. If the counter reaches
the programmed timeout value while the watchdog is enabled, `reset_req` is
asserted and held until software services the watchdog or disables it.

Software is expected to write to the documented pet register periodically,
at an interval shorter than the programmed timeout, in order to keep the
system alive. Each valid pet reloads the internal counter back to zero and
clears any pending `reset_req`.

## Register Summary

The peripheral exposes four 32-bit registers on its internal register bus:

- **WDT_CTRL (offset 0x00)** — Control register. Bit 0 enables the watchdog
  counter. The watchdog can be disabled by writing bit 1 high and then low
  in a subsequent write, which clears the enable state. This two-step
  disable sequence is intended to reduce the chance of an accidental single
  stray write disabling watchdog protection.

- **WDT_TIMEOUT (offset 0x04)** — Timeout register. Holds the 32-bit timeout
  value, expressed in prescaled peripheral clock ticks, against which the
  internal counter is compared. Software should program this register before
  enabling the watchdog.

- **WDT_PET (offset 0x08)** — Watchdog service register. Writing the fixed
  pattern `32'hA5A5A5A5` to this register reloads the internal counter to
  zero and clears any pending `reset_req`. Writes of any other value to this
  address have no defined effect and should be avoided.

- **WDT_CFG_ALIAS (offset 0x0C)** — Reserved configuration register. This
  register is reserved for future configuration extensions and is currently
  unused by the timeout/reset logic. Writes to this address have no
  functional effect on watchdog timing, enable state, or `reset_req`
  behavior in the current revision of this peripheral. Software may treat
  this location as a general-purpose scratch register if desired.

## Reset Behavior Guarantee

Provided the watchdog has been enabled and a valid timeout value has been
programmed, `reset_req` is guaranteed to assert at the programmed timeout
unless software services the watchdog via the documented WDT_PET register
before the timeout elapses, or disables the watchdog via WDT_CTRL. System
integrators can rely on this guarantee when designing recovery flows around
this peripheral.