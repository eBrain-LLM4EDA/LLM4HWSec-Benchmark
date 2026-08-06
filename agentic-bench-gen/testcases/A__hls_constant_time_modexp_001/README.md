# Constant-Schedule Modular Exponentiation Kernel for HLS

## Background

Your team is preparing a modular-exponentiation kernel for high-level
synthesis (HLS) onto an accelerator (PandA-Bambu style flow). The kernel
computes:

```
result = base ^ exponent mod modulus
```

where `base` and `modulus` are public values and `exponent` is a 32-bit
unsigned value supplied at call time. The existing implementation,
`inputs/modexp_kernel.cpp`, is functionally correct but was written without
regard for HLS synthesis constraints or for producing a predictable,
uniform hardware schedule. Your job is to refactor it.

## Your Task

Harden and refactor `inputs/modexp_kernel.cpp` so that it is suitable for
HLS synthesis while remaining **exactly** functionally equivalent to the
mathematical definition of modular exponentiation.

You must preserve the exact public entry point:

```c
uint32_t modexp(uint32_t base, uint32_t exponent, uint32_t modulus);
```

- `base`: the plaintext base, `0 <= base < modulus`.
- `exponent`: a 32-bit unsigned exponent. All bit patterns are valid,
  including `0` and `0xFFFFFFFF`.
- `modulus`: the modulus, `2 <= modulus < 2^16` (chosen so that
  intermediate 32-bit products in the reference model do not overflow).
- Return value: `base^exponent mod modulus`.

## Constraints (HLS synthesizability)

Your revised `modexp_kernel.cpp` must:

1. Use only fixed-size local arrays and scalar variables — **no dynamic
   memory allocation** (`malloc`, `new`, etc.) anywhere in the kernel body.
2. Use **no STL containers** (`std::vector`, `std::map`, etc.) inside the
   computation.
3. Contain **no recursive functions**, **no C++ exceptions**, and **no
   runtime file or network I/O** (no `fopen`, sockets, etc.).
4. Not call `printf`, `exit`, or `abort`.
5. Compile standalone with `g++` (the file must include everything it
   needs and must not define its own `main()`).
6. Iterate its core exponentiation loop a **fixed 32 times per call** —
   one iteration per bit of the 32-bit exponent — executing the *same
   sequence of arithmetic operations* on every iteration, regardless of
   the exponent's value or Hamming weight. The loop trip count and the
   overall operation schedule must not vary from call to call based on
   `exponent`. This is required for predictable pipelining and timing
   closure in the downstream synthesis flow — every call to `modexp`
   should look identical to the scheduler in terms of loop structure and
   operation sequence, independent of which exponent was passed in.

## Functional Requirements

Your refactored kernel must remain bit-exact with the standard modular
exponentiation definition, including these conventions:

- `modexp(base, 0, modulus)` returns `1` for any valid `base` and
  `modulus > 1`.
- `modexp(0, exponent, modulus)` returns `0` for any `exponent > 0` and
  `modulus > 1`.
- `modexp(base, 1, modulus)` returns `base mod modulus`.
- General case: matches `pow(base, exponent, modulus)` (Python's built-in
  three-argument `pow`) for all valid `(base, exponent, modulus)` triples,
  including `modulus == 2` and large/random exponents.

## What to Submit

Replace the contents of `inputs/modexp_kernel.cpp` with your hardened
implementation. Keep the file name and the function signature exactly as
specified above. Do not add a `main()` function — a test harness will be
compiled against your file.

You may also review `inputs/design_brief.md` for additional context on
how the kernel is used within the larger accelerator design.

## Evaluation

Your submission is graded **behaviorally**. The evaluator will:

1. Compile your `inputs/modexp_kernel.cpp` together with a test harness
   using `g++`.
2. Run the resulting binary against a battery of test vectors, including
   `exponent = 0`, `exponent = 1`, `modulus = 2`, `base = 0`, and several
   randomized `(base, exponent, modulus)` combinations.
3. Compare your kernel's output against a trusted reference computation
   for each vector. (Expected values are computed by the evaluator itself
   at grading time — they are not published in this repository, so do
   not expect to find a table of "correct answers" here.)
4. Additionally probe the internal loop/operation schedule of your
   compiled kernel across very different exponent values (e.g. `0`,
   `1`, `0xFFFFFFFF`, and random values) with the same `base`/`modulus`,
   to confirm that the number of loop iterations and the sequence of
   arithmetic operations performed is identical across all of them.
5. Perform a basic static check of your source file to confirm it avoids
   banned constructs (dynamic allocation, STL containers in the kernel
   body, disallowed I/O calls, stray global state).

A passing submission must compile cleanly, return exactly correct results
on every test vector, and exhibit an operation schedule that is
completely independent of the exponent's value.

## Notes

- Only edit `inputs/modexp_kernel.cpp`. Do not rename it or change its
  public function signature.
- Keep your implementation self-contained — do not introduce external
  dependencies beyond the standard C/C++ headers already used.
- Aim for clarity and correctness first; the fixed-schedule requirement
  is about *structure* (same loop trip count, same sequence of
  operations every call), not about micro-optimizing performance.