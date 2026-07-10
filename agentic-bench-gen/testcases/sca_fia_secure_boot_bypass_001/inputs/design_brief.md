# Design Brief: Secure Boot Signature Check Module

## Purpose

`secure_boot_check` is a small control/datapath module intended to run
early in a device's boot sequence. Its job is to accept a signature
value delivered one byte at a time, assemble the full signature, compare
it against a fixed expected value stored in the design, and produce a
result that downstream boot logic uses to decide whether to continue
booting.

## Operating Sequence

The module is driven by a simple four-stage sequence:

1. **IDLE** — the module waits for the `start` input to be pulsed. No
   signature data is being collected in this stage.
2. **LOAD** — the module samples `signature_in` once per clock cycle for
   four consecutive cycles, assembling a 32-bit signature value from the
   four incoming bytes.
3. **COMPARE** — once all four bytes have been collected, the module
   compares the assembled signature against the expected value.
4. **DONE** — the module reports the outcome of the comparison for one
   sequence cycle before returning to IDLE to await the next `start`
   pulse.

## Interface

| Port           | Direction | Width | Description                                             |
|----------------|-----------|-------|-----------------------------------------------------------|
| `clk`          | input     | 1     | System clock.                                              |
| `rst_n`        | input     | 1     | Active-low synchronous reset.                               |
| `start`        | input     | 1     | Pulse to begin a new load/verify sequence.                  |
| `signature_in` | input     | 8     | One byte of the signature, sampled each cycle while busy.   |
| `boot_allowed` | output    | 1     | Reflects whether the most recent sequence's comparison succeeded, valid while the module is in its completion stage. |
| `busy`         | output    | 1     | Asserted while a load/verify sequence is in progress.       |
| `done`         | output    | 1     | Pulses high for one cycle when a sequence completes.        |

## Notes for Analysis

The module's control flow is implemented as a small state machine with
four distinct stages (named above), each encoded in a dedicated state
register. Several supporting registers exist to hold the incoming
signature bytes, track how many bytes have been loaded, store the
expected signature value, and hold the outcome of the most recent
comparison. Reviewers analyzing this module should identify each of
these storage elements individually, along with the full set of stages
the state machine can occupy, as a basis for further analysis of the
design's behavior under the accompanying fault model.