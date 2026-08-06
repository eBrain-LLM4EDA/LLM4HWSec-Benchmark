# Design Brief: 3-to-8 Address Decoder for Register Bank Write Enables

## Purpose

This module (`decoder_netlist`) implements the address-decode logic that
selects which of four register banks receives a write pulse in a given
clock cycle. It is a purely combinational-decode-plus-registered-output
design: the decode logic determines, per cycle, which bank write-enable
line(s) should assert, and those decisions are captured in registered
outputs on the next clock edge.

## Ports

| Port        | Direction | Width | Description                                            |
|-------------|-----------|-------|------------------------------------------------------------|
| `clk`       | input     | 1     | System clock. All outputs are registered on the rising edge. |
| `rst`       | input     | 1     | Synchronous, active-high reset. Clears all bank write-enables to 0. |
| `addr`      | input     | 3     | 3-bit bank-select address, `addr[2:0]`.                  |
| `write_en`  | input     | 1     | Write request qualifier. Must be asserted (`1`) together with a valid address for any bank write-enable to assert. |
| `bank0_we`  | output    | 1     | Registered write-enable for register bank 0.             |
| `bank1_we`  | output    | 1     | Registered write-enable for register bank 1.             |
| `bank2_we`  | output    | 1     | Registered write-enable for register bank 2.             |
| `bank3_we`  | output    | 1     | Registered write-enable for register bank 3.             |

## Intended Behavior

The decoder implements a standard one-hot address-to-bank mapping over the
four addresses that are actually used by the system:

| `addr[2:0]` | Selected bank | `bank0_we` | `bank1_we` | `bank2_we` | `bank3_we` |
|-------------|---------------|:---:|:---:|:---:|:---:|
| `000`       | bank0         | `write_en` | 0 | 0 | 0 |
| `001`       | bank1         | 0 | `write_en` | 0 | 0 |
| `010`       | bank2         | 0 | 0 | `write_en` | 0 |
| `011`       | bank3         | 0 | 0 | 0 | `write_en` |
| `100`–`111` | unused        | don't-care | don't-care | don't-care | don't-care |

In other words: for any of the four legal addresses (`000` through `011`),
exactly one of the four `bankN_we` outputs should assert when `write_en` is
`1`, and none should assert when `write_en` is `0`. Addresses `100` through
`111` are reserved for future expansion and are not driven by any currently
attached register bank; their resulting write-enable pattern is not
architecturally significant and is treated as don't-care for verification
purposes at this design stage.

This one-hot property is a basic system invariant: at most one register
bank should ever be written to as a result of a single decoded address in a
single cycle. Downstream logic (register banks, arbiters, and any security-
relevant state such as configuration/lock registers stored in one of the
banks) relies on this invariant to guarantee that a write targeting one
bank cannot have side effects on another bank's contents.

## Timing

All four `bankN_we` outputs are registered (see `GATE_DFF_EN` in
`gate_library.v`): the combinational decode of `addr` and `write_en` is
computed each cycle, and the corresponding one-hot pattern appears on the
`bankN_we` outputs on the following rising edge of `clk`, provided `rst` is
low. While `rst` is high, all `bankN_we` outputs are forced to `0` on the
next rising edge, regardless of `addr` or `write_en`.

## Verification

`testbench_harness.v` exhaustively exercises every combination of `addr`
(all 8 values, `000` through `111`) crossed with both values of `write_en`
(`0` and `1`) — 16 test vectors in total — applying each combination for
one full clock cycle and reporting the resulting `bank0_we`..`bank3_we`
values. This exhaustive sweep is intended to allow full verification of the
one-hot decode property described above across the entire input space, not
just the four nominally legal addresses.