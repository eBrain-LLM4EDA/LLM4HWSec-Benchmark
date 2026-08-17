# Design Brief — Scalar Multiplication Controller

## Purpose

This module pair implements a compact "double-and-add" scalar
multiplier for a toy elliptic-curve-like point representation. Given
a 16-bit scalar and an implicit fixed base point, the controller
computes a scalar multiple of that base point by sequencing a series
of DOUBLE and ADD operations over a shared field datapath, and
presents the resulting point coordinates on its output ports.

The design is split into two modules:

- `scalar_mult_ctrl.v` — the top-level controller / finite state
  machine that sequences operations bit-by-bit over the scalar and
  manages the running accumulator.
- `field_datapath.v` — the shared multi-cycle execution unit that
  performs the actual DOUBLE and ADD arithmetic on 64-bit coordinate
  pairs.

## Interface — `scalar_mult_ctrl`

| Port | Direction | Width | Description |
|---|---|---|---|
| `clk` | input | 1 | System clock. |
| `rst_n` | input | 1 | Active-low, synchronous reset. |
| `start` | input | 1 | One-cycle pulse asserted while the controller is idle to begin processing a new scalar. |
| `scalar` | input | 16 | The value to process. Bit 15 is processed first, bit 0 last (MSB-first). |
| `done` | output (reg) | 1 | Moore output, asserted for exactly one cycle when processing of the final bit has completed. |
| `result_x` | output (reg) | 64 | Resulting point's X coordinate. Valid the same cycle `done` is high, and held until the next completed run. |
| `result_y` | output (reg) | 64 | Resulting point's Y coordinate. Valid the same cycle `done` is high, and held until the next completed run. |
| `state` | output (reg) | 3 | Debug/analysis-only: current control state, updated every cycle. Not part of the production interface. |
| `cycle_count` | output (reg) | 16 | Debug/analysis-only: running count of clock cycles elapsed since `start` was asserted; latched (holds its final value) once `cycle_count_valid` pulses. |
| `cycle_count_valid` | output (reg) | 1 | Debug/analysis-only: asserted for exactly one cycle, coincident with `done`, indicating `cycle_count` reflects the total cycles for that run. |

The `state`, `cycle_count`, and `cycle_count_valid` ports exist purely
to make the controller's behavior observable in simulation and testing
environments; they carry no functional role in the production
interface and may be left unconnected in a system integration.

## Interface — `field_datapath`

| Port | Direction | Width | Description |
|---|---|---|---|
| `clk` | input | 1 | System clock. |
| `rst_n` | input | 1 | Active-low, synchronous reset. |
| `op_start` | input | 1 | One-cycle pulse requesting a new operation. |
| `op_is_add` | input | 1 | Sampled at `op_start`: `0` selects DOUBLE, `1` selects ADD. |
| `in_x`, `in_y` | input | 64 each | Input point coordinates for the operation. |
| `add_x`, `add_y` | input | 64 each | Second operand coordinates, used only when `op_is_add` is `1`. |
| `out_x`, `out_y` | output (reg) | 64 each | Result coordinates, valid the cycle `op_done` pulses. |
| `op_done` | output (reg) | 1 | One-cycle pulse indicating `out_x`/`out_y` are valid for the just-completed operation. |

`field_datapath` accepts one operation request at a time and must
return to idle (signaled by `op_done`) before a new `op_start` pulse is
issued.

## Controller state machine overview

The controller processes the 16-bit scalar one bit index at a time,
starting at bit index 15 and finishing at bit index 0. For each bit
index it performs the following sequence:

1. **IDLE** — waits for `start`. On `start`, the accumulator is
   initialized, the bit index is set to 15, and a DOUBLE operation is
   issued for that bit index.
2. **DOUBLE** — a DOUBLE operation is always performed on the running
   accumulator for every bit index, regardless of the scalar's value
   at that index. When the datapath signals completion, the
   accumulator is updated with the DOUBLE result.
3. **ADD (conditional)** — after the DOUBLE completes, an ADD
   operation combining the accumulator with the fixed base point is
   performed only for bit indices where the corresponding scalar bit
   equals 1. When the scalar bit at the current index equals 0, this
   step is skipped and the controller proceeds directly to advancing
   the bit index.
4. **Advance bit index** — the bit index is decremented and a new
   DOUBLE operation is issued for the next bit index, repeating steps
   2–3, until bit index 0 has been processed.
5. **DONE** — once bit index 0's operations are complete, the final
   accumulator value is presented on `result_x`/`result_y`, and `done`
   pulses for one cycle. The controller then returns to IDLE, ready
   for the next `start`.

## Datapath latency notes

`field_datapath` models each operation kind with a distinct,
multi-cycle latency so that DOUBLE and ADD are clearly distinguishable
in a cycle-level trace:

- **DOUBLE** operations take 3 clock cycles from the cycle `op_start`
  is asserted to the cycle `op_done` pulses.
- **ADD** operations take 4 clock cycles from the cycle `op_start`
  is asserted to the cycle `op_done` pulses, reflecting the more
  complex combination of two point representations.

Both operation latencies are constant for a given operation kind —
every DOUBLE takes the same number of cycles as every other DOUBLE,
and likewise for ADD. The arithmetic performed by each operation is a
simplified, deterministic placeholder update (modular combination of
the input coordinates) chosen so that results are easy to reproduce
and check against a reference computation; it is not intended to
model a specific real-world curve.

Because both `scalar_mult_ctrl` and `field_datapath` are simple,
fully-synchronous designs with fixed per-operation latencies, the
exact number of clock cycles consumed by a complete run for a given
scalar can be determined precisely by simulating the two modules
together (e.g. with `iverilog`/`vvp`) and observing `cycle_count` when
`cycle_count_valid` pulses, rather than by estimating it analytically.

## Summary

Overall, one run of `scalar_mult_ctrl` from `start` to `done` consists
of exactly 16 DOUBLE operations (one per bit index) interleaved with
some number of ADD operations, one for each scalar bit that is set to
1. The total number of clock cycles a given run takes is therefore
determined by how many DOUBLE and ADD operations were issued during
that run, plus the fixed per-bit control overhead of the surrounding
state machine (state transitions between DOUBLE, ADD, and advancing to
the next bit index each consume their own clock cycles in addition to
the datapath's own busy cycles). Simulating the provided RTL directly
is the most reliable way to obtain exact cycle counts for any given
scalar.