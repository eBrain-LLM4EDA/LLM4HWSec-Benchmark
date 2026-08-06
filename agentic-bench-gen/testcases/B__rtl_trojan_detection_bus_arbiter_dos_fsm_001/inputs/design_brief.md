# Design Brief: 4-Master Bus Arbiter

## Purpose

This document describes the intended behavior of the `bus_arbiter` module
for reviewers who are validating the implementation in
`inputs/bus_arbiter.v` against its specification.

## System Overview

The arbiter mediates access to a single shared bus among four bus masters,
numbered 0 through 3. Each master signals a request for the bus by driving
its corresponding bit of the `req[3:0]` input high. The arbiter grants the
bus to at most one master at a time via the one-hot `gnt[3:0]` output, and
signals that a grant is currently outstanding via the `busy` output.

## Arbitration Policy

The arbiter implements round-robin priority arbitration:

1. When idle (no grant outstanding) and one or more masters assert `req`,
   the arbiter grants the bus to the lowest-numbered requesting master.
2. While a grant is outstanding, `busy` is asserted.
3. On the cycle following a grant, the arbiter checks for further pending
   requests:
   - If another master (higher index, wrapping around as needed) is
     requesting, the arbiter rotates the grant to that master, maintaining
     round-robin fairness rather than always favoring master 0.
   - If no other requests are pending, the arbiter returns to the idle
     state and deasserts `busy`.
4. Each master is expected to hold `req` asserted only as long as it needs
   the bus, and to deassert it once its transaction completes.

## State Set

The design is documented as a five-state finite state machine:

| State  | Meaning                                   |
|--------|--------------------------------------------|
| IDLE   | No grant outstanding; waiting for requests |
| GRANT0 | Master 0 currently holds the bus           |
| GRANT1 | Master 1 currently holds the bus           |
| GRANT2 | Master 2 currently holds the bus           |
| GRANT3 | Master 3 currently holds the bus           |

From any `GRANTi` state, the FSM is expected to either move to `IDLE`
(no further requests) or to another `GRANTj` state (round-robin rotation
to the next pending requester), every cycle, indefinitely, for as long as
the system runs. There is no notion in the specification of a state that
is not eventually followed by servicing a request when one is pending.

## Reset Behavior

`rst_n` is an active-low, asynchronous reset. When asserted (driven low),
the arbiter must immediately return to `IDLE`, deassert all `gnt` bits,
and deassert `busy`, regardless of the current state or clock edge.

## `busy` Signal Semantics

`busy` is intended purely as a status flag indicating "a grant is
currently outstanding." It should be asserted in every `GRANTi` state and
deasserted in `IDLE`. It is not intended to ever remain asserted
indefinitely while `gnt` is all-zero — that combination would mean the
arbiter believes it has granted the bus to someone, yet no master is
actually being serviced.

## Review Request

As part of sign-off for this design, please perform a liveness/robustness
review of the finite-state machine as actually implemented (not merely as
summarized in the table above). Specifically:

- Confirm that every state reachable from `IDLE` under some sequence of
  `req` values can, for every possible subsequent `req` pattern, either
  service a pending master or return to `IDLE`.
- Confirm there is no reachable state that acts as an unintended
  "terminal" or "absorbing" condition — i.e., a state from which the
  design implemented in RTL provides no legitimate path back to granting
  service to any master, for any future `req` value, short of a full
  system reset.
- If such a condition exists, document precisely which state it is, the
  exact signal conditions (state, `req`, `gnt`, `busy`) required to reach
  it, and its effect on subsequent bus operation.

This review should be grounded in the actual `case` statements and state
encodings present in `inputs/bus_arbiter.v`, since the RTL is the
authoritative implementation being signed off, not this brief.