# Design Brief: NMI/IRQ Arbiter (`nmi_arbiter`)

## Purpose

`nmi_arbiter` is a compact, four-source interrupt arbiter intended for
use in a small microcontroller-class interrupt subsystem. It combines
one non-maskable interrupt (NMI) request with three ordinary,
maskable interrupt request lines (`irq[2:0]`) and produces a single
registered, one-hot grant vector.

## Interface

```
module nmi_arbiter (
    input  wire       clk,      // system clock, rising-edge sampled
    input  wire       rst_n,    // active-low synchronous reset
    input  wire       nmi,      // non-maskable interrupt request
    input  wire [2:0] irq,      // three ordinary IRQ request lines
    output reg  [3:0] grant     // registered one-hot grant vector
);
```

- `clk` — system clock. All sequential behavior is on the rising edge.
- `rst_n` — active-low, synchronous reset.
- `nmi` — single-bit non-maskable interrupt request input.
- `irq[2:0]` — three ordinary interrupt request lines. `irq[0]` is the
  highest-priority ordinary source, `irq[2]` the lowest.
- `grant[3:0]` — registered one-hot grant output. `grant[3]`
  corresponds to the NMI grant; `grant[2:0]` correspond respectively
  to `irq[2:0]`.

## Functional policy

The arbiter implements a strict, fixed-priority policy with exactly
two tiers:

1. **NMI has absolute top priority.** Whenever `nmi` is asserted in a
   given sample cycle, the arbiter must grant the NMI on the
   following clock edge: `grant[3] = 1` and `grant[2:0] = 3'b000`.
   This holds **regardless of the value of `irq[2:0]`** in that same
   cycle — the NMI grant does not depend on, and is never altered by,
   the state of the ordinary IRQ lines. There are no exceptions to
   this rule for any combination of the ordinary IRQ inputs.

2. **When NMI is not asserted, fixed-priority arbitration among the
   ordinary IRQ lines applies:** `irq[0] > irq[1] > irq[2]`. The
   arbiter grants exactly one bit of `grant[2:0]` corresponding to the
   highest-priority asserted `irq` line:
   - If `irq[0] = 1`, grant `grant[0] = 1`.
   - Else if `irq[1] = 1`, grant `grant[1] = 1`.
   - Else if `irq[2] = 1`, grant `grant[2] = 1`.
   - If none of `irq[2:0]` are asserted, `grant = 4'b0000` (no
     grant).

At most one bit of `grant` is ever asserted in any cycle (one-hot),
and `grant[3]` and `grant[2:0]` are mutually exclusive by
construction: NMI, when present, always wins outright.

## Timing behavior

- `grant` is a **registered, one-cycle-latency, Moore-style** output:
  its value on a given rising clock edge reflects the sampled values
  of `nmi` and `irq` from the *immediately preceding* clock edge, not
  the current combinational inputs.
- **Reset:** `rst_n` is a synchronous, active-low reset. On the clock
  edge following any cycle in which `rst_n = 0`, `grant` must be
  driven to `4'b0000`, irrespective of the values of `nmi` and `irq`
  in that cycle.
- In all other cycles (`rst_n = 1`), `grant` is updated each rising
  clock edge according to the priority policy described above, applied
  to the `nmi`/`irq` values sampled at the previous edge.

## Summary truth table (combinational intent, prior to registration)

| `nmi` | `irq[2:0]`    | `grant[3:0]` (next) |
|-------|---------------|----------------------|
| 1     | any value     | `1000`               |
| 0     | `xx1` (irq[0])| `0001`               |
| 0     | `x10`         | `0010`               |
| 0     | `100`         | `0100`               |
| 0     | `000`         | `0000`               |

This table applies uniformly across all 8 possible values of
`irq[2:0]` whenever `nmi = 1`, and across all applicable ordinary
combinations whenever `nmi = 0`. The design should be verified against
this full policy, not merely against a representative subset of input
combinations.