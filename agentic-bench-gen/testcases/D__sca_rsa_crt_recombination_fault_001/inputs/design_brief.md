# Design Brief: `crt_recombine` Two-Path Modular Recombination Datapath

## Purpose

`crt_recombine` is a compact, resource-constrained datapath module intended for embedded arithmetic co-processing applications where a modular reduction result must be produced through a decomposed, two-path computation rather than a single wide modular divider. This structure is useful in area-constrained designs where implementing a single large modulus reducer is more expensive than implementing two small independent reducers whose results are recombined.

The module demonstrates a small worked example using two fixed demonstration moduli, `p = 11` and `q = 13`, whose product is `143`. Given an 8-bit input value `msg_in` (assumed to lie in the range `0..142`), the module produces `result_out = msg_in mod 143` by computing two independent partial results — `msg_in mod p` and `msg_in mod q` — and combining them via a fixed weighted-sum recombination formula, rather than performing a direct reduction modulo 143 in one step.

This two-path structure is representative of a broader class of datapath designs in which a computation is split across parallel low-cost branches and merged at the end, trading a single expensive operation for two cheap ones plus a combination step.

## Ports

| Port | Direction | Width | Description |
|---|---|---|---|
| `clk` | input | 1 | System clock. |
| `rst_n` | input | 1 | Active-low, synchronous reset. |
| `start` | input | 1 | Single-cycle pulse that initiates one computation. Sampled only while the module is idle. |
| `msg_in` | input | 8 | Input value to be reduced/recombined. Assumed to be in the range `0..142` for a meaningful result. |
| `result_out` | output (reg) | 8 | Recombined result. Valid only on the cycle that `done` is asserted. |
| `done` | output (reg) | 1 | Pulses high for exactly one clock cycle to indicate that `result_out` is valid for the computation just completed. |

## Functional Behavior

1. The module is idle and waiting after reset, with `done` deasserted.
2. On observing `start` while idle, the module latches `msg_in` and begins a short internal computation sequence.
3. The first phase computes the branch-1 partial result, `msg_in mod p` (with `p = 11`), and stores it into an internal register.
4. The second phase computes the branch-2 partial result, `msg_in mod q` (with `q = 13`), and stores it into a second internal register.
5. The final phase combines the two stored branch results using a fixed CRT-style weighted-sum recombination formula, producing a value in the range `0..142`, and drives this onto `result_out`.
6. On the same cycle that `result_out` becomes valid, `done` is pulsed high for exactly one cycle. The module then returns to idle and is ready to accept the next `start` pulse.

## Timing

- `start` should be held low except for the single cycle used to initiate a computation; it is only recognized while the module is idle.
- The computation occupies a small, fixed number of clock cycles per `start` pulse (on the order of a handful of cycles), reflecting the multi-phase branch-then-recombine structure described above.
- `done` is combinatorially aligned with the cycle on which `result_out` holds its final, valid value; consumers of this module should sample `result_out` on the same cycle `done` is observed high.
- The module does not accept a new `start` pulse until the current computation has completed and `done` has been observed.

## Intended Usage

`crt_recombine` is intended to be instantiated as a small arithmetic helper block within a larger embedded control or signal-processing pipeline where an occasional modular-reduction result is needed and area is at a premium. A companion reference implementation, `crt_reference`, computes the identical input/output function via a single direct modular-reduction path and is provided as a cross-checking oracle for verification and simulation purposes, so that the two-path implementation's output can be validated against a straightforward, non-decomposed computation on the same input vectors.