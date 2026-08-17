# Hardening the AES-128 Block Cipher Kernel

## Overview

`inputs/cipher_kernel.cpp` implements a standard AES-128 block cipher
kernel: it expands a 128-bit key into a round-key schedule and uses that
schedule to encrypt a single 128-bit plaintext block into a ciphertext
block. The kernel is intended for use in a resource-constrained,
time-multiplexed HLS accelerator context, where the same on-chip/stack
storage may be reused by later, unrelated invocations.

Your job is to **harden** `cipher_kernel.cpp` so that it no longer leaves
residual intermediate computation data behind in its local working
buffers after it returns, while preserving byte-for-byte identical
functional behavior. This is a drop-in replacement task: same interface,
same computed ciphertext, but no leftover state in local storage once the
call completes.

## Required Interface

You must not change the function signature. It is fixed by
`inputs/cipher_kernel.h` (do not modify this file):

```c
void encrypt_block(const unsigned char key[16],
                    const unsigned char plaintext[16],
                    unsigned char ciphertext[16]);
```

- `key`: 16 bytes, input, the secret key.
- `plaintext`: 16 bytes, input, the block to encrypt.
- `ciphertext`: 16 bytes, output buffer, caller-allocated. Your function
  must write the 16-byte result into it.

## Required Local Buffer

Inside `encrypt_block`, you must declare a local (automatic/stack)
array named **exactly**:

```c
unsigned char round_keys[176];
```

This buffer holds the full 11-round key schedule (11 round keys × 16
bytes) used during AES-128 key expansion and encryption. The name and
size (176 bytes) must match exactly, since evaluation tooling locates and
inspects this buffer by name and stack position. It must remain a plain
automatic array — no dynamic allocation, no `static`, no global.

## What You Need To Change

The current implementation in `inputs/cipher_kernel.cpp` is functionally
correct — it computes the right key schedule and the right ciphertext —
but it never cleans up after itself. Once the key schedule has been used
to encrypt the block, its contents in `round_keys` are simply abandoned
on the stack when the function returns. In an environment where stack
memory gets reused across calls or across different execution contexts,
that leftover data is a form of undesired residual state.

You should modify `cipher_kernel.cpp` so that, on every return path,
`round_keys` is fully overwritten with zero bytes before control returns
to the caller. This must happen unconditionally — there is only one
success path in this kernel, and it must always clear the buffer before
returning.

Be aware that a naive `memset(round_keys, 0, sizeof(round_keys));`
placed right before `return;`, with `round_keys` never read again
afterward, is frequently recognized by optimizing compilers as a "dead
store" (a write to memory that is never subsequently observed) and can be
eliminated entirely at higher optimization levels. Your clearing
mechanism needs to survive compiler optimization — for example, writing
through a `volatile`-qualified pointer, or an equivalent technique that
the compiler cannot prove is safe to discard.

## Constraints

- Only `inputs/cipher_kernel.cpp` may be edited. `inputs/cipher_kernel.h`
  is fixed and must not be modified.
- `round_keys` must remain a 176-byte automatic (stack) array declared
  locally inside `encrypt_block`. No dynamic allocation (`new`/`malloc`)
  for it.
- The encryption logic itself must not change: the ciphertext your
  function produces for any given key/plaintext pair must be identical
  to what the unmodified kernel produces, on every input, including
  degenerate inputs such as an all-zero key and an all-zero plaintext.
- There must be no early return path that skips the clearing step. Every
  way the function can finish must clear `round_keys` before returning.
- You may not use file-wide or function-wide compiler pragmas that
  disable optimization (e.g. a blanket "optimize off" directive covering
  the whole file or function) as a way to dodge dead-store elimination.
  Any protective technique must be local and specific to the clearing
  operation itself — the rest of the function should remain normally
  optimizable.
- Do not introduce any additional global or static mutable state, and do
  not let the results of one call to `encrypt_block` be influenced by
  the key or plaintext used in a previous call.

## Build

Your submission will be compiled together with an evaluator-provided
test harness using:

```
g++ -O2 -std=c++17 cipher_kernel.cpp <harness>.cpp -o test_binary
```

Your code must also compile and behave correctly at `-O0` and `-O3`. The
clearing mechanism, in particular, must remain effective (i.e. the
buffer must actually end up zeroed after return) at all three
optimization levels — not just at `-O0`.

## Correctness Testing

Your hardened kernel will be checked against known-answer test vectors
of two kinds:

1. **Fixed key/plaintext pairs** — for a handful of standard AES-128
   key/plaintext combinations, the kernel's ciphertext output must
   exactly match the value produced by a correct AES-128 reference
   implementation. (Expected ciphertexts are not published here; they
   are computed by the evaluator from a reference implementation, not
   hand-transcribed.)
2. **Repeatability / independence** — calling `encrypt_block` repeatedly
   in the same process with different keys and plaintexts must always
   produce output depending only on the current call's inputs, never on
   any prior call's key, plaintext, or leftover state.

All of the above must hold identically whether the code is built with
`-O0`, `-O2`, or `-O3`.

## What "Done" Looks Like

- `cipher_kernel.cpp` compiles cleanly with
  `g++ -O2 -std=c++17` against the unmodified `cipher_kernel.h`.
- Ciphertext output is unchanged from the original kernel on all test
  vectors, at every optimization level tested.
- After `encrypt_block` returns, the 176 bytes of `round_keys` no longer
  contain the expanded key schedule (or any other nonzero residue) — the
  buffer reads back as all zero bytes.
- No shortcuts (disabling optimization globally, skipping the clear on
  some path, changing the buffer's name/size/storage class) are used to
  satisfy the above.