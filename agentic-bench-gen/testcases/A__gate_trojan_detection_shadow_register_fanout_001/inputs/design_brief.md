# Design Brief: Key Register Round-Combination Datapath

## Module

`trojan_netlist` — top-level structural module implementing a single-cycle
key/round-data combination stage.

## Purpose

This block holds an 8-bit key value in a register bank and combines it,
bit-by-bit, with an externally supplied round-data value using a simple
XOR round function. The combined result is exposed on the module's
primary output bus.

## Clocking and Reset

- `clk` — single system clock. All sequential elements in this module are
  positive-edge triggered on `clk`.
- `rst_n` — active-low asynchronous reset. All registers reset to zero
  when `rst_n` is deasserted.

## Ports

- `key_in[7:0]` (input) — the key value to be loaded into the key
  register bank on each clock edge.
- `round_data[7:0]` (input) — externally supplied round-function operand,
  combined with the stored key bits.
- `round_out[7:0]` (output) — the sole documented output of this module;
  the result of combining each key register bit with the corresponding
  round-data bit.

## Key Register Bank

The key register bank is an 8-bit array `key_reg[7:0]`, implemented as
eight single-bit flip-flop instances, one per bit:

- `u_key_ff0` samples `key_in[0]` into `key_reg[0]`
- `u_key_ff1` samples `key_in[1]` into `key_reg[1]`
- `u_key_ff2` samples `key_in[2]` into `key_reg[2]`
- `u_key_ff3` samples `key_in[3]` into `key_reg[3]`
- `u_key_ff4` samples `key_in[4]` into `key_reg[4]`
- `u_key_ff5` samples `key_in[5]` into `key_reg[5]`
- `u_key_ff6` samples `key_in[6]` into `key_reg[6]`
- `u_key_ff7` samples `key_in[7]` into `key_reg[7]`

Each of these flip-flops is clocked by `clk` and reset by `rst_n`.

## Round-Combination Stage

Each bit of `key_reg[7:0]` feeds exactly **one** consumer: a dedicated
two-input XOR gate instance that combines it with the corresponding bit
of `round_data[7:0]` to produce the corresponding bit of `round_out[7:0]`:

- `u_round_xor0` combines `key_reg[0]` and `round_data[0]` into `round_out[0]`
- `u_round_xor1` combines `key_reg[1]` and `round_data[1]` into `round_out[1]`
- `u_round_xor2` combines `key_reg[2]` and `round_data[2]` into `round_out[2]`
- `u_round_xor3` combines `key_reg[3]` and `round_data[3]` into `round_out[3]`
- `u_round_xor4` combines `key_reg[4]` and `round_data[4]` into `round_out[4]`
- `u_round_xor5` combines `key_reg[5]` and `round_data[5]` into `round_out[5]`
- `u_round_xor6` combines `key_reg[6]` and `round_data[6]` into `round_out[6]`
- `u_round_xor7` combines `key_reg[7]` and `round_data[7]` into `round_out[7]`

## Documented Topology Summary

- Each bit of `key_reg[7:0]` has a fanout of exactly **one**: the
  corresponding `u_round_xor<i>` instance.
- `round_out[7:0]` is the only output port of this module that depends on
  `key_reg[7:0]`.
- No other module output or internal instance is expected to be driven,
  directly or indirectly, by any bit of `key_reg[7:0]`.

This document describes the complete intended datapath for this module.
Any additional consumers of `key_reg[7:0]`, or any additional output ports
influenced by it, found during netlist review would represent a deviation
from this specification and should be reported.