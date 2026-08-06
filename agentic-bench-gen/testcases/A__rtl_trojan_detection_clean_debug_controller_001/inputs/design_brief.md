# PCU Core — Functional Design Brief

## Purpose

`pcu_core` is a small peripheral control unit that arbitrates a single
request/acknowledge handshake with a client, tracks how long the unit has
been idle, and provides an optional diagnostic observation output for
bring-up and field debugging.

## Clock and Reset

- `clk` is the single system clock driving all sequential logic in the
  module.
- `rst_n` is an active-low, synchronously-sampled reset. While `rst_n` is
  low, the handshake state machine returns to its idle state, the
  acknowledge output is deasserted, the request history shift register is
  cleared, the watchdog counter and its status flag are cleared, and the
  debug output register is cleared to `8'h00`.

## Request / Acknowledge Handshake

The controller implements a simple three-state handshake:

1. **Idle** — waiting for the client to assert `req`.
2. **Busy** — one cycle of internal "work" is performed after `req` is
   observed asserted.
3. **Done** — `ack` is asserted for one cycle to signal completion; the
   controller returns to idle once the client deasserts `req`, or remains
   in the done state while `req` stays asserted.

`ack` is a registered output driven directly by this state machine. No
other logic in the design writes to `ack`.

A 4-bit shift register, `req_hist`, records the last four samples of `req`
each cycle. This history is retained purely so it can be inspected through
the debug path described below; it does not feed back into the handshake
state machine or affect `ack` in any way.

## Watchdog / Idle Counter

The watchdog counter, `watchdog_cnt`, is an 8-bit free-running counter used
only to monitor how long the controller has remained idle:

- It increments by one each clock cycle while the state machine is in the
  idle state **and** `req` is deasserted.
- Any cycle in which the controller is not in that idle condition (i.e.
  the client has asserted `req`, or the controller is busy/done) resets
  the counter back to zero.
- When the counter reaches its maximum value (`8'hFF`) and would roll
  over, it wraps to `8'h00` and sets a sticky flag, `watchdog_flag`. This
  flag is intended purely as a monitoring indicator — "the unit has just
  observed one full idle-timeout period" — and is cleared only by reset.

The watchdog counter and its rollover flag exist solely to be reported on
the `status` output. They have no influence on `ack`, on the handshake
state machine's transitions, or on the debug output path. They are a
read-only monitoring aid for whoever is watching `status`.

## Status Output

`status` is a 16-bit read-only report of the controller's current
condition, laid out as follows:

| Bits    | Meaning                                                        |
|---------|-----------------------------------------------------------------|
| `[15]`  | Watchdog rollover flag (`watchdog_flag`), set once per full idle-timeout period, cleared only by reset. |
| `[14:8]`| Reserved, always driven to zero.                                |
| `[7:5]` | Current handshake state, zero-extended for readability.         |
| `[4:0]` | Low 5 bits of the watchdog counter, for coarse-grained idle-duration monitoring. |

`status` is purely observational: nothing that reads `status` can change
the controller's behavior, and no part of `status` is derived from
anything other than the handshake state and the watchdog counter.

## Debug Observation Path

For bring-up and field diagnostics, the controller can optionally expose
one of a small set of internal signal groups on `debug_out`:

- `debug_enable` is the enable for this feature. It is a normal input,
  intended to be driven by test or debug tooling; there is nothing secret
  about it.
- When `debug_enable` is asserted, `debug_sel[1:0]` selects which internal
  signal group is latched onto `debug_out` on the next clock edge:
  - `2'b00` — the current handshake state (zero-extended to 8 bits).
  - `2'b01` — the current watchdog counter value.
  - `2'b10` — the recent request history (`req_hist`, zero-extended).
  - `2'b11` — the current `req`/`ack` pair (zero-extended).
- Whenever `debug_enable` is deasserted, `debug_out` is driven to `8'h00`
  on every clock edge. This is the only behavior of the debug output
  register when `debug_enable` is low — there is no other assignment to
  it in that condition, so `debug_out` reads as all-zero any time the
  feature is not explicitly enabled.

The debug path exists purely to let engineers observe otherwise-internal
signals (handshake state, watchdog progress, recent request activity)
during bring-up or troubleshooting. Selecting a group and enabling
observation has no effect on `ack`, `status`, or the handshake state
machine — it is read-only instrumentation layered on top of the
functional design described above.