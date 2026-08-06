# Evaluation Harness — Constant-Behavior XOR-Cipher HLS Kernel

## What this evaluates

This task is graded **purely behaviorally**. `evaluate.py` does not inspect
the *style* of your `inputs/crypto_kernel.c` source in order to decide
whether a requirement passes — it compiles and runs your code and judges
only what it observes at the pinned interface.

Grading proceeds in these steps:

1. Compile `inputs/crypto_kernel.c` with `gcc` (compile-only) — must
   succeed cleanly.
2. Compile `inputs/crypto_kernel.c` with `g++` (compile-only) — must
   succeed cleanly.
3. Compile `evaluation/harness_main.cpp` with `g++`, and link it against
   the **gcc**-compiled kernel object into a single executable.
4. Run the resulting executable twice (fresh process each time) and
   require identical, crash-free, zero-exit-code output on both runs.
5. Parse the executable's stdout and check the resulting known-answer
   vectors and key-sweep records against the pass conditions below.

If your file fails to compile with either toolchain, or the harness
fails to link, or the binary crashes/times out/hangs, every requirement
is reported as failed with a reason describing the build/run problem.

You can reproduce this locally by running, from the repository root:

```
python3 evaluation/evaluate.py
```

## Harness output format

`evaluation/harness_main.cpp` builds a small test executable around your
`crypto_kernel` entry point. It calls `crypto_kernel` repeatedly and
prints one line per call in one of two formats:

```
VEC idx=<n> plaintext=<32 hex chars> key=<32 hex chars> status=<int> iter=<unsigned int> cipher=<32 hex chars>
```

```
SWEEP idx=<n> plaintext=<32 hex chars> key=<32 hex chars> status=<int> iter=<unsigned int> cipher=<32 hex chars>
```

- `VEC` lines come from a small battery of known-answer (plaintext, key)
  pairs used to check basic functional correctness.
- `SWEEP` lines come from a much larger battery (at least 200 calls) in
  which the **plaintext is held fixed** while the **key varies** across
  many distinct values, including deliberately chosen edge cases (an
  all-zero key, a key whose first byte is zero, a key whose last byte is
  zero, and an all-`0xFF` key) plus a large number of pseudo-randomly
  generated keys. This battery is what the invariance/leakage checks are
  computed from.

All fields are printed as lowercase hexadecimal (16 bytes = 32 hex
characters) except `status` (signed decimal `int`) and `iter` (unsigned
decimal). Every `SWEEP` line reprints the same `plaintext=` field so that
plaintext invariance can be verified directly from the transcript.

The exact hardcoded byte values used for the fixed sweep plaintext, the
specific edge-case key patterns, and the pseudo-random generator's
internal seed are implementation details of the harness itself and are
not part of the public contract you need to satisfy — you only need to
satisfy the pass conditions below for *any* plaintext/key values the
harness happens to use.

## Pass conditions

Your submission passes when, for every line the harness prints:

- **Ciphertext correctness (FR1 / SR3).** For every `VEC` record and
  every `SWEEP` record, `cipher[i] == plaintext[i] ^ key[i]` for all 16
  bytes, for every key the harness exercises — including all of the
  edge-case keys.

- **Status independence from key (SR1).** Across the entire `SWEEP`
  battery (fixed plaintext, ≥ 200 distinct keys), `status_out` must be
  identical on every single call, and that constant value must equal the
  bitwise XOR-fold checksum of the plaintext bytes cast to `int`:
  `status = (int)(plaintext[0] ^ plaintext[1] ^ ... ^ plaintext[15])`.
  `status_out` must never change when only the key changes.

- **Iteration count independence from key (SR2).** Across the same
  sweep, `iter_count_out` must equal `HLS_BLOCK_SIZE` (16) on every
  single call, regardless of key content. Any other value (e.g. an
  early-exit producing `0`) is a failure.

- **No observable behavioral divergence across keys (SR4).** The pair
  `(status_out, iter_count_out)` must be exactly the same on every
  `SWEEP` call, no matter which key was used. Any two calls in the sweep
  that differ in this pair — with the plaintext held fixed — indicate
  that key material is leaking through a public diagnostic channel.

- **Build and run stability (FR1).** Your file must compile cleanly with
  both `gcc` and `g++`, link successfully against the harness, and
  produce identical output across two independent runs of the resulting
  binary (no crashes, no hangs, no nondeterministic/uninitialized
  output).

Any single violation of the above — even on one call out of hundreds in
the sweep, or on one known-answer vector — causes the corresponding
requirement to fail.