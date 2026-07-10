# XOR-Stream Cipher Kernel — Evaluation Harness

## Objective

`inputs/kernel.c` must implement a byte-wise XOR-stream cipher kernel that
processes its entire input buffer deterministically, regardless of the
content of the secret key. The kernel must always fully populate its output
buffer and always report the same, well-defined completion status.

## Required interface

`inputs/kernel.c` must define, at file scope:

```c
#define MAX_LEN <compile-time constant, integer literal >= 64>

void xor_cipher_kernel(const unsigned char plaintext[MAX_LEN],
                        const unsigned char key[MAX_LEN],
                        int len,
                        unsigned char ciphertext[MAX_LEN],
                        int *status,
                        int *iterations);
```

- `plaintext` — public input bytes to encrypt (length `len`, `len <= MAX_LEN`).
- `key` — secret input bytes (length `len`); only the XOR-combination with
  `plaintext` (i.e. `ciphertext`) is a sanctioned observable output — no
  other output may vary with key content.
- `len` — public input, number of valid bytes in `plaintext`/`key`.
- `ciphertext` — public output buffer; `ciphertext[i] == plaintext[i] ^ key[i]`
  for every `i < len`. Bytes at index `>= len` are unspecified.
- `status` — public output; must be set to `0` (`STATUS_OK`) on every call
  with `len <= MAX_LEN`. Behavior for `len > MAX_LEN` is undefined and is
  not exercised by this harness.
- `iterations` — public output; must be set to exactly `len` on every call,
  independent of key content.

`MAX_LEN` must be defined as a plain compile-time integer constant (e.g. via
`#define`) that is `>= 64`. The harness always calls the kernel with
`len <= 64`, so any `MAX_LEN >= 64` is compatible.

## Functional requirements

- **FR1 — Ciphertext correctness.** `ciphertext[i] == plaintext[i] ^ key[i]`
  for every `i < len`, for any plaintext/key content and any `len <= MAX_LEN`.
- **FR2 — Status correctness.** `status == 0` (`STATUS_OK`) for every call
  with `len <= MAX_LEN`, for all possible key byte values, including keys
  that contain zero bytes.
- **FR3 — Full buffer population.** The kernel writes all `len` bytes of
  `ciphertext` and reports `iterations == len` in a single call — no
  truncated or partially-written output, and no dynamic memory allocation.
- **FR4 — Clean build.** The file compiles without errors using
  `gcc -std=c11 -Wall -Wextra`, and does not produce implicit-declaration,
  incompatible-pointer-type, conflicting-types, or type-mismatch warnings
  (other warnings are permitted).

## Security / robustness requirements

These requirements describe properties that must hold no matter how the
secret `key` bytes are chosen — i.e. the public, observable outputs
(`status`, `iterations`, and the sanctioned `ciphertext` output) must behave
consistently and correctly under adversarial variation of the secret input.

- **SR1 — Status determinism.** With plaintext and `len` held fixed,
  `status` must be bitwise identical across a large, deterministic sample of
  randomized keys (including all-zero keys, all-0xFF keys, and keys with
  scattered zero bytes). In other words, `status` must never depend on key
  *content*, only on whether `len <= MAX_LEN`.
- **SR2 — Iteration-count determinism.** With plaintext and `len` held
  fixed, `iterations` must equal `len` exactly for every key in the same
  randomized-key sample used for SR1 — the kernel must never exit its
  processing loop early based on key content.
- **SR3 — No banned/data-dependent control-flow constructs.** The source of
  `inputs/kernel.c` must not contain: (a) branches or `switch` statements
  whose condition inspects `key[...]` (directly, or indirectly via an
  intermediate variable assigned from `key[...]`) and whose body exits the
  enclosing loop or function (`return`/`break`/`continue`); (b)
  `malloc`/`calloc`; (c) recursive self-calls; (d) loop bounds that depend
  on the contents of `key`, `plaintext`, or `ciphertext` rather than on
  `len`/a fixed constant. This is checked via static text analysis of the
  submitted source, independent of build/run success.
- **SR4 — Ciphertext correctness under secret variation.** For every key in
  the same large randomized-key sample used for SR1/SR2, `ciphertext[i]`
  must equal `plaintext[i] ^ key[i]` for every `i < len` — i.e. functional
  correctness must be preserved even as the secret key varies adversarially.

## Constraints

- Single file: `inputs/kernel.c`, implementing the pinned entry point
  exactly as declared above.
- Fixed-size arrays only for `plaintext`, `key`, `ciphertext` (sized by
  `MAX_LEN`); no `malloc`/`calloc`/`free`, no recursion, no STL/C++
  containers.
- No variable-trip-count loops — loop bounds must depend only on `len`
  and/or fixed constants, never on the contents of `plaintext`, `key`, or
  `ciphertext`.
- No control flow (branch, `break`, `continue`, `return`) whose condition
  depends on the *value* of any key byte.
- `status` must use `0` as the only defined success value for this kernel.

## Running the evaluator

From the repository root:

```
python3 evaluation/evaluate.py
```

This script:

1. Confirms `inputs/kernel.c` exists.
2. Compiles `inputs/kernel.c` with `gcc -std=c11 -Wall -Wextra -c` to check
   build hygiene (FR4).
3. Compiles `inputs/kernel.c` together with the shipped test driver
   `evaluation/harness_main.cpp` (which declares the pinned interface and
   drives it with fixed-plaintext known-answer vectors plus 220
   deterministic randomized-key trials), links a test binary, and executes
   it.
4. Parses the test binary's deterministic stdout (plaintext / KAT /
   TRIAL records) and checks FR1, FR2, FR3, SR1, SR2, SR4 behaviorally
   against those records.
5. Performs a static, fail-on-presence text scan of `inputs/kernel.c` for
   banned constructs to check SR3.

For each of `FR1, FR2, FR3, FR4, SR1, SR2, SR3, SR4` it prints exactly one
line:

```
[TEST] PASS: <ID>
```
or
```
[TEST] FAIL: <ID>: <reason>
```

The script exits with code `0` only if every requirement passes, and a
non-zero exit code if any requirement fails (including build/run failures,
which are reported as failures of the corresponding behavioral
requirements rather than as setup errors — a submission that fails to
compile or crashes at runtime does not satisfy those requirements).