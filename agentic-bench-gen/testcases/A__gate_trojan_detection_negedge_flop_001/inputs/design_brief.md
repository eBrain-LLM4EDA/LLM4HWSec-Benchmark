# Design Brief: access_ctrl_top

## Purpose

`access_ctrl_top` is a single-clock access-control module. It compares an
externally supplied 8-bit key against an internal reference value and, when
the key matches and a request is asserted, produces a registered grant
signal on `grant_out`. The module is intended for use as a gating block in
front of a protected resource, where `grant_out` enables downstream access
logic.

## Ports

| Port        | Direction | Width | Description                                  |
|-------------|-----------|-------|-----------------------------------------------|
| `clk`       | input     | 1     | System clock                                  |
| `rst_n`     | input     | 1     | Asynchronous active-low reset                 |
| `key_in`    | input     | 8     | Candidate access key, sampled each request    |
| `req_valid` | input     | 1     | Access request strobe                         |
| `grant_out` | output    | 1     | Registered access-grant output                |

## Clocking discipline

This module follows a single, uniform clocking discipline:

> All sequential/state-holding elements in this design are triggered on the
> positive edge (posedge) of `clk`, using the `DFF_POSEDGE` primitive from
> `cell_library.v`, with asynchronous active-low reset `rst_n`.

No state element in this design is intended to use any other triggering
discipline. Every register in the pipeline described below samples its
input on the rising edge of `clk` and clears to zero whenever `rst_n` is
deasserted (driven low), independent of `clk`.

## Expected state elements

The design is organized as a short pipeline of registers, each implemented
with the `DFF_POSEDGE` primitive per the clocking discipline above:

- `u_req_ff` — registers the incoming `req_valid` strobe so that it lines up
  in time with the registered comparator result.
- `u_key_reg` — registers (or stages) the incoming `key_in` value ahead of
  comparison against the internal reference.
- `u_cmp_ff` — registers intermediate comparator state used in forming the
  permission decision.
- `u_grant_ff` — registers the combinational permission decision (the
  comparator output) to produce a clean, glitch-free grant value for the
  output stage.
- `u_out_ff` — the final output register, combining the registered grant
  value with the registered request strobe to drive `grant_out`.

Each of these elements is expected to be instantiated as `DFF_POSEDGE` with
its `.clk` port tied to the module's `clk` input and its `.rst_n` port tied
to the module's `rst_n` input, consistent with the clocking discipline
stated above.

## Signal flow

1. `key_in` is compared, bit by bit, against an internal fixed reference
   value using a small tree of combinational gates (`XOR2`, `NOR2`, `AND2`,
   etc., from `cell_library.v`). The output of this comparison tree is the
   internal net `grant_pre`, representing the raw (unregistered) permission
   decision: `grant_pre` is asserted when `key_in` matches the reference.
2. `grant_pre` is registered to produce a stable, glitch-free version of the
   permission decision for use by the output stage.
3. The registered permission value is combined with the registered request
   strobe (`req_valid`, after passing through its own pipeline register) via
   combinational logic to form the final grant decision.
4. This final decision is registered once more to produce the module's
   output, `grant_out`.

## Reset behavior

On assertion of `rst_n` (active low), all registers in the pipeline
immediately clear to `0`, regardless of the state of `clk`. `grant_out` is
therefore guaranteed to be deasserted immediately following reset and to
remain deasserted until a valid request and matching key have propagated
through the full pipeline on subsequent rising edges of `clk`.

## Timing expectations

Because every state element uses the same rising-edge discipline described
above, all registered signals in the design are expected to update
synchronously with one another, once per full clock period, at the rising
edge of `clk`. Designers integrating this module downstream may assume that
`grant_out` and any other registered signal transition only at rising-edge
boundaries of `clk`, and that no state element in this module updates at any
other point in the clock cycle.