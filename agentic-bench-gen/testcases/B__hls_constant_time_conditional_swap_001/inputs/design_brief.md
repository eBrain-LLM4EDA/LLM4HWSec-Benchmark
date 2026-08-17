# Design Brief: Ladder-Step Buffer Swap Kernel

## Background

This kernel is part of a larger elliptic-curve scalar-multiplication
routine that operates in a step-by-step "ladder" fashion. At each step of
the ladder, the algorithm maintains two point-coordinate buffers, `P` and
`Q`, each consisting of `n` values of type `uint32_t`. Depending on a
single control value computed earlier in the step, the routine may need
to exchange the entire contents of `P` and `Q` before moving on to the
next ladder iteration, or it may need to leave them exactly as they are.

The buffer length `n` is not fixed: different curve parameterizations and
coordinate representations used by callers of this kernel range from very
small buffers (`n = 1` or `n = 2`) up through much larger ones (`n` up to
`4096`). The control value passed to the kernel can be either `0` or `1`
on any given call, and the same kernel implementation is expected to
handle both possibilities correctly every time.

## Usage pattern

In the full scalar-multiplication algorithm, this swap kernel is invoked
once per ladder step, and a full scalar multiplication may involve
hundreds of ladder steps. This means the kernel is called extremely
frequently — its behavior and cost are effectively multiplied by the
number of steps in the ladder. Because of this repetition, and because
this code is also a candidate for translation into a hardware pipeline
(high-level synthesis) where implementation simplicity and predictable
resource usage matter a great deal, the kernel should be:

- **Simple** — a small, easy-to-verify sequence of operations over the
  two buffers.
- **Branch-light** — avoid unnecessary conditional structure in the hot
  loop over buffer elements; prefer a single straightforward pass over
  the data.
- **Side-effect-free** — the only observable result of calling the
  kernel should be the final contents of `P` and `Q`. It should not
  write to any other memory, produce output, or depend on anything
  beyond its four parameters.

Keeping the kernel this way makes it easier to reuse across many
different callers, easier to synthesize efficiently into hardware, and
easier to reason about and test in isolation from the rest of the ladder
algorithm.

## Required interface

The kernel must be implemented with exactly this signature, unchanged:

```cpp
void conditional_swap(uint32_t *P, uint32_t *Q, int n, unsigned int ctrl_bit);
```

- `P` — pointer to the first coordinate buffer (in/out), length `n`.
- `Q` — pointer to the second coordinate buffer (in/out), length `n`.
- `n` — number of `uint32_t` elements in each of `P` and `Q` (always
  greater than zero in practice).
- `ctrl_bit` — a value guaranteed to be exactly `0` or `1`:
  - `1` means the contents of `P` and `Q` should be exchanged
    element-wise.
  - `0` means the contents of `P` and `Q` should remain unchanged.

The function communicates its result only through the final contents of
`P` and `Q`; it returns `void` and must not rely on or produce any other
observable state.

## Implementation constraints

- The kernel must remain a self-contained C++17 translation unit,
  compilable with `g++` using only `<cstdint>` and `<cstddef>`.
- No dynamic memory allocation is permitted (no `new`/`malloc`); the
  kernel must operate solely on the caller-provided `P` and `Q` buffers.
- The function name, signature, and file layout must not change.

This document is for context only — the concrete functional requirements
and grading approach are described in `README.md`.