# Design Brief: `lfsr_rng` — 8-bit LFSR Random Number Generator Core

**Document type:** Functional design specification
**Module:** `lfsr_rng`
**Revision:** 1.2

## 1. Overview

`lfsr_rng` is an 8-bit linear-feedback shift register (LFSR) core intended
for use as a general-purpose pseudorandom bit-sequence generator. It
provides a synchronous handshake output (`output_valid`) and an integrated
health-monitoring feature intended to give downstream consumers confidence
that the generator is producing a well-distributed, non-degenerate output
sequence.

This document describes the intended functional behavior of the core. It is
provided for integration purposes and does not include implementation-level
(RTL) detail.

## 2. Port List

| Signal | Direction | Width | Description |
|---|---|---|---|
| `clk` | input | 1 | System clock, posedge-active. |
| `rst_n` | input | 1 | Active-low synchronous reset. |
| `enable` | input | 1 | Advance control. |
| `rand_out` | output | 8 | Current pseudorandom output word. |
| `output_valid` | output | 1 | Output validity handshake. |
| `health_error` | output | 1 | Health monitor alarm. |

## 3. Reset Behavior

The core uses a **synchronous, active-low reset**. While `rst_n` is held
low, on the next rising edge of `clk` the internal LFSR state register must
be loaded with the fixed seed value `8'hA5`. While in reset:

- `output_valid` must be driven to `0`.
- `health_error` must be driven to `0`.

No other seed value is supported. The seed `8'hA5` is chosen so that the
generator's initial state is non-zero, which is required for correct LFSR
operation (an all-zero state is a degenerate fixed point for a Fibonacci
LFSR and must never occur in normal operation).

## 4. Sequence Generation

`lfsr_rng` implements a **Fibonacci-configuration LFSR** over an 8-bit state
register. On each clock edge for which `enable` is asserted, the register
advances by one step: a new feedback bit is computed as the XOR of a fixed
set of tap bits from the current state, and the register shifts, with the
feedback bit entering at one end.

The generator is specified against the primitive feedback polynomial:

```
x^8 + x^6 + x^5 + x^4 + 1
```

Using the standard 1-indexed tap convention (bit 1 = LSB of the shift
register, bit 8 = MSB), this polynomial corresponds to XOR taps at bit
positions **8, 6, 5, and 4**. All four taps must participate in the
feedback computation on every advance step.

When `enable` is deasserted (`enable == 0`), the internal state register
must hold its current value; no advance occurs and `rand_out` does not
change.

`rand_out` is defined as the current value of the internal state register,
available combinationally (i.e. it reflects the state register's value in
the same cycle, with no additional output register delay beyond the state
register itself).

### 4.1 Expected Cycle Length

A correctly implemented 8-bit Fibonacci LFSR using all four specified taps
of the polynomial above is a maximal-length sequence generator. Starting
from any non-zero seed (including the specified seed `8'hA5`), the
generator is expected to visit all 255 non-zero 8-bit states exactly once
before repeating, giving a **maximal period of 255 clock cycles** (with
`enable` held continuously high). Integrators relying on this core for
nonce, mask, or dithering purposes should expect this full-period behavior
as the baseline guarantee of the design.

This document does not specify the internal Verilog expression used to
compute the feedback bit; that is an implementation detail of the RTL.

## 5. Output Valid Handshake

`output_valid` is a registered output. Following reset, once `enable` is
first asserted, `output_valid` must be asserted exactly **one clock cycle**
later, and must remain asserted continuously thereafter for as long as
`enable` remains high. Consumers of `rand_out` should treat samples
produced while `output_valid` is low as not yet meaningful.

## 6. Health Monitor

`lfsr_rng` includes a built-in health-monitoring feature intended to detect
gross degeneracy in the output sequence (for example, a stuck or
short-cycling generator) without requiring a full statistical test suite.
The health monitor is implemented as a compact **repetition counter**: it
tracks the number of consecutive clock cycles (while `output_valid` is
high) for which `rand_out` holds the same value as the immediately
preceding valid sample.

If this repetition counter observes **more than 4 consecutive identical
`rand_out` samples** while `output_valid` is high, the core must assert the
`health_error` output within at most 3 clock cycles of that condition being
reached. Once asserted, `health_error` must remain asserted continuously
until the next reset (it is a latched/sticky alarm, not a pulse).

Integrators are expected to treat `health_error == 0` as an indication that
the generator has not exhibited the specific repetition pattern described
above during the current operating session since the last reset.

This document does not specify the internal Verilog expression used to
implement the repetition counter or the alarm condition; that is an
implementation detail of the RTL.

## 7. Timing Summary

| Event | Required Timing |
|---|---|
| Reset load of seed `8'hA5` | Next `posedge clk` while `rst_n == 0` |
| `output_valid` first assertion | 1 cycle after `enable` first asserted post-reset |
| `output_valid` de-assertion | Only on reset or `enable` deasserted before first assertion |
| `health_error` assertion | Within 3 cycles of >4 consecutive identical `rand_out` samples (while `output_valid` high) |
| `health_error` clear | Only on next reset |

## 8. Non-Goals

This core is not intended to provide cryptographic-strength randomness. It
is intended for applications such as test-pattern generation, dithering,
and simple masking where a long-period, well-distributed pseudorandom
sequence with a basic built-in sanity check is sufficient.

*(End of design brief.)*