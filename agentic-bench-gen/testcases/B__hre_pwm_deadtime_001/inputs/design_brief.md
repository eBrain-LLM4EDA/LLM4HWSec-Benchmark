# Design Brief: Legacy Half-Bridge Gate-Driver PWM Block

## Background

This block was salvaged from a legacy motor-controller board during a
teardown of end-of-life industrial equipment. No datasheet, no design
documentation, and no commit history survived the recovery — only the
synthesized netlist and a partially-flattened RTL wrapper that appear to
have been pulled from an old synthesis run directory. Silkscreen and
package markings identify it only as a "PWM/GD" block, consistent with
it having driven the two switches of a half-bridge gate driver stage.

This brief summarizes what can be inferred about the block's role and
pinout from board-level context and datasheet fragments of the
surrounding circuitry. It is deliberately incomplete on internal timing
details — recovering those precisely is the point of the exercise. Use
it as an orientation document, then study `gate_netlist.v` and
`obfuscated_rtl.v` to pin down the exact cycle-by-cycle behavior.

## What we know about the block's function

The block is a **programmable-duty-cycle complementary PWM generator**.
It produces two output drive signals intended for the high-side and
low-side switches of a half-bridge. Because both switches share the same
supply rail and ground return through the load, they must never be told
to conduct at the same time — if they were, the two switches would form
a short circuit straight across the supply. Whatever internal logic this
block uses, it clearly exists to prevent that from happening: the two
outputs are complementary, not simply inverses of each other, and from
board-level probing it's evident that a **short safety gap is inserted
between transitions** to avoid the outputs overlapping across a
switching event. The exact width and placement of that gap are not
documented anywhere we could find — that's part of what you need to
recover from the low-level artifacts.

The duty cycle appears to be programmable via a 4-bit input, consistent
with a design that supports 16 discrete duty settings. The switching
period itself appears to be fixed, and board-level clock probing plus
counter bit-width in the gate netlist strongly suggest it is built around
a single internal 4-bit free-running counter, i.e. **a period of exactly
16 clock cycles**.

## Recovered pin-level interface

Cross-referencing pin continuity on the recovered board against the
gate-level netlist, the following pinout and general semantics could be
established:

| Pin (external)   | Internal role                                                         |
|-------------------|------------------------------------------------------------------------|
| Clock input       | Rising-edge system clock                                               |
| Reset input       | Synchronous, **active-high** reset (confirmed active-high by pull-down on this net at board level; no evidence of asynchronous reset behavior in the netlist's clocking structure) |
| Enable input      | Active-high enable, sampled synchronously with the clock              |
| Duty select input | 4-bit programmable duty value, presumably 0–15                        |
| High-side drive   | Registered output driving the upper switch                            |
| Low-side drive    | Registered output driving the lower switch                            |

For the purposes of your recovered word-level module, use these exact
signal names and widths (this is the pinned interface for your
submission, independent of whatever internal names the low-level
artifacts use):

- `clk` — input, 1 bit, rising-edge clock
- `rst` — input, 1 bit, synchronous active-high reset
- `en` — input, 1 bit, active-high enable, sampled synchronously
- `duty` — input, 4 bits, programmable duty value (0–15)
- `pwm_hi` — output reg, 1 bit, high-side drive
- `pwm_lo` — output reg, 1 bit, low-side drive

## What you need to recover

The high-level behavior — a free-running 4-bit counter defining a
16-cycle period, a programmable duty threshold, complementary registered
outputs, and a safety gap around transitions to prevent overlap — is
established above. What is **not** established, and what you must
determine by studying `gate_netlist.v` and `obfuscated_rtl.v` in detail,
includes:

- The exact registered timing relationship between the internal counter
  state and each output (i.e. how many cycles of latency separate the
  counter condition from the corresponding output assertion).
- The precise placement and width of the safety gap at each transition
  boundary — both at the start of the period and at the duty-cycle
  boundary partway through the period. Do not assume it is one cycle,
  zero cycles, or symmetric between the two boundaries without checking
  the logic directly.
- The exact behavior at the extremes of the duty range (very low and
  very high duty settings), where one or both output windows may
  collapse entirely.
- The exact behavior of the counter and outputs while enable is
  deasserted — does the counter freeze, and if so, what do the outputs
  do while it's frozen?
- The exact reset latency — how many cycles after reset is sampled does
  the internal state and each output actually reach its reset value?

Both `gate_netlist.v` and `obfuscated_rtl.v` describe the **same**
underlying design at different levels of abstraction, with different,
non-obvious internal signal names in each. Neither one by itself may be
easy to read directly, but cross-referencing the two — matching up
counter bits, comparator-like structures, and register update timing
between the gate-level and RTL-level descriptions — should let you
converge on one unambiguous, fully specified behavior. That recovered
behavior is what your submitted `pwm_deadtime_gen` module must
reproduce, cycle for cycle, under simulation.