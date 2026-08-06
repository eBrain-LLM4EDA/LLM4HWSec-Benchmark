# Recovering a Complementary PWM Generator with Dead-Time Insertion

## Objective

You have been handed the remains of an undocumented gate-driver IP block,
recovered from a legacy motor-controller design with no accompanying
documentation. Your job is to reverse engineer its true behavior from the
low-level artifacts provided and re-express it as clean, word-level
Verilog.

The block is a **4-bit-programmable complementary PWM generator** with a
fixed 16-clock period. It drives the two switches of a half-bridge gate
driver and must insert a short safety gap around every duty-cycle
transition so the two switches are never told to conduct at the same time.

You must recover the exact cycle-accurate behavior — not just something
that "looks like" a PWM waveform — and submit it as a single, clean
Verilog module.

## Input artifacts (`inputs/`)

- **`design_brief.md`** — plain-English description of the block's role,
  pinned port list, and general behavioral framing. Use this to orient
  yourself before diving into the low-level artifacts.
- **`obfuscated_rtl.v`** — a synthesizable RTL wrapper for the block, but
  with renamed ports/signals and flattened boolean logic. It implements
  the real behavior, just obscured.
- **`gate_netlist.v`** — a gate-level netlist (primitive gates plus a
  locally defined flip-flop cell) realizing the same function at an even
  lower structural level, again with generic, renamed signals.

These three artifacts describe **one unambiguous design**. Cross-reference
them against each other and against the port/timing contract below to
converge on the exact recovered behavior. Do not assume any single
artifact by itself gives you the full picture — the netlist and the
obfuscated RTL use different internal signal names and different
structural styles, but they implement the identical function.

## Required output

Submit your recovered design at:

```
submission/recovered_rtl.v
```

It must contain a single Verilog module named exactly:

```
pwm_deadtime_gen
```

with exactly this port list (names and widths must match precisely):

| Port      | Direction | Width | Description                                   |
|-----------|-----------|-------|------------------------------------------------|
| `clk`     | input     | 1     | Rising-edge clock                              |
| `rst`     | input     | 1     | Synchronous, active-high reset                 |
| `en`      | input     | 1     | Active-high enable, sampled synchronously      |
| `duty`    | input     | [3:0] | Programmable duty value, 0-15                  |
| `pwm_hi`  | output reg| 1     | High-side complementary drive                  |
| `pwm_lo`  | output reg| 1     | Low-side complementary drive                   |

The module must be a **single, self-contained file**, compilable
standalone with `iverilog` — no vendor/proprietary primitives, no
external libraries, no dependency on `gate_netlist.v` or
`obfuscated_rtl.v` at compile time.

## Constraints

- Internal timing is built around a **4-bit counter with a fixed period
  of 16 clock cycles**. No other period length is acceptable.
- Reset is **synchronous, active-high only** — do not use an asynchronous
  reset.
- `pwm_hi` and `pwm_lo` are registered (Moore) outputs, one cycle behind
  the internal counter state, per the timing contract you are given
  separately in the task interface description.
- The two input reference artifacts (`gate_netlist.v`, `obfuscated_rtl.v`)
  are for reverse-engineering purposes only. Do not submit them as-is or
  assume they can simply be repackaged — their signal names are flattened
  and renamed and must be reconstructed at the clean word level in your
  submission.

## What your recovered design must get right

Your submission will be checked against a set of functional requirements
and safety requirements. You don't need to know the internal grading
mechanics to pass — just make sure your recovered design satisfies all of
the following, for every duty value and every enable/reset pattern that
can reasonably occur:

**Functional requirements:**
- **FR1** — Correct high-side and low-side assertion windows for a
  representative duty value, held enabled, across multiple periods.
- **FR2** — No overlap between `pwm_hi` and `pwm_lo` for every duty value
  0 through 15, held enabled, across multiple periods.
- **FR3** — Correct edge-case behavior at the extremes of the duty range
  (very low duty values where the high side never asserts, and very high
  duty values where the low side never asserts).
- **FR4** — Correct hold behavior when `en` is deasserted: the internal
  counter must freeze, and the outputs must settle to and remain at
  whatever value the held counter/duty combination implies.

**Safety requirements:**
- **SR1** — The two outputs must never be observed high on the same clock
  cycle, for any duty value and any enable-toggling pattern, with zero
  tolerance for exceptions.
- **SR2** — The safety gap between switching events must be of the exact
  correct width at both boundaries of the duty window (period restart and
  duty transition) — neither too short nor too long — for the full range
  of interior duty values.

## How you will be evaluated

Your submitted file will be compiled together with an independently
generated testbench and an independently authored reference
implementation, using `iverilog`, and run under `vvp`. The evaluator
observes `pwm_hi` and `pwm_lo` cycle-by-cycle across a broad sweep of
duty values, reset sequences, and enable-hold sequences, and compares
your waveform directly against the reference's waveform. Passing requires
matching the reference exactly, cycle for cycle, with no overlap
violations anywhere in the test sweep.

No expected waveform values, golden traces, or evaluation scripts are
provided in this repository — your job is to derive the correct behavior
from the artifacts and the specification above, not to reverse engineer
the test harness.

## Starting point

`submission/recovered_rtl.v` currently contains a placeholder module with
the correct name and port list but only a naive, incomplete
implementation. It is provided purely as a compileable skeleton so you
can confirm your toolchain setup — it is not a valid answer and will not
pass evaluation. Replace its contents with your recovered design.