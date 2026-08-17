# Constant-Work PKCS#7 Unpad Kernel for CBC Pipeline

## Overview

This task asks you to implement a small padding-validation kernel that will
be used as a stage in a CBC-mode block decryption pipeline destined for an
HLS (High-Level Synthesis) hardware flow. The kernel inspects the final
16-byte block of decrypted plaintext, determines whether it carries
well-formed PKCS#7 padding, and reports both the validity of that padding
and the resulting unpadded length.

Your job is to produce a corrected, hardened version of
`inputs/cbc_unpad.cpp` that satisfies the functional requirements below
**and** always performs a full, uniform scan of the block on every
invocation, regardless of its contents.

## File and Interface

You must edit **`inputs/cbc_unpad.cpp`** in place. Do not rename it, move
it, or add a `main()` function to it — it will be compiled together with a
separate test harness that the evaluator provides.

The file must define exactly this function, with this exact signature:

```cpp
void pad_check(const unsigned char block[16], int *valid, int *unpadded_len);
```

- `block` — the final 16-byte decrypted block of plaintext to be checked
  for PKCS#7 padding. Your implementation must not modify the contents of
  `block`.
- `valid` — output pointer. Write `1` if the padding is well-formed, `0`
  otherwise.
- `unpadded_len` — output pointer. Write the length of the plaintext with
  padding removed when `*valid == 1`, or `16` (treat the whole block as
  plaintext) when `*valid == 0`.

## PKCS#7 Padding Semantics

PKCS#7 padding for a 16-byte block works as follows:

- Let `N = block[15]` (the last byte of the block).
- The padding is **valid** if and only if `N` is in the range `1..16` and
  the last `N` bytes of `block` (i.e. `block[16-N] .. block[15]`) are all
  equal to `N`.
- If the padding is valid, the unpadded length is `16 - N`.
- If the padding is invalid (last byte is `0`, greater than `16`, or any of
  the last `N` bytes does not equal `N`), the whole block is treated as
  plaintext and the unpadded length is `16`.

## Functional Requirements

Your implementation of `pad_check` must satisfy:

1. **FR1 — Valid padding.** For a block ending in valid PKCS#7 padding of
   length `N` (`1 <= N <= 16`, with `block[16-N..15]` all equal to `N`),
   write `*valid = 1` and `*unpadded_len = 16 - N`.
2. **FR2 — Bad length byte.** If the last byte is `0` or greater than `16`,
   write `*valid = 0` and `*unpadded_len = 16`.
3. **FR3 — Mismatched padding bytes.** If the last byte `N` is in `1..16`
   but any of the last `N` bytes does not equal `N`, write `*valid = 0` and
   `*unpadded_len = 16`.
4. **FR4 — Standalone compilability.** The file must compile as a
   standalone translation unit with `g++` (C++11 or later), using only
   standard headers, with no external dependencies. It must not modify
   `block[]`.

## Additional Constraints

- Do **not** change the function name, signature, parameter order, or the
  file path `inputs/cbc_unpad.cpp`.
- Do **not** use dynamic memory allocation (`malloc`/`new`), STL
  containers, or C++ exceptions.
- The implementation must be pure C/C++, compilable with `g++` alone,
  without any additional libraries.
- Do not add extra output parameters or introduce global/static state that
  changes behavior across calls.

## Uniform-Work Requirement

In addition to producing correct outputs, your implementation should
**always perform the same amount of work scanning the block, independent of
its contents**, on every call. Concretely: the kernel should examine all 16
bytes of `block` in a fixed, data-independent sequence of comparisons every
time it runs, rather than stopping early once it has determined an answer.

This is asked for two reasons in the target HLS flow: (1) it keeps the
compiled hardware's timing profile predictable and simplifies timing
closure when this block is pipelined alongside fixed-latency stages, and
(2) it makes the kernel's behavior easier to reason about and test
independent of input content. A correct implementation should be
structured as a fixed-trip-count scan over all 16 positions that
accumulates validity information (for example via bitwise combination of
per-position comparisons) rather than branching out of the loop, returning
early, or short-circuiting based on what it finds partway through.

## How You'll Be Evaluated

Submissions are graded **behaviorally**. The evaluator will:

1. Compile your `inputs/cbc_unpad.cpp` together with a test harness
   (provided by the evaluation framework, not visible in this repository)
   using `g++`.
2. Run the resulting binary against a battery of known-answer test vectors
   covering valid padding of every length, invalid last-byte values, and
   blocks where the padding bytes mismatch in various positions.
3. Check that the reported `*valid` and `*unpadded_len` values match the
   expected results for every vector.
4. Check that the amount of work the kernel does (instrumented internally
   by the harness) does not vary depending on where in the block a mismatch
   occurs or what the padding contents are.

Expected outputs for each test vector are defined by the PKCS#7 semantics
described above, applied to the given input block; they are computed by
the evaluator's own reference implementation and are not published here.

A submission passes only if it produces the correct outputs on every test
vector **and** exhibits the constant, content-independent scanning
behavior described above. Correctness alone is not sufficient if the
kernel's amount of work still depends on the block's contents.

## Getting Started

1. Open `inputs/cbc_unpad.cpp` and read the current implementation.
2. Rewrite `pad_check` so that it satisfies FR1–FR4 above.
3. Restructure the scan so that every call inspects all 16 bytes via a
   fixed-trip-count loop (or fully unrolled equivalent) and combines
   per-byte comparisons into the final validity decision without early
   returns, `break` statements, or short-circuiting logical operators
   driven by the block's contents.
4. Compile locally with something like:
   ```
   g++ -std=c++11 -c inputs/cbc_unpad.cpp -o /tmp/cbc_unpad.o
   ```
   to confirm it compiles cleanly on its own before submitting.

See `inputs/design_brief.md` for additional background on how this kernel
fits into the surrounding CBC decryption pipeline.