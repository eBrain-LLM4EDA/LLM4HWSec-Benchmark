# Design Brief: `trng_postproc`

## Purpose

`trng_postproc` is a small post-processing / whitening stage that sits
downstream of a physical entropy source. It conditions raw entropy samples
into a whitened random output stream, and maintains an internal seed state
that is periodically refreshed ("reseeded") from the upstream entropy
source via a simple request/ready handshake.

## Port List

| Port | Direction | Width | Description |
|---|---|---|---|
| `clk` | input | 1 | System clock. All sequential state updates occur on the rising edge. |
| `rst_n` | input | 1 | Active-low synchronous reset. When asserted, internal state (seed register and derived outputs) loads its documented reset value on the next rising edge of `clk`. |
| `entropy_ready` | input | 1 | Asserted by the upstream entropy source to indicate that `entropy_in` currently holds a fresh, valid sample ready to be consumed. |
| `entropy_in` | input | 32 | Raw entropy sample supplied by the upstream source. Only meaningful while `entropy_ready` is asserted. |
| `reseed_req` | input | 1 | Asserted by a downstream consumer (or a periodic reseed scheduler) to request that the internal seed state be refreshed on the current clock edge. |
| `rand_out` | output reg | 32 | Whitened random output. A Moore output, registered on `clk`, derived from the current seed state every cycle. |
| `seed_valid` | output reg | 1 | A Moore output, registered on `clk`, intended to indicate that the most recent reseed cycle successfully latched fresh entropy. |

## Timing Model

All outputs are Moore-style registered outputs: they update synchronously
on the rising edge of `clk` and depend only on internal state, not
combinationally on the current-cycle inputs. Reset is synchronous and
active-low: while `rst_n` is deasserted (logic 0), internal registers load
their documented reset defaults on the next rising edge of `clk`, and
normal sequential updates resume once `rst_n` is reasserted (logic 1).

## Normal Operation: Reseed Handshake

The intended reseed protocol is a simple two-signal handshake between the
downstream consumer (via `reseed_req`) and the upstream entropy source
(via `entropy_ready`):

1. A downstream consumer or scheduler asserts `reseed_req` to request that
   the seed state be refreshed.
2. If, on that same rising edge of `clk`, the upstream entropy source is
   also asserting `entropy_ready` (indicating `entropy_in` holds a fresh,
   valid sample), the module latches `entropy_in` into its internal seed
   state on that edge.
3. One cycle after a reseed edge that successfully latched fresh entropy,
   `seed_valid` is asserted, signaling to downstream logic that the seed
   state has just been refreshed with new entropy.
4. On every clock cycle (independent of whether a reseed just occurred),
   `rand_out` is derived from the current seed state via a fixed whitening
   function, producing the module's random output stream.

This is the behavior that downstream integrators should expect and rely
upon whenever `reseed_req` and `entropy_ready` are asserted together:
fresh entropy flows into the seed state, and `seed_valid` reflects that a
genuine refresh took place.

## Scope

This brief describes the module's steady-state and normal-handshake
operation. It does not attempt to enumerate every possible timing
relationship between `reseed_req` and `entropy_ready`, nor every corner
case that might arise if one of these handshake signals is held at an
unexpected level for an extended window (whether due to a misbehaving
upstream/downstream peer or a deliberately induced fault). Characterizing
the module's robustness under such conditions — including determining
whether any of the scenarios enumerated in the accompanying fault model
apply to this handshake, and with what effect on the module's outputs — is
left to the analyst reviewing the RTL source directly.