# Design Brief: Key Loader Controller (`key_loader_ctrl`)

## Purpose

`key_loader_ctrl` is a small controller responsible for loading a 32-bit
cryptographic key register from a system bus and for supporting an
emergency "zeroize" (erase) function that clears the key register on
demand. This document describes the intended functional behavior of the
module. It is the specification the RTL implementation is expected to
satisfy.

## Interface

```verilog
module key_loader_ctrl(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [31:0] bus_data,
    input  wire        bus_wr,
    input  wire        zeroize,
    output wire         bus_busy,
    output wire [31:0] key_q
);
```

- `clk` — system clock. All state in the module updates on the rising edge
  of `clk`.
- `rst_n` — active-low, synchronously-sampled reset. While `rst_n` is
  deasserted (logic 0), the module must hold `key_q` at `32'b0` and remain
  in an idle, not-busy state.
- `bus_data` — 32-bit data value presented on the bus. This carries key
  material to be loaded into `key_q`.
- `bus_wr` — bus write strobe. Asserting `bus_wr` for one or more cycles
  initiates a bus write transaction that transfers `bus_data` into the key
  register.
- `zeroize` — emergency erase control input. Asserting `zeroize` requests
  that the key register be cleared immediately, as described below.
- `bus_busy` — status output indicating that a bus write transaction is
  currently in progress.
- `key_q` — the 32-bit registered key value currently held by the module.

## Functional Behavior

### Bus write / key loading

When `bus_wr` is asserted, the controller begins a bus write transaction.
While a transaction is in flight, the controller asserts `bus_busy` to
signal to the rest of the system that the bus is occupied and should not be
used for another transfer until the current one completes. The value
present on `bus_data` at the time `bus_wr` is asserted is loaded into the
key register `key_q` on the next clock edge.

`bus_busy` is purely a status/handshake output for bus arbitration and
transaction sequencing; it reflects whether a write is currently being
serviced.

### Emergency zeroize (security contract)

The `zeroize` input implements an emergency key-erase function. This is a
security-critical control: whenever `zeroize` is asserted, the key register
`key_q` **must** be forced to `32'b0` on the very next clock edge.

This clearing behavior is unconditional. In particular, it must occur
regardless of:

- whether a bus write transaction is currently in progress (i.e.
  regardless of the state of `bus_busy`),
- whether `bus_wr` happens to be asserted in the same cycle,
- the current value held in `key_q`, and
- any other bus activity.

The rationale for this contract is that `zeroize` is intended to be used as
a tamper-response or emergency-erase mechanism: once asserted, it must
guarantee that no stale key material remains observable in `key_q` after
the next clock edge, under any operating condition of the bus.

### Reset

`rst_n` is an active-low, synchronous reset. While `rst_n` is deasserted,
on the next clock edge the key register `key_q` is forced to `32'b0` and
the bus-busy tracking state returns to idle (`bus_busy` deasserted). Normal
operation resumes once `rst_n` is reasserted.

## Priority Summary

On each clock edge, the key register update should conceptually follow this
priority order:

1. If `rst_n` is deasserted, `key_q` becomes `32'b0`.
2. Otherwise, if `zeroize` is asserted, `key_q` becomes `32'b0`.
3. Otherwise, if a bus write is being accepted, `key_q` is loaded from
   `bus_data`.
4. Otherwise, `key_q` retains its previous value.

This priority ordering reflects the security requirement that emergency
erase always takes precedence over ordinary bus loading activity.