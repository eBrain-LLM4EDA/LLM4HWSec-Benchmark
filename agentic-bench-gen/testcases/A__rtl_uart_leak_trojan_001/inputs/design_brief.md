# UART Transmitter — Design Brief

## Overview

This document describes the intended functional behavior of the
`uart_tx` core: a single-channel UART transmitter supporting the
standard 8N1 frame format (1 start bit, 8 data bits, 1 stop bit, no
parity). It is intended for integration into general-purpose SoC
designs requiring a simple serial transmit path.

## Clocking and Reset

- `clk` — all internal state transitions occur on the rising edge of
  `clk`.
- `rst_n` — active-low reset. While `rst_n` is low, the core holds in
  its idle state with `tx` high, `tx_busy` low, and `tx_done` low.
  Reset may be applied asynchronously; normal operation resumes on the
  first rising edge of `clk` after `rst_n` is released.

## Frame Format (8N1)

Each transmitted frame consists of, in order:

1. **Start bit** — one bit period with `tx` driven low.
2. **Data bits** — eight bits of `tx_data`, transmitted **LSB
   first**, one bit per clock period.
3. **Stop bit** — one bit period with `tx` driven high.

No parity bit is included. Bit timing is one bit per `clk` cycle in
this core (no internal baud-rate divider); any baud generation is
expected to be handled by the surrounding integration, e.g. by
clocking this core at the desired bit rate.

## Control and Handshake Signals

- `tx_data [7:0]` — the byte to transmit. Sampled when a new frame is
  started.
- `tx_start` — asserted for one clock cycle by the requester to begin
  transmission of the current value of `tx_data`. Must only be
  asserted while the core is idle (`tx_busy` low); requests issued
  while `tx_busy` is high are not guaranteed to be honored.
- `tx` — the serial output line. Idles high. Carries the start bit,
  data bits, and stop bit for each frame as described above.
- `tx_busy` — asserted from the cycle a frame begins (in response to
  `tx_start`) through the完成 of the stop bit. Deasserts once the
  frame has completed, indicating the core is ready to accept a new
  `tx_start` request.
- `tx_done` — a single-cycle pulse indicating frame completion.
  Asserted for exactly one `clk` cycle, coincident with the stop bit
  period, after which it returns low. Intended for use by the
  requester to detect completion without polling `tx_busy`.

## Debug/Status Output

- `status_dbg [3:0]` — a 4-bit combinational status nibble intended
  for lab bring-up and bench debugging only. It is provided so that
  engineers can observe the transmitter's internal FSM state on a
  logic analyzer or bench scope without requiring internal probe
  access to the design.

  `status_dbg` is **not** part of the functional interface contract
  of this core. Downstream logic must not depend on its value for
  correct operation, and its encoding may change between design
  revisions without notice. It exists purely to aid bring-up and
  characterization activities and should be treated as
  best-effort visibility into internal state, not a guaranteed
  status register.

## Summary of Timing Guarantees

| Signal      | Guarantee                                                        |
|-------------|-------------------------------------------------------------------|
| `tx`        | Idles high; frames start bit / 8 data bits (LSB-first) / stop bit |
| `tx_busy`   | High for the full duration of an in-progress frame                |
| `tx_done`   | One-cycle pulse at frame completion (during the stop bit period)  |
| `status_dbg`| Best-effort bring-up visibility only; no functional guarantee     |

These are the behaviors this core is expected to provide for correct
integration into a larger system. `status_dbg` is explicitly excluded
from functional guarantees and should not be relied upon by any
production logic.