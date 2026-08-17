# Constant-Time Conditional Swap for a Scalar-Multiplication Ladder

## Objective

`inputs/ladder_swap.cpp` contains a small kernel used in an elliptic-curve
point-doubling/addition ladder step. It maintains two coordinate buffers,
`P` and `Q`, each an array of `uint32_t` of length `n`, and conditionally
exchanges their contents element-wise based on a single control bit.

Your task is to harden this file so that it always produces exactly the
same swap results as described below, for both possible control values,
across the full required range of array sizes, while also being robust
against implementation choices that make its execution behavior vary with
the control value itself (control flow, memory access pattern, and timing
should all be independent of which control value was passed in).

You must not change the file name or the function signature. Submit your
revised file in place of `inputs/ladder_swap.cpp`.

## Required interface

```cpp
void conditional_swap(uint32_t *P, uint32_t *Q, int n, unsigned int ctrl_bit);
```

- `P` — pointer to the first coordinate buffer (in/out), length `n`.
- `Q` — pointer to the second coordinate buffer (in/out), length `n`.
- `n` — number of `uint32_t` elements in each of `P` and `Q` (always > 0 in tests).
- `ctrl_bit` — selector value, guaranteed by the caller to be exactly `0` or `1`.
  - When `ctrl_bit == 1`, the contents of `P` and `Q` must be exchanged element-wise.
  - When `ctrl_bit == 0`, the contents of `P` and `Q` must remain unchanged.

The function returns `void` and communicates its result solely by mutating
the contents pointed to by `P` and `Q` in place. No other global state,
files, or standard output may be used.

## Functional requirements

- **FR1** — For `ctrl_bit == 1` and arbitrary arrays `P` and `Q` of length
  `n`, after the call the contents of `P` and `Q` must be exactly swapped
  (new `P` equals old `Q`, new `Q` equals old `P`) for every index from
  `0` to `n-1`.
- **FR2** — For `ctrl_bit == 0` and arbitrary arrays `P` and `Q` of length
  `n`, after the call the contents of `P` and `Q` must be exactly
  unchanged from their values before the call.
- **FR3** — The function must handle `n` in the range `1` to `4096`
  (inclusive) without buffer overrun, memory corruption, or crash. This
  will be verified across multiple sizes, including `n = 1`, `n = 2`,
  `n = 64`, and `n = 4096`.
- **FR4** — `inputs/ladder_swap.cpp` must compile cleanly with
  `g++ -std=c++17 -Wall -Wextra` with zero errors, and must be linkable
  against an external test harness that declares and calls
  `conditional_swap` with the exact signature given above.

## Constraints

- The file must remain self-contained C++17 and compile with `g++` using
  only `<cstdint>` and `<cstddef>`.
- Do not rename the function, change its signature, or split its logic
  across multiple translation units.
- Do not use dynamic memory allocation (no `new`/`malloc`); operate only
  on the caller-provided buffers.
- The function must not print, log, or otherwise expose `ctrl_bit` or any
  intermediate values through side channels other than the final contents
  of `P` and `Q`.

## How you will be graded

Your submitted `inputs/ladder_swap.cpp` will be compiled with
`g++ -std=c++17 -Wall -Wextra` against an evaluator-provided test harness
(not included in this repository) and then executed. Grading is entirely
behavioral: the harness calls `conditional_swap` with a range of `n`
values and both control values, compares the resulting buffer contents
against the expected swap/no-swap semantics, and also exercises the
implementation under additional automated checks that observe its runtime
behavior (such as how much work it does and how long it takes) for each
control value.

To do well on all of these checks, your implementation should:

- Produce byte-exact correct results for every required functional
  scenario (FR1–FR3).
- Perform the *same sequence of operations* on `P` and `Q` — the same
  loop structure, the same number of iterations, the same memory
  accesses — no matter which control value is passed in. Avoid writing
  the swap decision as an `if`/ternary/loop-bound/short-circuit condition
  that depends on `ctrl_bit` (or on anything derived from it). Prefer
  arithmetic/bitwise techniques that compute the same instructions for
  either control value and let the *data*, not the *control flow*,
  determine whether a swap happened.
- Avoid any variation in execution time between the two control values
  beyond ordinary system noise. Implementations that skip a whole loop or
  block of work for one control value but not the other are likely to
  fail this check even if their functional output is correct.

A correct, hardened submission should pass every check above. A naive
implementation that simply branches on `ctrl_bit` to decide whether to
swap will produce correct functional results but will fail the
behavioral checks that look at execution pattern and timing consistency
between the two control values — so functional correctness alone is not
sufficient to pass.

## Files

- `inputs/ladder_swap.cpp` — the file you must revise and resubmit in
  place.
- `inputs/design_brief.md` — background context on how this kernel is
  used within the larger ladder computation.

Submit only the revised `inputs/ladder_swap.cpp`. No other answer file is
required.