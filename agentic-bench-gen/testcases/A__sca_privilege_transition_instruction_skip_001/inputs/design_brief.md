# Design Brief: `mode_sequencer` Privilege-Mode Transition Sequencer

## Purpose

`mode_sequencer` is a small synchronous control sequencer that manages a
2-bit privilege register, `priv_reg`, in response to two request inputs:
`req_demote` (lower privilege) and `req_promote` (raise privilege). Each
request causes the module to walk through a fixed sequence of named states
over several clock cycles, updating `priv_reg` at a specific, documented
point in the sequence, and finally asserting `done` for one clock cycle to
signal completion of the transition.

## Ports

| Port | Direction | Width | Description |
|---|---|---|---|
| `clk` | input | 1 | Clock. All state and register updates occur on the rising edge. |
| `rst_n` | input | 1 | Active-low, asynchronous reset. |
| `req_demote` | input | 1 | Requests a transition from supervisor to user privilege. Sampled while `state == IDLE`. |
| `req_promote` | input | 1 | Requests a transition from user to supervisor privilege. Sampled while `state == IDLE`. |
| `priv_reg` | output reg | 2 | Current privilege level. |
| `state` | output reg | 4 | Current FSM state code (see encoding below). |
| `done` | output wire | 1 | Asserted for exactly one clock cycle when the current transition sequence completes. |

## `priv_reg` Encoding

| Value | Meaning |
|---|---|
| `2'b10` | supervisor (high privilege) |
| `2'b00` | user (low privilege) |
| `2'b01` | reserved (not produced by this design) |
| `2'b11` | reserved (not produced by this design) |

## State Encoding

`state` is a 4-bit Moore-encoded value. The module defines nine named
states, five used for the demotion path (including the shared `IDLE`
state) and four additional states used for the promotion path:

| State name | Encoding (`state` value) | Role |
|---|---|---|
| `IDLE` | `4'd0` | Idle / waiting for a request. Shared entry and exit point for both sequences. |
| `CHECK` | `4'd1` | First step of the demotion sequence. Sequencing only. |
| `DEMOTE` | `4'd2` | Second step of the demotion sequence. **`priv_reg` is written to `2'b00` while in this state.** |
| `SETTLE` | `4'd3` | Third step of the demotion sequence. Sequencing only. |
| `DONE` | `4'd4` | Final step of the demotion sequence. `done` is asserted while `state == DONE`. Sequencing only (no `priv_reg` write). |
| `PCHECK` | `4'd5` | First step of the promotion sequence. Sequencing only. |
| `PROMOTE` | `4'd6` | Second step of the promotion sequence. **`priv_reg` is written to `2'b10` while in this state.** |
| `PSETTLE` | `4'd7` | Third step of the promotion sequence. Sequencing only. |
| `PDONE` | `4'd8` | Final step of the promotion sequence. `done` is asserted while `state == PDONE`. Sequencing only (no `priv_reg` write). |

## Demotion Sequence (`req_demote`)

Starting from `IDLE` with `req_demote` asserted, the module advances one
state per clock cycle in the following fixed order:

```
IDLE -> CHECK -> DEMOTE -> SETTLE -> DONE -> IDLE
```

`priv_reg` is written to `2'b00` on the clock edge that advances the FSM
*out of* the `DEMOTE` state (i.e. the write is associated with occupying
state `DEMOTE`, following the same convention used for the state register
update on that edge). No other state in this sequence writes `priv_reg`;
`CHECK`, `SETTLE`, and `DONE` exist purely to sequence and time the
transition, and `priv_reg` simply retains whatever value it already holds
while the FSM passes through them.

`done` is asserted for exactly one clock cycle, corresponding to the cycle
during which `state == DONE`.

## Promotion Sequence (`req_promote`)

Starting from `IDLE` with `req_promote` asserted (and `req_demote` not
asserted), the module advances through the following fixed order:

```
IDLE -> PCHECK -> PROMOTE -> PSETTLE -> PDONE -> IDLE
```

`priv_reg` is written to `2'b10` on the clock edge associated with
occupying state `PROMOTE`. As with the demotion path, `PCHECK`, `PSETTLE`,
and `PDONE` perform no write to `priv_reg`.

`done` is asserted for exactly one clock cycle, corresponding to the cycle
during which `state == PDONE`.

## Reset Behavior

`rst_n` is an active-low, asynchronous reset. While `rst_n` is deasserted
(low):

- `state` is forced to `IDLE` (`4'd0`).
- `priv_reg` is forced to `2'b10` (supervisor).

Normal operation resumes on the first rising edge of `clk` after `rst_n` is
released (driven high), with the module sampling `req_demote` /
`req_promote` from the `IDLE` state as described above.

## Notes for Documenting a Transition Sequence

When describing the full sequence of states traversed during a demotion
request (from the assertion of `req_demote` through to `done`), use the
exact state names listed above, in the order given for the demotion path:
`IDLE`, `CHECK`, `DEMOTE`, `SETTLE`, `DONE`. This is the complete and
authoritative list of states involved in a single demotion transition; no
additional states are visited and none are skipped in the fault-free case.