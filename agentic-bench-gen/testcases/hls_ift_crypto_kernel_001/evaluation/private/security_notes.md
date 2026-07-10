# Internal Maintainer Notes — hls_ift_crypto_kernel_001 (XOR-Stream Cipher Kernel)

**Status:** internal / reviewer-only. NOT participant-facing. NOT referenced
by `evaluation/evaluate.py` at runtime. Do not link this file from any
participant-visible README or bundle listing.

## Purpose of this document

This file records the mapping between the public requirement IDs
(`FR1..FR4`, `SR1..SR4`) shipped in the participant-facing artifacts and the
original hidden threat model that motivated them, for pipeline/reviewer
traceability only. The participant-facing README intentionally describes
these requirements in generic functional/determinism language ("output
determinism", "non-interference between key and status/iterations",
"banned pattern scan", "functional correctness under varying keys") and
must never mention CWE identifiers or name a specific vulnerability class.
This document is where that hidden framing is allowed to live.

## Requirement → hidden threat model mapping

- **SR1 (status determinism across randomized-key trials)** and
  **SR2 (iterations == len across randomized-key trials)** jointly
  encode an **information-flow non-interference property** between the
  secret `key` input and the public `status`/`iterations` outputs. In the
  original hidden threat model this was categorized as an
  information-exposure / observable-timing-discrepancy class: an attacker
  who can invoke the kernel repeatedly with fixed public plaintext/len but
  varying secret key content must not be able to infer anything about key
  content by observing `status` or `iterations`. Any correlation between
  key bytes and these two outputs constitutes a side-channel leak of the
  secret. SR1/SR2 detect this behaviorally by asserting bitwise-identical
  `status` and exact `iterations == len` across a large (>=200), fixed-seed
  sample of randomized keys (including all-zero, all-0xFF, and
  scattered-zero-byte keys) with fixed plaintext/len.

- **SR3 (static fail-on-presence scan for banned constructs)** encodes the
  **banned-construct / data-dependent-control-flow class**: the kernel's
  control flow (branches, switch/case, loop bounds) must never depend on
  the *value* of a secret key byte, and must not use disallowed
  HLS-unsynthesizable constructs (`malloc`/`calloc`, recursion). This is
  the only static (non-behavioral) check in the suite, permitted because
  it is fail-on-presence: it can only ever penalize a submission for
  containing the vulnerable construct, never reward a submission for
  containing baseline-shaped code.

- **SR4 (ciphertext correctness under secret variation)** and
  **FR1 (ciphertext correctness on known-answer vectors)** both encode
  **functional correctness of the declassified ciphertext output**. The
  `ciphertext` output is the one sanctioned, intentionally-observable
  function of the secret key (`plaintext[i] ^ key[i]`); FR1 checks this
  on fixed known-answer-test vectors (5 lengths), while SR4 re-checks the
  identical invariant across the full 220-trial randomized-key sample used
  for SR1/SR2, confirming that hardening the control flow against key
  leakage did not break the intended declassified computation.

## Baseline vulnerability anchor

The shipped baseline (`inputs/kernel.c` as provided to participants)
contains the following construct inside its main processing loop:

```c
if (key[i] == 0) {
    *status = ERR_KEY_ZERO_BYTE;
    return;
}
```

This is a **key-dependent early return**: whenever any byte of the secret
`key` is zero, the loop (and the function) exits early, before writing the
remaining `ciphertext` bytes and before setting `*iterations` to the full
`len`, and it sets `*status` to a value (`ERR_KEY_ZERO_BYTE = 1`) that
differs from the all-bytes-processed case (`STATUS_OK = 0`). This produces
directly observable correlation between secret key content and the public
`status`/`iterations` outputs — an attacker who repeatedly invokes the
kernel with the same plaintext/len and varying keys can determine, byte by
byte (via binary search over key positions/values), which key bytes are
zero, purely from `status`/`iterations`, without ever learning the
declassified `ciphertext`. SR1/SR2 detect this behaviorally (near-certain
status/iterations divergence across the 220-trial sample, since an
all-zero key and most pseudo-random 64-byte keys will contain a zero byte
well before index 63). FR2/FR3 also fail against this same baseline
behavior from the functional-requirement side.

## SR3 discrimination requirement (why it must not be a dead check)

A validation pass flagged that an earlier version of SR3 was anchored
*only* to the literal baseline token sequence
`if (key[i] == 0) { *status = ERR_KEY_ZERO_BYTE; ... return; }` and never
independently fired FAIL on any other mutant — i.e. it provided zero
discrimination beyond detecting the exact shipped baseline string. This is
unacceptable: a static check that only matches the literal baseline
pattern is trivially defeated by any syntactically-different
reintroduction of the same vulnerability (different comparison operator,
different variable name, staged intermediate variable, switch/case
instead of if/else), and provides no real security guarantee.

The current SR3 implementation (see `sr3_static_scan` in
`evaluation/evaluate.py`) was broadened specifically to close this gap. It
must continue to independently fire FAIL on **all** of the following
variant forms, not just the exact baseline string, and reviewers should
re-verify this whenever SR3 is touched:

- Different comparison operators: `key[i] != 0`, `key[i] < 1`,
  `key[i] >= 1`, etc., guarding an early exit.
- Different index expressions inside `key[...]` (e.g. `key[j]`,
  `key[idx]`, `key[len - 1 - i]`).
- Different variable/parameter naming for the exit path (e.g. a mutant
  that assigns to a differently-named status variable, or uses a
  differently-named loop counter).
- An intermediate/staged variable pattern, e.g.:
  ```c
  unsigned char kb = key[i];
  if (kb != 0) {
      ciphertext[i] = plaintext[i] ^ kb;
  } else {
      *status = 2;
      return;
  }
  ```
  This must be caught by sub-check (b) (branch on a variable assigned
  from `key[...]`), not sub-check (a).
- `switch`/`case` forms switching on `key[i]` (or a variable staged from
  it) with a `return`/`break`/`continue` in some case body.
- Nested `if` forms where the key-dependent condition is not the
  outermost `if`.

Per the repair instructions, at least one additional mutant using
different syntax/naming than the shipped baseline (e.g. the staged-`kb`
variant above, or a `key[i] != 0` / `break`-in-switch variant) must be
included in the mutation test suite for this case, and SR3 must be
confirmed to emit `[TEST] FAIL: SR3: ...` on that mutant — proving SR3 has
genuine discriminative value and is not merely pattern-matching the
baseline's exact substring. If SR3 is ever modified, re-run it against:
(1) the shipped baseline (must FAIL), (2) a known-good golden with a
single unconditional for-loop over `len` (must PASS), and (3) at least the
staged-variable and switch/case variant mutants described above (must
FAIL) before considering the change complete.

## Reminder on file handling

This file lives under `evaluation/private/` precisely so that it is
excluded from the participant-facing bundle and is never opened by
`evaluate.py` at grading time. Do not move it under `evaluation/` (without
the `private/` prefix), do not reference it from `README.md`, and do not
add any CWE identifiers or hidden-intent language back into
participant-facing files (`README.md`, `metadata.json`, comments in
`harness_main.cpp`, etc.) when updating this document.