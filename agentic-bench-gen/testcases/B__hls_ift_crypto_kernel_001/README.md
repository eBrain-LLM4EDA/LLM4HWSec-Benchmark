# Uniform-Timing XOR-Stream Cipher Kernel for HLS Synthesis

## Overview

This task asks you to harden a small C kernel that implements a byte-wise
XOR-stream cipher, intended to be synthesized with an HLS toolchain in the
style of PandA-Bambu. The kernel must be written in a strict, synthesis-friendly
subset of C and must produce **well-defined, deterministic behavior for every
valid input**.

The file you need to edit is:

```
inputs/kernel.c
```

The current implementation in that file has inconsistent behavior for
certain key values, which causes incomplete output and inconsistent
status/iteration counts depending on what's in the key buffer. Your job is
to rework the control flow so the kernel always fully processes the entire
buffer and always reports a single, consistent status/iterations pair for
any valid `len` and any key content.

## Required Interface

You must implement exactly this function signature, in a single file
`inputs/kernel.c`:

```c
#define MAX_LEN 64   /* must be a compile-time constant, >= 64 */

void xor_cipher_kernel(const unsigned char plaintext[MAX_LEN],
                        const unsigned char key[MAX_LEN],
                        int len,
                        unsigned char ciphertext[MAX_LEN],
                        int *status,
                        int *iterations);
```

Do not rename the function, change the parameter order, or alter the
meaning of any parameter. `MAX_LEN` must be defined with `#define` in the
same file and must be at least 64.

### Parameters

- **plaintext** — input buffer of bytes to encrypt. Only the first `len`
  bytes are meaningful.
- **key** — input buffer of bytes used to XOR against the plaintext. Only
  the first `len` bytes are meaningful.
- **len** — number of valid bytes in `plaintext` and `key`; guaranteed to
  satisfy `len <= MAX_LEN` for all inputs you need to handle correctly.
- **ciphertext** — output buffer. For every `i` in `[0, len)`, you must
  write `ciphertext[i] = plaintext[i] ^ key[i]`. Bytes at index `>= len`
  are unspecified and not checked.
- **status** — output status code written through the pointer. `0` means
  success. This kernel only needs to define behavior for `len <= MAX_LEN`;
  for any such call, the success code must always be reported.
- **iterations** — output counter written through the pointer. It must
  reflect exactly how many bytes were processed, i.e. it must always equal
  `len` on a valid call.

## Engineering Constraints

Because this code is meant to be synthesized by an HLS tool, it must stay
within a restricted, predictable subset of C:

- No `malloc`, `calloc`, or `free` — use only fixed-size arrays.
- No recursion.
- No STL or other dynamic containers (this is plain C, but the same rule
  applies if you use C++ constructs).
- No loops whose trip count depends on buffer contents — loop bounds must
  be derived only from `len` (which is bounded by the fixed `MAX_LEN`),
  never from the data being processed.
- Everything must live in the single file `inputs/kernel.c`.
- The file must compile cleanly with `gcc -Wall -Wextra` (and `g++` if
  compiled as C++): no errors, and no warnings about implicit declarations
  or type mismatches.
- Do not add a `main()` function to this file — it will be linked against
  a separate test harness.

## What to Fix

The current kernel has a bug: for certain key contents, it produces
**incomplete ciphertext output** and **inconsistent status/iteration
values** — the function stops processing partway through the buffer
instead of always handling all `len` bytes the same way every time.

Your task is to rework the kernel so that:

1. It always processes **all `len` bytes**, every single call, regardless
   of what values appear in `plaintext` or `key`.
2. It always writes the full, correct ciphertext for every index
   `i < len`.
3. It always reports the same success status for any call with
   `len <= MAX_LEN`, no matter what the key contains.
3. `iterations` always ends up equal to `len` exactly, on every call.

In short: the kernel's externally observable behavior (status and
iterations) should depend only on `len`, and the ciphertext output should
always be complete and correct — there should be no data-dependent branch
that causes the kernel to stop early or report a different outcome based
on the contents of the buffers.

## How You'll Be Evaluated

Your submitted `inputs/kernel.c` will be:

1. **Compiled** with `gcc`/`g++` using standard flags. It must build
   cleanly with no errors (warnings about implicit declarations or type
   mismatches will also be treated as failures).
2. **Run against a battery of test vectors**, including many trials with
   the same `plaintext`/`len` but different randomly generated `key`
   contents (including edge cases such as all-zero keys and keys with
   scattered zero bytes). The harness checks that:
   - the ciphertext output is correct (`plaintext[i] ^ key[i]`) for every
     trial and every valid index,
   - the `status` output is identical across all trials,
   - the `iterations` output equals `len` on every trial.
3. **Scanned for a small set of disallowed source constructs** — dynamic
   memory allocation, recursion, and loops whose bound is not tied to
   `len` — as a basic code-quality/synthesizability check. Presence of any
   of these will cause the submission to fail this check regardless of
   runtime behavior.

A correct, hardened submission compiles cleanly and produces fully
consistent, correct behavior across all of the above checks.