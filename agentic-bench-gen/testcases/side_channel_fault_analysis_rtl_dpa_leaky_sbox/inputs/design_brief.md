# Design Brief: Single-Round Substitution/Permutation Datapath

## Overview

`round_datapath.v` implements one round of a small substitution-permutation
style block cipher round function operating on 8-bit data. It is intended
as a representative fragment of a larger multi-round cipher datapath, cut
down to a single round for focused analysis. The module is fully
synchronous, single-clock, with a synchronous active-high reset.

The round takes an 8-bit `plaintext` byte and an 8-bit `round_key` byte
each cycle and produces an 8-bit `round_out` byte, via a four-stage
register pipeline. Each stage of the pipeline is implemented as its own
always block driving a dedicated register, and the S-box lookup itself is
factored out into the separate combinational module `sbox_lut`
(`sbox_table.v`), which round_datapath.v instantiates.

## Pipeline stages and signals in scope

The following four registers make up the complete pipeline and are the
full set of signals in scope for this analysis. There are no other
clocked storage elements in the datapath.

| Signal          | Width | Functional description                                                                 |
|-----------------|-------|------------------------------------------------------------------------------------------|
| `plaintext_reg`  | 8-bit | Registers the raw `plaintext` input each cycle; the first pipeline stage, prior to any key involvement. |
| `key_mix_reg`    | 8-bit | Registers the bitwise XOR of `plaintext_reg` with `round_key`; this is the key-mixing stage. |
| `sbox_out_reg`   | 8-bit | Registers the output of the `sbox_lut` combinational lookup table applied to `key_mix_reg`. |
| `round_out_reg`  | 8-bit | Registers a linear diffusion step applied to `sbox_out_reg` (a fixed bit-rotation combined with an XOR); this stage is already balanced from a logic-design standpoint and drives the module's `round_out` output. |

All four registers are updated on every rising edge of `clk` and are held
at `8'h00` while `rst` is asserted.

## Analysis scope

Participants must evaluate **all four** of the registers listed above
against the Hamming-distance power model defined in `power_model.md`,
using the simulation traces produced by `testbench_hd_trace.v`. For each
signal, compute the `hd_variance` statistic as specified in
`power_model.md`, and report your findings — including which signals you
consider worth flagging and why, plus any hardening recommendations for
flagged signals — using the JSON schema described in `README.md`.

This brief does not prejudge which signals will turn out to show more or
less data-dependent switching activity than others; that determination is
the purpose of the analysis you are asked to perform. Your report should
be driven by the simulation data and the variance computation, not by
assumptions about the pipeline stages' roles.