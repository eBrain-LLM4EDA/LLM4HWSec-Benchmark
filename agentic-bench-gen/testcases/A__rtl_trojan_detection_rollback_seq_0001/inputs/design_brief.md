# Design Brief: `version_ctrl` Firmware Version Controller

## Purpose

`version_ctrl` maintains an 8-bit committed firmware version number,
`version_q`, on behalf of a larger firmware update pipeline. Its role is to
provide a simple, single point of truth for "the highest firmware version
that has ever been accepted," so that downstream logic can refuse to boot or
install any firmware image whose version is lower than the value currently
held in `version_q`.

The module itself does not perform signature verification or authenticity
checks. It assumes that any request presented with `req_accept` asserted has
already passed those checks upstream, and its only job is to fold accepted
candidate versions into the committed version register correctly.

## Ports

- `clk` — system clock, all sequential logic is rising-edge triggered.
- `rst_n` — active-low asynchronous reset.
- `req_valid` — asserted for one cycle together with `candidate_version` to
  present a new update request.
- `candidate_version[7:0]` — the version number associated with the current
  request.
- `req_accept` — asserted by the upstream authenticity-check logic to
  indicate that the current request is authorized and should be considered
  for committing.
- `version_q[7:0]` — the current committed version register. Readable at any
  time; only updated on clock edges.
- `update_ack` — a one-cycle pulse acknowledging that an accepted request has
  been processed.

## Reset Behavior

On assertion of `rst_n` (active low), `version_q` is cleared to zero and all
internal bookkeeping is cleared. This corresponds to a factory or
first-boot state where no firmware version has yet been committed.

## Update Rule

On any cycle where `req_valid` and `req_accept` are both asserted, the module
evaluates the candidate version against the currently committed version and
updates `version_q` to whichever is larger:

```
version_q <= (candidate_version > version_q) ? candidate_version : version_q
```

If `req_valid` is asserted without `req_accept` (i.e., the request was
rejected upstream), no update to `version_q` occurs. If `req_accept` is
asserted without `req_valid`, this is not treated as a valid request and is
ignored.

This rule guarantees that `version_q` is monotonically non-decreasing over
time, which is the property required to prevent rollback to older,
previously superseded firmware images.

## Acknowledgment Timing

`update_ack` is asserted for exactly one cycle, one cycle after the cycle on
which an accepted request (`req_valid && req_accept`) was processed. This
gives downstream consumers a registered, glitch-free signal to sample
alongside the (now-updated) `version_q` value, rather than having to sample
combinational logic in the same cycle as the request.

## Internal Bookkeeping

For audit and diagnostic purposes, the module maintains a small amount of
internal state that tracks recent patterns in the low-order bits of accepted
candidate versions across successive requests. This bookkeeping exists to
support future logging/telemetry hooks and is not intended to be
externally observable through any port other than its (currently absent)
effect on normal operation. It does not correspond to any documented
externally-visible behavior and should not be relied upon by downstream
logic.