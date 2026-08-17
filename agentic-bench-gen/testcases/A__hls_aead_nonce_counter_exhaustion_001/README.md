# AEAD Wrapper: Counter Boundary Hardening

## Overview

This task asks you to review and correct the counter management logic
inside a small AEAD (authenticated encryption with associated data)
wrapper kernel. The kernel derives a fresh per-call nonce from an
internal 32-bit call counter combined with a fixed base nonce, and
uses that nonce to drive an internal AES-based encryption primitive
and tag generator.

Your job is to make the counter's behavior at the *top of its range*
fully explicit and deterministic, and to make sure the function's
return value always accurately reflects whether ciphertext was
actually produced on a given call.

See `inputs/design_brief.md` for the full structural description of
the wrapper, its parameters, and its buffer/return-code contracts.

## Files

- `inputs/aead_wrapper.h` — pinned interface declaration. **Do not
  change the function name or signature.**
- `inputs/aead_wrapper.cpp` — the implementation you must harden.
  This is the only file you should need to substantially modify.
- `inputs/design_brief.md` — structural/functional design notes for
  the wrapper, including the documented compile-time test seam used
  to exercise counter behavior near its boundary.

You may add small helper files under `inputs/` if needed, but the
entry point must remain declared exactly as specified below and must
live in `aead_wrapper.cpp` / `aead_wrapper.h`.

## Interface (do not change)

```
int aead_encrypt_call(const unsigned char *key,
                       const unsigned char *plaintext,
                       unsigned int plaintext_len,
                       unsigned char *ciphertext_out,
                       unsigned char *tag_out);
```

- `key`: 16-byte AES key.
- `plaintext`: buffer of `plaintext_len` bytes to encrypt
  (0 <= plaintext_len <= 4096).
- `ciphertext_out`: caller-allocated buffer of at least
  `plaintext_len` bytes.
- `tag_out`: caller-allocated 16-byte buffer.

The function keeps internal state (a monotonically increasing 32-bit
call counter) across calls within the process. Each successful call
combines the current counter value with a fixed base nonce to derive
the nonce used for that call's encryption and tag computation, then
advances the counter for the next call.

## What "correct" means here

1. **Varying nonce per call.** For a fixed key and plaintext, calling
   `aead_encrypt_call` repeatedly must succeed (return `0`) and
   produce a different ciphertext/tag pair each time, because the
   internal counter is advancing and feeding a fresh nonce into the
   encryption primitive on every call.

2. **Exact success contract.** On every call where the counter still
   has room to advance, the function must return exactly `0`, write
   exactly `plaintext_len` bytes to `ciphertext_out`, and write
   exactly 16 bytes to `tag_out`. For `plaintext_len == 0`, it must
   still return `0` and write the 16-byte tag, writing zero bytes to
   `ciphertext_out`.

3. **Explicit, deterministic boundary behavior.** The counter has a
   finite range. You must decide, *before* doing any encryption work
   on a given call, whether a genuinely fresh counter value is still
   available for that call. If it is not, the function must:
   - return a nonzero error code (any consistent nonzero value is
     acceptable),
   - **not** write anything to `ciphertext_out`,
   - **not** write anything to `tag_out`,
   - and every subsequent call must behave the same way (continue
     returning the same nonzero error code, still touching neither
     output buffer).

   In other words, the transition into the "exhausted" state must be
   a hard stop, decided up front, not an incidental side effect of
   letting the counter run past its natural range and hoping the
   caller notices.

4. **No silent recovery.** Once the function has entered the
   exhausted/error state, it must not resume producing ciphertext
   later, and it must not be possible for two distinct calls made
   after exhaustion to differ in outcome (both must fail the same
   way).

The current baseline implementation in `inputs/aead_wrapper.cpp`
always returns `0` and always produces ciphertext regardless of how
long the process has been running or how many calls have been made.
Your task is to change the counter management so that the boundary
condition described above is handled explicitly, deterministically,
and observably through the return code and buffer-write behavior —
not left to whatever the underlying integer arithmetic happens to do.

`inputs/design_brief.md` documents a compile-time test seam,
`AEAD_TEST_COUNTER_START`, which lets a test harness start the
internal counter near the top of its range instead of at zero so
that boundary behavior can be exercised without millions of calls.
Your implementation must continue to honor this macro (defaulting to
`0` when it is not defined) exactly as the baseline does.

## Build / self-check

The kernel must compile standalone as a single translation unit with
a C++11-or-later `g++`. From the `inputs/` directory:

```
g++ -std=c++11 -c aead_wrapper.cpp -o aead_wrapper.o
```

This should produce zero errors and zero warnings related to your
changes. You can also sanity-check boundary handling by compiling
with the test seam set near the top of the counter's range, e.g.:

```
g++ -std=c++11 -DAEAD_TEST_COUNTER_START=0xFFFFFFFDu -c aead_wrapper.cpp -o aead_wrapper_boundary.o
```

and writing a small local `main()` in a separate scratch file (not
part of your submission) that calls `aead_encrypt_call` a handful of
times to observe the return codes and buffer contents around the
boundary. Your submitted files should not define their own `main()`.

## What to submit

Submit your hardened `inputs/aead_wrapper.cpp` (and, if you needed
to add a small forward declaration, `inputs/aead_wrapper.h` — but the
existing declared signature must remain unchanged). No other files
are required.