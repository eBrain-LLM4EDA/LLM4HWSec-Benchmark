# `aes_core` Design Brief

## Overview

`aes_core` is a compact, single-lane, iterative AES-like round-function
core. It performs a fixed 10-round transformation over a 128-bit input
block using a 128-bit key, producing a 128-bit output block. The core
is intended for low-area embedded use cases where a single round
datapath is reused sequentially across all rounds rather than unrolled
in hardware.

## Ports

| Port       | Direction | Width | Description                                                |
|------------|-----------|-------|--------------------------------------------------------------|
| `clk`      | input     | 1     | System clock. All sequential logic is synchronous to `clk`. |
| `rst_n`    | input     | 1     | Active-low asynchronous reset.                               |
| `in_data`  | input     | 128   | Plaintext/input block to be transformed.                     |
| `key`      | input     | 128   | Initial key material for the round schedule.                 |
| `start`    | input     | 1     | Single-cycle pulse that loads `in_data`/`key` and begins processing. |
| `out_data` | output    | 128   | Resulting transformed block, valid when `done` is asserted.  |
| `done`     | output    | 1     | Single-cycle pulse indicating `out_data` is valid.            |

## Datapath

### State register

`state_reg` holds the 128-bit working state. On the cycle that `start`
is asserted (while the core is idle), `state_reg` is loaded from
`in_data`. On each subsequent active cycle, `state_reg` is updated with
the output of the round function until the round counter reaches its
terminal value, at which point the final state is latched into
`out_data`.

### Key register

`key_reg` holds the working key material used to derive per-round key
bytes. It is loaded from `key` at the start of processing and rotated
by one byte each round, providing a simple key-schedule-like evolution
across the 10 rounds.

### Round counter (`round_cnt`)

`round_cnt` is a 4-bit register that counts the number of completed
rounds, from `0` up to `10`. It is reset to `0` when a new block is
loaded (on `start`), incremented once per round while the core is busy,
and used to select the round constant fed into the round function. When
`round_cnt` reaches `10`, the core considers the block finished: the
current state is committed to `out_data` and the core returns to idle.

### Round function

Each round applies a byte substitution to part of the state using a
fixed substitution table (S-box) and mixes in a per-round constant from
a fixed round-constant table (`rcon`), indexed by `round_cnt`. The
result is combined with a rotated view of the key register to produce
the next state. This mirrors, in simplified single-byte-substitution
form, the substitute/mix/add-round-key structure of a standard AES-like
round.

### Busy/control flag

An internal `busy` flag tracks whether the core is currently processing
a block. It is set when a new block is accepted via `start` and cleared
once the final round completes and `out_data`/`done` have been updated.
While `busy` is asserted, new `start` pulses are ignored until the
current block finishes.

## Timing and Handshake

1. While idle (`busy == 0`), asserting `start` for one cycle loads
   `in_data` into `state_reg` and `key` into `key_reg`, resets
   `round_cnt` to `0`, and sets `busy`.
2. On each subsequent cycle while `busy` is asserted and `round_cnt` is
   less than `10`, one round of the round function is applied and
   `round_cnt` increments.
3. When `round_cnt` reaches `10`, the current `state_reg` value is
   written to `out_data`, `done` is pulsed for exactly one cycle, and
   `busy` is cleared, returning the core to idle.
4. `out_data` remains stable and valid from the cycle `done` is
   asserted until the next block completes.

## Reset Behavior

Asserting `rst_n` low asynchronously clears `state_reg`, `key_reg`,
`round_cnt`, `busy`, `done`, and `out_data` to zero. No processing
occurs while reset is held, and the core resumes normal idle behavior
once `rst_n` is released, ready to accept a new `start` pulse.