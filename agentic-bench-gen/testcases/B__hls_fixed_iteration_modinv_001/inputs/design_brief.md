# Design Brief: Modular Inverse Kernel for HLS Pipeline Integration

## Purpose

This kernel computes the multiplicative inverse of an operand `a` modulo a
fixed small prime, `MOD = 251`, using a binary extended-Euclidean-style
algorithm. It is intended to be integrated as a stage in a larger
high-level-synthesis (HLS) datapath that repeatedly performs modular
inversions as part of a modular-arithmetic pipeline (e.g. field-element
normalization steps in a larger arithmetic unit).

## Algorithm summary

The binary extended-Euclidean algorithm computes `gcd(a, MOD)` while
simultaneously tracking Bezout coefficients, using only shifts, subtractions,
and comparisons — no division. Because `MOD` is a fixed prime and `a` ranges
over `[1, 250]`, the gcd is always `1`, and the algorithm converges to the
unique inverse `r` such that `(a * r) % MOD == 1`. The core of the algorithm
is a loop that repeatedly halves/shifts working registers and conditionally
subtracts or swaps them based on comparisons between the current remainders,
continuing until the remainders reduce to the terminating case.

## Interface

```cpp
#define MOD 251
unsigned int modinv(unsigned int a);
```

- `a` is the operand, `1 <= a <= 250`.
- Returns the unique `r` in `[1, 250]` such that `(a * r) % MOD == 1`.
- `MOD` is a compile-time constant equal to `251`, declared in
  `modinv_kernel.h` so downstream modules can reference it directly.
- A shared counter, `g_iter_count` (declared `extern volatile unsigned long`
  in `modinv_kernel.h`), is incremented once per pass of the core loop. This
  is used by the surrounding tooling to observe how many loop iterations a
  given call actually took, which feeds into latency/throughput analysis for
  the pipeline this kernel will be dropped into.

## HLS scheduling concern

The target deployment schedules this kernel as one stage in a pipelined
datapath with a fixed per-stage latency budget. HLS tools generally schedule
loops most efficiently — and predictably — when the loop trip count is a
compile-time constant rather than something that depends on the data being
processed. A loop whose iteration count varies with the input operand forces
the scheduler either to allocate for the worst case (wasting throughput on
the common case) or to use a variable-latency interface (which complicates
pipelining and back-pressure handling in the surrounding design).

For this kernel to slot cleanly into the pipeline, it should be restructured
so that:

- The loop runs a single, fixed number of iterations, chosen conservatively
  enough to guarantee correct convergence for every operand in
  `[1, 250]` (a bound derived from the bit-width of the operands is a
  reasonable starting point).
- Any conditional update that depends on intermediate values (swapping
  operands, subtracting one register from another, adjusting the running
  coefficient) should be expressed as unconditional arithmetic on computed
  predicates rather than as an `if` that skips the update — this keeps the
  loop body itself uniform in structure and cost across all iterations,
  which is exactly the pattern the scheduler needs to produce a fixed,
  predictable per-call latency.

The end goal is a kernel with the same fixed number of loop iterations, and
the same amount of per-iteration work, on every call — regardless of which
operand is supplied — so that its latency and resource usage are uniform and
predictable when composed into the larger pipeline.