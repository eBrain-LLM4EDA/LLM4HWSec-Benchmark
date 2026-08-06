# Design Brief: scan_controller

## Overview

The `scan_controller` module is a gate-level implementation of a simple scan-chain controller used for design-for-test (DFT) purposes. It allows external test equipment to shift test patterns into and out of a 4-bit register chain while the device is in test mode.

## Interface

| Port       | Direction | Width | Description                                      |
|------------|-----------|-------|--------------------------------------------------|
| `clk`      | input     | 1     | Clock signal (positive edge triggered)           |
| `rst_n`    | input     | 1     | Asynchronous reset (active low)                  |
| `test_mode`| input     | 1     | Test mode enable (1 = test mode, 0 = functional) |
| `scan_in`  | input     | 1     | Serial scan input                                |
| `data_in`  | input     | 4     | Parallel functional data input                   |
| `data_out` | output    | 4     | Parallel functional data output                  |
| `scan_out` | output    | 1     | Serial scan output                               |

## Functional Description

### Functional Mode (`test_mode = 0`)

When `test_mode` is low, the module operates as a simple 4-bit register:

- The `scan_enable` signal is driven low, which selects the `data_in` port at each scan multiplexer.
- On each rising edge of `clk`, the value on `data_in` is captured into the internal flip-flops.
- The captured value appears on `data_out` after the clock edge.
- The `scan_in` and `scan_out` ports are not used in this mode; the scan chain is isolated from the functional path.

### Test Mode (`test_mode = 1`)

When `test_mode` is high, the module enters scan shift mode:

- `scan_enable` is driven high, selecting the scan chain path at each multiplexer.
- The four flip-flops are connected as a serial shift register:
  - `scan_in` → DFF0 → DFF1 → DFF2 → DFF3 → `scan_out`
- On each clock cycle, the scan chain shifts by one position: the value at `scan_in` is loaded into the first flip-flop, and the previous contents shift toward `scan_out`.
- The `data_in` port is ignored during scan shifting.

## Implementation Details

The netlist is constructed entirely from primitive logic gates (AND, OR, NOT, NAND, NOR, XOR, XNOR, BUF) and D-type flip-flops (DFF). The scan multiplexers are implemented as 2-to-1 MUX primitives controlled by the `scan_enable` signal, which is a buffered version of `test_mode`.

The design exhibits naturally low switching activity on the `test_mode` and `scan_enable` nets during functional operation, as these signals remain static at logic 0. This is a typical characteristic of DFT control logic and does not indicate any abnormal behavior.

## Usage Notes

- The module is intended for integration into larger designs that require scan-based testing.
- In functional mode, the scan chain is completely transparent to normal operation.
- The asynchronous reset (`rst_n`) initializes all flip-flops to 0 when asserted low, regardless of mode.