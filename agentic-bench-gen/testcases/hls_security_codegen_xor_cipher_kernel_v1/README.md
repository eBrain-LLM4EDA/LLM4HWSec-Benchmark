# Constant-Behavior XOR-Cipher HLS Kernel — Eliminating Key-Dependent Status/Iteration Leakage

## Task

`inputs/crypto_kernel.c` implements a small HLS-style XOR stream-cipher block
kernel. It takes a **secret** 16-byte key and a **public** 16-byte plaintext,
produces a 16-byte ciphertext, and reports two additional **public**
diagnostic values used for HLS instrumentation: a checksum-style status code
and a loop-iteration counter.

The shipped file currently in `inputs/crypto_kernel.c` is a **functional but
intentionally insecure baseline**. Your job is to replace it in place with a
**security-hardened** version that preserves the exact interface and the
exact cryptographic transform, but removes every trace of key-dependent
behavior from the diagnostic outputs and control flow.

You must not modify any other file. Only `inputs/crypto_kernel.c` is graded.

## Required interface (must match byte-for-byte)

```c
#include <stdint.h>
#include <string.h>

#define HLS_BLOCK_SIZE 16

void crypto_kernel(const uint8_t plaintext[HLS_BLOCK_SIZE],
                    const uint8_t key[HLS_BLOCK_SIZE],
                    uint8_t ciphertext[HLS_BLOCK_SIZE],
                    int *status_out,
                    unsigned int *iter_count_out);
```

- `plaintext` — public input, 16 bytes.
- `key` — **SECRET** input, 16 bytes. Must never influence `status_out`,
  `iter_count_out`, control flow, or any output other than `ciphertext`.
- `ciphertext` — public/declassified output, 16 bytes. The **only** channel
  through which key-derived data may legitimately appear, computed as
  `ciphertext[i] = plaintext[i] ^ key[i]` for `i = 0..15`.
- `status_out` — public diagnostic output. Must equal the XOR-fold checksum
  of the plaintext bytes cast to `int`:
  `status = (int)(plaintext[0] ^ plaintext[1] ^ ... ^ plaintext[15])`.
  Must be a pure function of `plaintext` only.
- `iter_count_out` — public diagnostic output. Must always be set to exactly
  `HLS_BLOCK_SIZE` (16), since the kernel must always fully process the
  fixed-size block regardless of any input content.

No other entry points, no `main()`, and no headers beyond `<stdint.h>` and
`<string.h>` are permitted.

## Objective

1. `ciphertext[i] == plaintext[i] ^ key[i]` for every `i`, for every valid
   (plaintext, key) pair.
2. `status_out` equals the XOR-fold checksum of the plaintext bytes, **and
   is completely invariant with respect to the key** — for a fixed
   plaintext, every distinct key value must produce the same `status_out`.
3. `iter_count_out` always equals `16`, for every key value, with no
   early return, break, or continue gated on key content.

## Constraints

- The kernel must remain synthesizable-style C:
  - Fixed-size arrays only — no `malloc`/`new`, no recursion.
  - All loops must have a compile-time-constant trip count of exactly
    `HLS_BLOCK_SIZE` (16) — no data-dependent loop bounds.
  - No global mutable state may be used to smuggle information between
    separate invocations of `crypto_kernel`.
- The file must compile cleanly, standalone, with **both** `gcc` and `g++`,
  using only `<stdint.h>` and `<string.h>`.
- The function signature, parameter order, and parameter types must match
  the pinned interface exactly.

## Current baseline (why it fails)

The shipped `inputs/crypto_kernel.c` contains a secret-dependent early-exit:

```c
if (key[0] == 0) {
    *status_out = 1;
    *iter_count_out = 0;
    /* ciphertext left incorrect on this path */
    return;
}
/* ... otherwise runs the real 16-iteration XOR loop,
   computes the real checksum, and sets iter_count_out = 16 ... */
```

This branches on secret key material *before* the main loop completes. As a
result:

- `status_out` and `iter_count_out` both change value depending solely on
  whether `key[0] == 0`, leaking one bit of the secret key through outputs
  that are supposed to be public and key-independent.
- The ciphertext computation is skipped/incorrect on that branch, meaning
  the kernel also fails basic functional correctness for that class of key.

This baseline will **fail** the invariance battery even though it may pass
some functional vectors that don't happen to use a `key[0] == 0` key.

## Threat model

An attacker can invoke `crypto_kernel` repeatedly with a fixed,
attacker-chosen public plaintext while the secret key varies across many
unknown values, including adversarially chosen edge-case keys:

- all-zero key
- key with `key[0] == 0` (other bytes nonzero)
- key with `key[15] == 0`
- all-`0xFF` key
- high-entropy pseudo-random keys (fixed seed)

The attacker observes only the public ciphertext, the public `status_out`,
and the public `iter_count_out`. The attacker must **not** be able to
distinguish any two different secret keys, or infer any bit of key
material, from variation in `status_out` or `iter_count_out`. Only
ciphertext may vary with the key, and only in the exact
plaintext-XOR-key relationship.

## CWEs addressed

- **CWE-208** — Observable Timing/Behavioral Discrepancy
- **CWE-203** — Observable Discrepancy
- **CWE-385** — Covert Timing (generalized: covert behavioral) Channel
- **CWE-200** — Exposure of Sensitive Information to an Unauthorized Actor

See `inputs/cwe_list.md` for details, and `inputs/security_spec.md` for the
full restated specification.

## How evaluation works

`evaluate.py` (built independently by the grading harness, not shipped in
this repo) will:

1. Compile `inputs/crypto_kernel.c` standalone with both `gcc` and `g++`
   against a generated test harness `main()`.
2. Run known-answer functional test vectors and check
   `ciphertext == plaintext ^ key` for every vector.
3. Run a behavioral invariance battery: for a fixed plaintext, sweep across
   **≥200 distinct keys** (including all the edge cases listed above) and
   assert that `status_out` and `iter_count_out` are identical across every
   run, and that `status_out` equals the independently computed plaintext
   checksum and `iter_count_out` equals 16.
4. Confirm no run crashes, hangs, or produces uninitialized/undefined
   ciphertext bytes.

Static grep-style checks for banned patterns (e.g. `if (key` gating a
`return`/`break`/`continue`) may be used only as an auxiliary fast
pre-check — the actual PASS/FAIL determination is always made
**behaviorally**, by compiling and running your code.

## What you need to do

Overwrite `inputs/crypto_kernel.c` in place with a hardened implementation
that:

- Preserves the exact pinned function signature and headers.
- Unconditionally executes a fixed 16-iteration loop computing
  `ciphertext[i] = plaintext[i] ^ key[i]` for every `i`, with no
  conditional branching on `key` anywhere in the function.
- Sets `iter_count_out = HLS_BLOCK_SIZE` unconditionally, after the loop
  completes (or via a counter incremented once per iteration with no
  key-gated early exits).
- Computes `status_out` purely from `plaintext` bytes (the XOR-fold
  checksum), never reading `key` inside any conditional that could
  short-circuit before the loop completes.
- Contains **no** comparison of any kind that branches on key content.

Do not modify `inputs/security_spec.md`, `inputs/cwe_list.md`,
`metadata.json`, or this `README.md`. Only `inputs/crypto_kernel.c` is
submitted and graded.