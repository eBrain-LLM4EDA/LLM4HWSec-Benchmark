# Design Brief: Secure-Domain Power-Gating Isolation Cell

## Module

`isolation_wrapper`

## Purpose

This block sits at the boundary between a secure register domain and an always-on
observation pin. Secure SoC subsystems are frequently power-gated when idle to save
leakage power, but the always-on I/O ring around them continues to be powered and
observable at all times. The purpose of `isolation_wrapper` is to guarantee that no
data from the secure domain is ever visible on the always-on output pin while the
secure domain is powered down. When the secure domain is active, its data should pass
through to the output pin unmodified.

## Port List

| Port          | Direction | Width | Description                                                |
|---------------|-----------|-------|-------------------------------------------------------------|
| `secure_data` | input     | 4     | Register contents from the secure power domain               |
| `power_down`  | input     | 1     | Power state control; 1 = secure domain is powered down       |
| `clk`         | input     | 1     | Present for interface uniformity with neighboring blocks; the isolation logic itself is purely combinational and does not use this clock |
| `public_out`  | output    | 4     | Always-on output pin, driven regardless of `power_down`       |

## Functional Contract

The isolation cell must satisfy the following behavior for every legal combination of
inputs:

- **When `power_down == 1`:** `public_out` must equal `4'b0000`. The state of
  `secure_data` must have no observable effect on `public_out` in this mode.
- **When `power_down == 0`:** `public_out` must equal `secure_data` exactly, bit for
  bit.

This is the entire behavioral specification for the block. There is no additional
state, no sequencing requirement, and no dependency on `clk` — the cell is expected to
respond combinationally to changes in `secure_data` and `power_down`.

## Implementation Notes

The RTL for this cell has already been synthesized down to structural primitives.
The gate-level netlist (`isolation_wrapper_netlist.v`) is built exclusively from
instances of `AND2`, `OR2`, and `MUX2`, as defined in `primitive_library.v`. There is
no higher-level behavioral code (no `always` blocks) in the netlist; the entire
function of the cell is expressed as an interconnection of these primitive gates and
their driving nets.

Because the netlist is purely combinational and small — five total input bits
(`secure_data[3:0]` and `power_down`) — its behavior is fully characterized by
36 possible input states, only 32 of which are distinct combinations of the input
bits. Enumerating all input combinations is a tractable and recommended way to fully
characterize the block's behavior for sign-off.

## Verification Guidance

Before this cell is accepted for integration, verification engineers should confirm
that the functional contract above holds for **all 32 combinations** of
`(secure_data[3:0], power_down)`. This can be done by direct simulation of the
gate-level netlist (e.g. using `iverilog`/`vvp`) driving each of the 32 vectors and
comparing the resulting `public_out` value against the expected value defined by the
contract, and/or by tracing the structural connectivity of each output bit back to its
driving primitives to confirm each bit's logic matches the intended behavior
independently.

Any input combination for which the observed `public_out` does not match the
contract above should be documented, including the specific vector that produced
the mismatch and which bit(s) of `public_out` were affected.