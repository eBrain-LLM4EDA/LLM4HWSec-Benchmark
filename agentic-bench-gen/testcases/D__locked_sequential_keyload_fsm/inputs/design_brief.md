# Design Brief: Sequential Lock with Key-Loaded Initial State

## Overview

The circuit `top` is a small sequential design that implements a serial key-loading lock. Before the circuit can perform its intended data-processing function, a specific 4-bit key must be applied one bit at a time on the `key_in` port over four consecutive clock cycles, starting after the asynchronous reset is de-asserted.

## Port Description

| Port      | Direction | Width | Description                              |
|-----------|-----------|-------|------------------------------------------|
| `clk`     | input     | 1     | Clock signal (rising-edge triggered)     |
| `rst_n`   | input     | 1     | Active-low asynchronous reset            |
| `key_in`  | input     | 1     | Serial key input (one bit per cycle)     |
| `data_in` | input     | 1     | Data input                               |
| `data_out`| output    | 1     | Data output                              |

## Functional Behavior

- **Reset**: When `rst_n` is low, the circuit is held in an idle state and all internal state is cleared.
- **Key Loading**: After `rst_n` goes high, the circuit enters a loading phase. On each of the next four rising clock edges, the value present on `key_in` is shifted into an internal shift register. The order of loading is serial: the first bit after reset is loaded into the least-significant position, and subsequent bits are shifted in.
- **Key Verification**: After the fourth key bit has been loaded, the circuit compares the complete 4-bit pattern against a hardcoded expected value.
  - If the pattern matches, the circuit transitions to **functional mode**.
  - If the pattern does not match, the circuit enters a **decoy mode**.
- **Functional Mode**: In functional mode, `data_out` follows `data_in` (the intended function).
- **Decoy Mode**: In decoy mode, the circuit produces a deterministic but non-functional output that does not correspond to the intended data processing. Once in decoy mode, the circuit remains there until a reset is applied.
- **Stability**: Both functional and decoy modes are stable; once entered, the circuit stays in that mode regardless of further changes on `key_in`.

## Notes for Analysis

- The netlist is provided in `locked_fsm.v` and is synthesizable, compiling cleanly with standard Verilog tools.
- The oracle traces in `oracle_traces.txt` show the circuit's behavior when the correct key sequence is applied, including the transition into functional mode and subsequent functional operation.
- The key sequence is exactly 4 bits long. The internal shift register and state machine are implemented with standard D-type flip-flops.
- Your task is to determine the correct key sequence and identify the hierarchical names of the four flip-flops that hold the key bits during loading.