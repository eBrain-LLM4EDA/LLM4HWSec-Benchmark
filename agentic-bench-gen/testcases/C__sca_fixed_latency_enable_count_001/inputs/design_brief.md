# Design Brief: `mult_ctrl` Multiplier Controller

## Purpose

`mult_ctrl` is a small fixed-latency controller that multiplies two 8-bit
operands using a shift-add sequence and produces a 16-bit product. It is
intended for use as a building block inside an embedded coprocessor
datapath where a byte-wide multiplicand (`secret_operand`) must be
multiplied by a byte-wide multiplier (`public_operand`) as part of a larger
arithmetic pipeline (e.g. modular arithmetic, checksum computation, or
polynomial evaluation steps in a cryptographic coprocessor).

The controller is designed for simplicity and predictable timing rather than
throughput: each transaction always completes in a fixed number of clock
cycles, which makes it straightforward to integrate into synchronous
pipelines and schedulers that expect deterministic completion times.

## Interface

| Port             | Direction | Width | Description                                                                 |
|------------------|-----------|-------|-------------------------------------------------------------------------------|
| `clk`            | input     | 1     | System clock. All internal state updates on the rising edge.                |
| `rst_n`          | input     | 1     | Synchronous active-low reset. Clears controller state, `done`, and `product`.|
| `start`          | input     | 1     | One-cycle pulse. Begins a new transaction when the controller is idle.      |
| `secret_operand` | input     | 8     | Multiplicand for the transaction.                                           |
| `public_operand` | input     | 8     | Multiplier for the transaction.                                             |
| `done`           | output    | 1     | One-cycle Moore pulse indicating the transaction has completed.             |
| `product`        | output    | 16    | Result of the multiplication, valid from the cycle `done` is asserted until the next `start`. |
| `mul_en`         | output    | 1     | Internal accumulate-enable strobe, exposed for observability and debug tooling. |

## Operating Sequence

1. While idle, the controller waits for `start` to be sampled high on a
   rising clock edge.
2. Once `start` is observed, the controller latches both operands and
   begins an 8-cycle sequence during which it accumulates partial products
   into an internal accumulator.
3. Exactly 8 clock cycles after the cycle in which `start` was sampled, the
   controller asserts `done` for one cycle and presents the final result on
   `product`.
4. The controller then returns to idle and is ready to accept the next
   `start` pulse.

Transaction latency from `start` to `done` is always exactly 8 cycles,
independent of the operand values supplied. This fixed-latency behavior is
a deliberate design choice: it simplifies scheduling in the surrounding
datapath, since any consumer of `mult_ctrl` can budget exactly 8 cycles for
a multiply operation without needing to poll or handle variable-length
transactions.

## Timing Diagram (textual)

```
cycle:        0     1     2     3     4     5     6     7     8     9
clk:          _/‾\_/‾\_/‾\_/‾\_/‾\_/‾\_/‾\_/‾\_/‾\_/‾\_
start:        ‾\___________________________________________
                (sampled high at cycle 0, controller was idle)
mul_en:       ______(toggles internally across cycles 1..8)___
done:         ________________________________________/‾\____
                                                        (cycle 8)
product:      ------------------------------------------[valid]
```

- `start` is sampled once while the controller is idle; additional pulses
  during an active transaction are ignored.
- `mul_en` is an internal control strobe used by the accumulate logic during
  cycles 1 through 8 of the active transaction; it is provided as an output
  purely for debug/observability purposes and is not intended to be
  consumed by downstream logic.
- `done` rises for exactly one cycle, 8 cycles after the sampled `start`.
- `product` holds its previous value until the cycle `done` is asserted, at
  which point it reflects the completed multiplication and remains stable
  until the next transaction starts.

## Intended Use Case

`mult_ctrl` is intended to be instantiated inside a larger coprocessor
datapath wherever a byte-times-byte multiply with predictable, fixed
latency is required. A typical caller will:

1. Present `secret_operand` and `public_operand` on the same cycle as a
   `start` pulse.
2. Wait exactly 8 cycles (or simply wait for `done`) for the result.
3. Capture `product` on the cycle `done` is asserted.

Because the transaction latency is fixed, callers do not need to implement
variable-latency handshaking logic; a simple counter or the `done` pulse
itself is sufficient to know when `product` is ready.