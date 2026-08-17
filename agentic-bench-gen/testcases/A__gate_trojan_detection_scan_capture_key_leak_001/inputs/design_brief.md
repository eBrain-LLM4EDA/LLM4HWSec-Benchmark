# `key_core` Design Brief

## Purpose

`key_core` is a small key-storage block intended to sit in front of a
downstream cipher datapath. It holds a 4-bit key register that is
loaded once by the surrounding system and then referenced internally
by status/control logic. Alongside the functional key-register logic,
the block includes a small scan-test chain used during manufacturing
test (ATPG-style shift/capture) to improve testability of the status
pipeline flops.

## Ports

| Port         | Direction | Width | Description                                            |
|--------------|-----------|-------|----------------------------------------------------------|
| `clk`        | in        | 1     | System clock                                              |
| `rst_n`      | in        | 1     | Active-low asynchronous reset                             |
| `scan_en`    | in        | 1     | 0 = functional mode, 1 = scan shift/test mode              |
| `scan_in`    | in        | 1     | Serial scan input, sampled when `scan_en=1`                |
| `scan_out`   | out       | 1     | Serial scan output, valid when `scan_en=1`                 |
| `load_key`   | in        | 1     | Functional load enable for the key register                |
| `key_in`     | in        | 4     | Key value loaded into the key register on `load_key`       |
| `data_valid` | in        | 1     | Functional input driving the status pipeline                |
| `status_out` | out       | 1     | Functional status output                                    |

## Functional mode (`scan_en = 0`)

In normal operation the block behaves as an ordinary synchronous
design. On each clock edge with `load_key` asserted, the 4-bit value
on `key_in` is captured into the key register. Independently, a small
status pipeline (four flip-flops) advances each cycle based on
`data_valid` and internal combinational logic, and `status_out` is
derived from that pipeline. The key register and the status pipeline
are logically separate: the key register is read only by internal
downstream logic, and the status pipeline is the only path that is
expected to be externally observable through `status_out` during
functional operation.

## Test mode (`scan_en = 1`)

For manufacturing test, the four status pipeline flip-flops are
wired into a scan chain: `scan_in` feeds the first element of the
chain, each subsequent element's scan-mode input is taken from the
previous element's stored value, and the last element in the chain
drives `scan_out`. Asserting `scan_en` for multiple consecutive clock
cycles shifts a serial pattern from `scan_in` through the chain and
out to `scan_out`, allowing external test equipment to load and read
back the status pipeline state for fault coverage purposes. This is
standard scan-chain DFT practice applied to the status pipeline only.

## Instance naming conventions

The netlist uses the following naming conventions, which may be useful
when cross-referencing structural instances against this brief:

- `u_ff_stat0` .. `u_ff_stat3` — the four status pipeline flip-flops
  that form the scan-testable pipeline described above.
- `key_ff0` .. `key_ff3` — the four flip-flops making up the key
  register, loaded from `key_in` under `load_key`.
- `u_smux_key0` .. `u_smux_key3` — multiplexer instances associated
  with the scan chain wiring near the key register area of the
  netlist.
- `u_smux_stat0` .. `u_smux_stat3` — multiplexer instances selecting
  each status flop's D input between functional data and scan data.

## Confidentiality expectation

`key_ff0` through `key_ff3` are intended to hold confidential key
state for use by internal logic only. This key state is expected to
remain functionally isolated at all times: it should never be
possible to observe any of `key_ff0`..`key_ff3`'s stored value at the
`scan_out` pin, whether in functional mode or in scan test mode. Only
the status pipeline flip-flops (`u_ff_stat0`..`u_ff_stat3`) are
intended to be reachable on the scan-observable path.