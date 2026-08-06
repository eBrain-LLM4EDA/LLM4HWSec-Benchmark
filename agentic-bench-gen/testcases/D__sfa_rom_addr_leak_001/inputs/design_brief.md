# Design Brief: `subst_lookup` Module

## Purpose

`subst_lookup` implements a small keyed substitution/permutation lookup stage used inside a compact cipher datapath. Each clock cycle, the surrounding datapath presents a nibble-position selector and a per-session key nibble, and the module returns the substituted nibble value for that combination one cycle later.

## Context in the Datapath

The parent cipher datapath processes data in fixed-width nibble slices across several rounds. For each round, an upstream controller steps through the nibble positions of the current block and, for each position, drives:

- `public_index` — identifies which nibble position (0-15) within the current round is being processed. This value comes from a round counter/sequencer in the surrounding datapath and cycles through all 16 positions as the round is processed.
- `secret_key` — the key nibble associated with the current session, supplied by the key-scheduling logic upstream of this module. It stays fixed for the duration of the operation being reviewed here.

The module combines these two into an internal lookup index and returns the corresponding substitution value on `table_data`, which is consumed by the next pipeline stage (e.g., a mix/diffusion block) later in the round.

## Interface

```
module subst_lookup(
    input  wire       clk,
    input  wire       rst_n,
    input  wire [3:0] public_index,
    input  wire [3:0] secret_key,
    output wire [3:0] table_data
);
```

- `clk` — the single system clock driving all sequential logic in this module.
- `rst_n` — active-low, synchronous reset. While asserted low, the module's internal pipeline register clears to zero on the next rising edge of `clk`.
- `public_index` — 4-bit nibble-position selector, updated by the upstream sequencer every cycle (or as needed by the surrounding control logic).
- `secret_key` — 4-bit key nibble, held constant by the upstream key schedule for the duration of a given operation.
- `table_data` — 4-bit substituted output nibble, valid one cycle after the corresponding `public_index`/`secret_key` pair was presented.

## Internal Pipeline Stage

Functionally, the module is organized as a two-stage pipeline:

1. **Index combine (combinational).** `public_index` and `secret_key` are combined into an internal lookup index. This combining step is purely combinational and has no registered state of its own.
2. **Register (sequential, one cycle).** The combined index is captured into an internal register on the rising edge of `clk`. This register is cleared to zero whenever `rst_n` is low at the clock edge, and otherwise takes on the combined index value from stage 1. This is the only clocked storage element in the module.
3. **ROM lookup (combinational).** The registered index from stage 2 selects one of sixteen fixed substitution values from an internal lookup table. The selected value is presented on `table_data`.

## Timing

- `table_data` reflects the substitution result for the `public_index`/`secret_key` pair that was present at the module's inputs exactly one clock cycle earlier.
- There is no combinational path directly from `public_index` or `secret_key` to `table_data` within the same cycle; the one-cycle register in the middle of the pipeline sets the latency for the whole stage.
- The upstream sequencer must account for this one-cycle latency when pairing `table_data` with the round-processing logic that consumes it (e.g., by delaying its own control signals by one cycle to stay aligned with the substituted output).

## Functional Requirements Summary

- For every combination of `public_index` and `secret_key`, after the one-cycle pipeline latency, `table_data` must equal the fixed substitution table's entry at the position given by combining those two inputs.
- The lookup table itself is a fixed 16-entry permutation of the values 0 through 15 and does not change based on any runtime input; it is a static property of this module's implementation.
- Reset behavior: asserting `rst_n` low for at least one clock edge forces the internal pipeline register to zero, which in turn selects lookup-table entry zero for `table_data` on the following cycle (until new index values propagate through).

## Review Focus

A reviewer examining this module for correctness and integration purposes should confirm: (1) the one-cycle latency between input presentation and `table_data` validity, (2) correct reset behavior of the internal pipeline register, and (3) that the internal lookup table matches the fixed permutation specified for this cipher variant.