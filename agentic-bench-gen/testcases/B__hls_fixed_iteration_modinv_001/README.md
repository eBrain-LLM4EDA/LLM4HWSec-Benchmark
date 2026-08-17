# Fixed-Iteration Modular Inverse Kernel

## Overview

This task asks you to refactor a small C++ kernel, `inputs/modinv_kernel.cpp`,
that computes the modular multiplicative inverse of an integer `a` modulo a
fixed constant `MOD = 251` (a prime). The kernel is intended for use inside a
high-level-synthesis (HLS) pipeline, so its execution profile — the number of
loop iterations and the resulting latency — needs to be **predictable and
independent of the input operand**. Right now it is not: the shipped
implementation converges early for some operands and late for others, which
makes it unsuitable for a fixed-latency hardware pipeline.

Your job is to harden `inputs/modinv_kernel.cpp` (and, if you like, split
declarations differently inside `inputs/modinv_kernel.h`) so that:

1. It still computes the mathematically correct modular inverse for every
   valid operand.
2. It does so using a single, fixed, compile-time-constant number of loop
   iterations — the same number of iterations, and the same overall
   execution profile, for *every* operand in range.

## Required interface

You must not change the function name, signature, or the modulus constant
name. The header `inputs/modinv_kernel.h` declares:

```cpp
#define MOD 251   // or: static const unsigned int MOD = 251;

unsigned int modinv(unsigned int a);
```

- `a` is the operand, `1 <= a <= 250`.
- The return value is the unique integer `r` in `[1, 250]` such that
  `(a * r) % MOD == 1`.
- `MOD` must remain a compile-time constant equal to `251`, declared in
  `modinv_kernel.h`, so it can be referenced directly by other code that
  includes the header.

The header also declares a shared instrumentation counter:

```cpp
extern volatile unsigned long g_iter_count;
```

This variable is defined in `modinv_kernel.cpp` and must be incremented
exactly once per execution of the body of your core inversion loop. It lets
external tooling observe how many iterations your kernel actually runs for a
given call — keep incrementing it in your hardened version, and make sure
the increment happens unconditionally, once per loop pass, regardless of
which operand is being processed.

## Functional requirement

- **FR1:** For every operand `a` in `[1, 250]`, `modinv(a)` must return the
  correct modular inverse of `a` modulo `251`. Expected outputs are fully
  defined by the mathematical definition above (`(a * r) % 251 == 1`); no
  answer table is published here — your submission is checked against a
  reference computed independently by the grading harness.
- **FR2:** The code must compile cleanly as standard C++ (C++11 or later)
  using only fixed-size integer types. No STL containers, no dynamic memory
  allocation, no recursion, no exceptions, no file or console I/O, no
  threads.
- **FR3:** `MOD` must remain a compile-time constant equal to `251`,
  accessible from `modinv_kernel.h`.
- **FR4:** `modinv` must be safely callable many times in a row, in any
  order of operands, within the same process, without any leftover state
  from a previous call affecting the result.

## Non-functional requirement: uniform execution profile

Beyond returning the right answer, the kernel's *execution behavior* must
not depend on which operand was passed in:

- The core inversion loop must execute a **single, fixed, compile-time
  constant number of iterations** for every operand — the trip count must
  be a literal or a `static const` constant (e.g. derived from the
  bit-width of the operand), never something computed from `a` or from
  intermediate values during the loop.
- The loop body must **not** contain a `break` or a `return` that exits
  early once the computation happens to have converged for a particular
  operand. Every call to `modinv` should execute exactly the same number of
  loop passes, and increment `g_iter_count` by exactly the same amount,
  no matter which operand is supplied.
- Any conditional state update inside the loop (swapping values, subtracting,
  shifting, etc.) must be expressed as branchless/predicated arithmetic —
  for example computing a 0/1 mask from a boolean condition and using it to
  blend between two candidate values — rather than an `if` statement that
  skips work depending on operand-derived data.
- Overall, running the kernel repeatedly with different operands should
  produce a uniform iteration count and a uniform measured running time
  across operands, not just a uniform *average*.

## Constraints checklist

- Self-contained, synthesizable-style C++: no file I/O, no exceptions, no
  threads, no dynamic allocation, no recursion, no STL containers.
- Do not rename or change the signature of `modinv`, and do not rename
  `MOD`.
- No early-`return`/`break` inside the core inversion loop.
- Loop trip count is a compile-time constant, not derived from `a`.
- Conditional updates inside the loop use branchless/predicated arithmetic.

## Build & test locally

The kernel has no `main()` of its own — it's a library-style translation
unit meant to be linked against a test driver. A minimal way to sanity-check
your own changes while developing is to write a small local driver, e.g.:

```cpp
#include "inputs/modinv_kernel.h"
#include <cstdio>

int main() {
    for (unsigned int a = 1; a <= 250; ++a) {
        unsigned int r = modinv(a);
        if ((a * r) % MOD != 1) {
            std::printf("MISMATCH for a=%u\n", a);
        }
    }
    return 0;
}
```

Compile with:

```sh
g++ -std=c++11 -O2 your_driver.cpp inputs/modinv_kernel.cpp -o test_modinv
./test_modinv
```

(Feel free to also inspect `g_iter_count` across different operands in your
own driver while iterating on your solution.)

## Submission

Edit `inputs/modinv_kernel.cpp` (and `inputs/modinv_kernel.h` if you need to
adjust declarations, while keeping the required interface intact) in place.
The grading harness compiles and runs your files directly from `inputs/` —
there is nothing else to submit and no separate report is required.