# Streaming Pipeline Module Design Brief

## Overview

The `stream_pipeline` module implements a single-clock streaming data path with a one-entry skid buffer to handle backpressure. It accepts data on an input ready/valid interface and forwards it to an output ready/valid interface, ensuring no data is lost when the downstream consumer is not immediately ready.

## Interface

| Signal   | Direction | Width | Description                                      |
|----------|-----------|-------|--------------------------------------------------|
| clk      | input     | 1     | Clock signal (all logic is synchronous to this). |
| rst_n    | input     | 1     | Active-low synchronous reset.                    |
| s_valid  | input     | 1     | Input valid qualifier from upstream source.      |
| s_ready  | output    | 1     | Backpressure signal to upstream source.          |
| s_data   | input     | 32    | Input data word.                                 |
| m_valid  | output    | 1     | Output valid qualifier to downstream sink.       |
| m_ready  | input     | 1     | Ready signal from downstream sink.               |
| m_data   | output    | 32    | Output data word.                                |

## Handshake Protocol

The module uses the standard AXI-Stream-like ready/valid handshake:

- A transfer occurs on any cycle where both `s_valid` and `s_ready` are high.
- The upstream source asserts `s_valid` when it has valid data to send.
- The module asserts `s_ready` when it can accept new data.
- Similarly, on the output side, a transfer occurs when both `m_valid` and `m_ready` are high.

## Skid Buffer Operation

To avoid stalling the upstream source when the downstream sink is not ready, the module includes a single-entry skid buffer:

- When the output is not ready (`m_ready` low) and a new input word arrives, the incoming data is stored in the skid buffer and `s_ready` is deasserted to prevent further input transfers.
- Once the output becomes ready, the skid buffer contents are forwarded to the output register, and the skid buffer is cleared.
- The pipeline can hold at most two data items: one in the output register and one in the skid buffer.

## Expected Behavior

Under normal operation, the module should pass every input word to the output without duplication or loss, respecting the flow control signals. The output valid signal `m_valid` should be asserted whenever valid data is present in the output register, and should be deasserted only when that data has been accepted by the downstream sink (i.e., after a cycle with `m_valid` and `m_ready` both high).

## Implementation Notes

- The design is fully synchronous to `clk` and uses a synchronous active-low reset (`rst_n`).
- All registers are reset to known states.
- The module is intended to be synthesizable and follows standard RTL coding practices.