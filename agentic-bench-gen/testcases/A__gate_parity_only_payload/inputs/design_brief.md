# Design Brief — Parity Data Path

## Overview

The circuit `top` is a simple 8‑bit data path that computes the parity of an input byte and asserts a `parity_error` output when the parity is odd.

## Inputs and Outputs

| Signal | Direction | Width | Description |
|--------|-----------|-------|-------------|
| `data_in` | input | 8 | Data byte whose parity is checked. |
| `parity_error` | output | 1 | Asserted high (1) when the number of 1‑bits in `data_in` is odd; low (0) when the number of 1‑bits is even. |

## Functional Behaviour

The circuit implements a standard even‑parity checker:

- The eight bits of `data_in` are XORed together to produce an internal parity result.
- If the parity result is 1 (odd number of ones), `parity_error` is driven to 1.
- If the parity result is 0 (even number of ones), `parity_error` is driven to 0.

The design is purely combinational; the output responds immediately to changes on `data_in`.

## Intended Use

This module is intended to be part of a larger system where data integrity is monitored. Downstream logic can use the `parity_error` signal to detect single‑bit errors in the data byte and take appropriate action (e.g., request retransmission or flag a fault).

## Implementation Notes

- The netlist is built entirely from primitive logic gates (`and`, `or`, `not`, `nand`, `nor`, `xor`, `xnor`, `buf`).
- The hierarchy is flat; all gates are instantiated at the top level.
- The testbench (`design_tb.v`) provides a set of input vectors that exercise both even‑ and odd‑parity cases.