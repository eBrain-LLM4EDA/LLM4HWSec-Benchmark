# Security Specification — Constant-Behavior XOR-Cipher HLS Kernel

## Objective

`inputs/crypto_kernel.c` must implement an HLS-style XOR stream-cipher block
kernel whose externally observable behavior is **constant with respect to
the secret key**, except for the ciphertext itself. Concretely: the kernel
must compute the correct XOR transform between a public plaintext and a
secret key, while guaranteeing that neither its control flow nor its public
diagnostic outputs (`status_out`, `iter_count_out`) ever vary based on the
content of the key. Only `ciphertext` may legitimately carry key-derived
information, and only in the exact `plaintext XOR key` relationship.

## Pinned interface

The submitted file must include only the following two headers:

```c
#include <stdint.h>
#include <string.h>
```

and define the block size and entry point exactly as follows:

```c
#define HLS_BLOCK_SIZE 16

void crypto_kernel(const uint8_t plaintext[HLS_BLOCK_SIZE],
                    const uint8_t key[HLS_BLOCK_SIZE],
                    uint8_t ciphertext[HLS_BLOCK_SIZE],
                    int *status_out,
                    unsigned int *iter_count_out);
```

- `plaintext` — public input, 16 bytes.
- `key` — **SECRET** input, 16 bytes.
- `ciphertext` — public/declassified output, 16 bytes.
- `status_out` — public diagnostic output.
- `iter_count_out` — public diagnostic output.

No other entry points, no additional headers, and no `main()` are
permitted in this file.

## Required behavioral properties

1. **Ciphertext correctness.** For every `i` in `0..HLS_BLOCK_SIZE-1`:
   `ciphertext[i] == plaintext[i] ^ key[i]`, for every valid
   `(plaintext, key)` pair.

2. **Status independence from key.** `status_out` must be set to the
   XOR-fold checksum of the plaintext bytes cast to `int`:
   `status = (int)(plaintext[0] ^ plaintext[1] ^ ... ^ plaintext[15])`.
   `status_out` must be a **pure function of `plaintext` only** — it must
   never depend, directly or indirectly, on any byte of `key`.

3. **Iteration count independence from key.** `iter_count_out` must always
   equal `HLS_BLOCK_SIZE` (16), for every invocation, regardless of the
   content of `key` or `plaintext`. The kernel must always fully process
   the fixed-size block; no early return, `break`, or `continue` may be
   gated on key content (or on anything else).

4. **No key-dependent branching.** No `if`, `switch`, ternary, loop
   condition, or other control-flow construct in the kernel may branch,
   directly or indirectly, on the value of any byte of `key`. The only
   permitted use of `key` is as a pure data operand in the fixed-trip-count
   XOR loop that produces `ciphertext`.

5. **No cross-call state.** No global or `static` mutable state may be
   used to carry information between separate invocations of
   `crypto_kernel`. Each call must be behaviorally independent of prior
   calls (aside from the pure combinational relationship of its own
   inputs to its own outputs).

6. **Synthesizable-style constraints.** No `malloc`/`new`, no recursion,
   fixed-size arrays only. All loops must have a compile-time-constant
   trip count of exactly `HLS_BLOCK_SIZE` (16) — no data-dependent loop
   bounds of any kind.

## Security requirements

### SR1 — status_out invariance and correctness

`status_out` must be invariant across all secret key values for a fixed
plaintext, and must equal the XOR-fold checksum of that plaintext.

*Detection strategy:* for a fixed plaintext, invoke `crypto_kernel` with a
large set (**≥ 200**) of distinct keys spanning edge cases — all-zero key,
`key[0] == 0` with other bytes nonzero, `key[15] == 0`, all-`0xFF` key, and
pseudo-random keys generated from a fixed seed — and assert every resulting
`status_out` is identical and equals the expected checksum computed
independently by the harness from the plaintext.

### SR2 — iter_count_out constancy

`iter_count_out` must equal `HLS_BLOCK_SIZE` (16) for every invocation
regardless of key content (no early return/short-circuit on secret data).

*Detection strategy:* for the same key/plaintext sweep as SR1, assert
`iter_count_out == 16` in every run; any run producing a different value
(e.g. 0) indicates an early-exit vulnerability.

### SR3 — ciphertext functional correctness under all keys

`ciphertext` must equal `plaintext XOR key` for every `(plaintext, key)`
pair, including the edge-case keys used to probe leakage, so that
hardening does not break functional correctness or silently skip the XOR
computation in any branch.

*Detection strategy:* compare each byte of the returned ciphertext against
an independently computed `plaintext[i] ^ key[i]` reference for a battery
of known-answer vectors plus the same key sweep used in SR1/SR2.

### SR4 — no observable behavioral difference across differing keys

No aspect of externally observable behavior (`status_out`, `iter_count_out`,
or process exit/error behavior) may differ between any two runs that share
the same plaintext but use different keys.

*Detection strategy:* behavioral cross-run diffing — run the harness
pairwise across the full key sweep with identical plaintext and assert
byte-for-byte equality of the `(status_out, iter_count_out)` tuple across
all runs. A fail-on-presence grep for banned patterns like `if(key` /
`if (key` gating a `return`/`break`/`continue` may be used only as an
auxiliary fast pre-check, never as a substitute for the behavioral PASS.

## Threat model

An attacker can invoke `crypto_kernel` repeatedly with a fixed,
attacker-chosen public plaintext while the secret key varies across many
unknown values, including adversarially chosen edge-case keys such as an
all-zero key, a key with a zero first byte, a key with a zero last byte,
and high-entropy random keys. The attacker observes only: (1) the public
ciphertext output (the approved/declassified channel), (2) the public
`status_out` value, and (3) the public `iter_count_out` value (a proxy for
execution timing/loop trip count). The attacker must **not** be able to
distinguish any two different secret keys, or infer any bit of key
material, from variation in `status_out` or `iter_count_out`; only
ciphertext may vary with the key, and only in the exact
`plaintext XOR key` relationship.