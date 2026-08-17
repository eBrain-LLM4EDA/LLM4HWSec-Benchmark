# Design Brief: `precharge_bus_wrapper`

## Purpose

`precharge_bus_wrapper` transports an 8-bit data word from an internal
source to a shared, externally observable bus (`dbus[7:0]`) using a
two-phase transfer protocol. This brief documents the module's port
semantics and the timing contract that downstream logic and bus observers
should rely on.

## Ports

| Port | Direction | Width | Description |
|---|---|---|---|
| `clk` | input | 1 | System clock. All internal state transitions occur on the rising edge. |
| `rst_n` | input | 1 | Active-low, synchronous reset. While `rst_n` is low, on the next rising edge of `clk` the module clears its internal sequencer, drives `dbus` to `8'h00`, and deasserts `valid`. |
| `load` | input | 1 | One-cycle pulse asserted by the requester to begin a transfer. `data_in` must be valid on the same cycle `load` is asserted; the module samples it that cycle. |
| `data_in` | input | 8 | The transported data word for the transfer initiated by the current `load` pulse. |
| `dbus` | output (reg) | 8 | The shared bus net. This is the point at which the transferred value becomes externally observable. |
| `valid` | output (reg) | 1 | Asserted for exactly one cycle per completed transfer, on the cycle where `dbus` carries the fully settled data value corresponding to the most recent `load`. |

## Transfer protocol

Each transfer proceeds through two sequencer phases following the cycle in
which `load` is sampled:

1. **Load cycle** (`load_cycle`) — `load` is asserted (`load = 1`) together
   with a valid `data_in`. The module latches `data_in` internally on this
   cycle. `dbus` and `valid` are not updated with respect to this transfer
   yet on this cycle.

2. **Precharge phase** (`load_cycle + 1`) — On the cycle immediately
   following the load cycle, the module drives `dbus` to its
   architecturally-fixed baseline value (`8'h00`) and holds `valid` low.
   This phase always drives the same fixed value regardless of the data
   word being transferred.

3. **Evaluate phase** (`load_cycle + 2`) — On the second cycle following
   the load cycle, the module drives `dbus` to the latched data word
   (i.e., the value sampled from `data_in` on `load_cycle`) and asserts
   `valid` for that single cycle. This is the cycle on which `dbus`
   presents the fully settled, correct output of the transfer and at which
   downstream logic should capture the result.

After the evaluate phase, the sequencer returns to its idle state and is
ready to accept a new `load` pulse on a subsequent cycle.

## Timing summary

Relative to the cycle on which `load` is asserted (offset 0):

| Phase | Cycle offset from `load` | `dbus` driven to | `valid` |
|---|---|---|---|
| Load (sample) | 0 | unspecified / previous transfer's residual value | 0 |
| Precharge | +1 | fixed baseline (`8'h00`) | 0 |
| Evaluate | +2 | the latched data word from `data_in` | 1 (for this cycle only) |

This gives a fixed, documented **two-cycle latency** from the assertion of
`load` to the cycle on which `valid` is asserted and `dbus` carries the
correct, settled result of the transfer. Requesters and downstream
consumers of `dbus` should use `valid` as the indicator of when to sample
`dbus`, rather than relying on cycle counting alone, but the two-cycle
offset above is the documented behavior implemented by the sequencer.

## Reset behavior

While `rst_n` is deasserted, the sequencer is held in its idle state,
`dbus` is driven to `8'h00`, and `valid` remains deasserted. No transfer is
considered in progress across a reset; any `load` pulse that was asserted
immediately prior to reset must be reissued once `rst_n` is released for
the transfer to complete.