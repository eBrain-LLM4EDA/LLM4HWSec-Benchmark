# Design Brief: `signature_compare` Byte-Serial Signature Comparator

## Purpose

`signature_compare` is a small verification-unit block used in a
bootloader/firmware-update pipeline to compare a locally computed
"expected" 16-byte signature against a "received" 16-byte signature
supplied by an external source (e.g. a host tool or an update image
header). The comparison is performed byte-by-byte as the two
signatures are streamed into the module, rather than requiring both
16-byte values to be buffered in full before comparison begins. This
keeps the module's data-path narrow (single byte-wide compare per
cycle) and avoids the need for two 128-bit input registers upstream.

## Operating Context

The module is instantiated inside a larger verification sequencer that:

1. Computes or retrieves the expected 16-byte signature and reads the
   received 16-byte signature from wherever it is staged (e.g. a
   receive FIFO or memory-mapped buffer).
2. Pulses `start` for one cycle to begin a new comparison.
3. Presents `expected_byte` and `received_byte` for byte position 0 on
   the cycle after `start`, and continues presenting successive byte
   pairs (position 1, 2, ... up to 15) on successive cycles, asserting
   `byte_valid` on each cycle a valid byte pair is present.
4. Waits for `done` to assert, then reads `match` to determine whether
   the update image (or whatever payload the signature guards) should
   be accepted.

The sequencer is expected to hold `byte_valid` high for each of the 16
cycles following `start` in normal operation; there is no requirement
to pad, delay, or reorder byte delivery. `byte_valid` exists primarily
to let the sequencer stall byte delivery (e.g. while waiting on a slow
upstream buffer) without corrupting the module's internal counter.

## Port Semantics

- `clk`, `rst_n`: Standard synchronous design. `rst_n` is active-low;
  when deasserted (`rst_n = 0`), all internal state (byte counter,
  outputs) clears on the next rising edge of `clk`. The module is
  otherwise fully synchronous — no combinational output paths depend
  directly on the byte inputs.

- `start`: A one-cycle pulse issued by the sequencer to begin a new
  comparison. Asserting `start` clears `done` and `match` and resets
  the internal byte counter, so the module is ready to accept the
  first byte pair on the following cycle. The sequencer must not
  reassert `start` mid-comparison; doing so restarts the byte counter
  and discards any partial comparison progress.

- `expected_byte`, `received_byte`: Byte-wide values for the current
  signature position, valid whenever `byte_valid` is asserted. The
  module consumes exactly one byte pair per cycle in which
  `byte_valid` is high.

- `byte_valid`: Qualifies `expected_byte`/`received_byte` on a given
  cycle. When low, the module holds its current internal state and
  does not advance its byte counter.

- `done`: A Moore-style output. It asserts once the module has
  consumed the bytes it needs to determine a verdict for the current
  comparison, and remains asserted (along with a stable `match` value)
  until the next `start` pulse begins a new comparison cycle. Downstream
  logic should treat `match` as valid only while `done` is high.

- `match`: Indicates whether the two signatures presented during the
  current comparison were found to be identical. Only meaningful while
  `done = 1`.

## Timing Notes

The number of clock cycles between the `start` pulse and the
subsequent assertion of `done` is an implementation detail of the
internal comparison logic and is not specified as a fixed constant in
this brief. Designers integrating this module into a larger pipeline
(e.g. sizing timeout counters, scheduling downstream reads of `match`)
should determine the module's actual cycle latency empirically — for
example, using the reference testbench provided alongside this module
— rather than assuming a particular fixed value. The sequencer should
simply wait for `done` to assert rather than relying on a hardcoded
cycle count.

## Reset and Re-use

After a comparison completes (`done = 1`), the module can be reused
for a subsequent comparison by issuing a new `start` pulse; there is no
need to assert `rst_n` between comparisons unless a full state reset is
desired (e.g. at power-up or after a detected protocol error upstream).
`rst_n` is provided primarily for initializing the module into a known
state and for use in system-level reset trees.

## Summary of Expected Functional Behavior

- All 16 byte pairs equal → `done` asserts with `match = 1`.
- Any one or more byte pairs differ → `done` asserts with `match = 0`.
- `done` and `match` hold their values from the completed comparison
  until the next `start` pulse.

This brief describes the module's external contract; refer to
`signature_compare.v` for the exact internal implementation.