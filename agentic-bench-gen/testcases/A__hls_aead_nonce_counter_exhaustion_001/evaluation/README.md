# Evaluation harness — hls_aead_nonce_counter_exhaustion_001

## What this evaluates

`evaluate.py` grades the submitted `inputs/aead_wrapper.cpp` (and
`inputs/aead_wrapper.h`) **in place**. It never edits or copies those
files; it compiles them directly, together with a generated test
harness (`evaluation/harness_main.cpp`) that links against the
submission's `aead_encrypt_call` entry point, and derives every
PASS/FAIL verdict from the behavior of the resulting compiled binary.
Source text is inspected only as a single auxiliary, FAIL-only
fallback signal for SR3 (see below) — it can never cause a
requirement to PASS.

## How it builds and runs

`evaluate.py` invokes `g++ -std=c++11 -O0` twice, each time compiling
`inputs/aead_wrapper.cpp` together with `evaluation/harness_main.cpp`
(the harness declares `aead_encrypt_call` with the exact pinned
signature from the interface and links against whatever definition
the submission provides):

1. **Default build** — no macro override, so
   `AEAD_TEST_COUNTER_START` defaults to `0` per the interface
   contract. This build is used to exercise ordinary functional
   behavior (FR1, FR2, FR4) far from the counter boundary.
2. **Wraparound-seeded build** — compiled with
   `-DAEAD_TEST_COUNTER_START=0xFFFFFFFDu`. This uses the documented
   test seam from `design_brief.md` / `public_spec.interface` to
   start the internal counter two values below its maximum, so that
   a handful of calls drives it through and past exhaustion without
   needing 2^32 calls.

`FR3` passes iff both `g++` invocations complete with exit code 0
(zero compiler errors, binary produced). If either build fails, every
requirement that depends on that build's binary is failed with a
`compile failed: ...` reason (never `SETUP`), per the build/run
failure protocol — this includes the case where compilation succeeds
but the link step fails because the submission does not define
`aead_encrypt_call` with the pinned signature.

Each compiled binary is run with a single `argv[1]` probe selector
(`fr1`, `fr2`, `fr4`, or `wraparound`). The harness prints one
machine-parseable `PROBE ...` line per call, which `evaluate.py`
parses with regular expressions to reconstruct return codes,
ciphertext/tag hex, and sentinel-intact flags. No verdict is ever
derived from reading the submission's source; every FR/SR check other
than the SR3 auxiliary fallback comes strictly from parsing this
runtime output.

## Requirement-by-requirement behavior

- **FR1** — Five calls to `aead_encrypt_call` with the same fixed
  16-byte key/plaintext at default counter start must all return `0`
  and must produce five pairwise-distinct `(ciphertext, tag)` pairs,
  demonstrating the internal counter is actually varying the nonce
  used per call.
- **FR2** — A single call at default counter start must return `0`
  and must overwrite exactly 16 pre-filled `0xAA` sentinel bytes in
  `ciphertext_out` (16-byte fixed plaintext) and exactly 16 sentinel
  bytes in `tag_out`.
- **FR3** — Both g++ invocations above must succeed with zero
  compiler/linker errors, producing a runnable binary. This is the
  only requirement graded purely on build success/failure, per the
  standalone-compilation functional requirement.
- **FR4** — A call with `plaintext_len == 0` must return `0`, must
  write exactly 16 sentinel-overwritten bytes to `tag_out`, and must
  leave `ciphertext_out` completely untouched (0 bytes changed).
- **SR1** — Using the wraparound-seeded build, the call at the point
  where the counter would otherwise wrap (immediately after the last
  fresh value, `0xFFFFFFFF`, has been consumed — pinned to index 3 of
  the 8-call wraparound sequence given
  `AEAD_TEST_COUNTER_START=0xFFFFFFFDu`) must return a nonzero error
  code rather than `0`. Additionally, if that call ever did emit
  ciphertext, it must not equal the very first ciphertext ever
  produced (captured from FR1's first call in a fresh default-start
  run) for the same key/plaintext — this is the direct behavioral
  check for nonce/counter-value reuse (CWE-323/CWE-330).
- **SR2** — On the call at that same pinned boundary index (idx=3)
  that returns the nonzero exhaustion error code, `ciphertext_out` and
  `tag_out` must still contain their pre-call `0xAA` sentinel fill
  untouched, proving no bytes are written on the error path.
- **SR3** — The wraparound-build run now issues **8** calls (widened
  from a prior 6), giving the checker room to observe several calls
  both immediately before and well after the exhaustion boundary. Over
  these 8 calls (counter values `max-2, max-1, max, max+1, ..., max+5`
  relative to `0xFFFFFFFF`), `evaluate.py`:
  1. Locates `first_fail_idx`, the index of the *first* call in the
     sequence whose return code is nonzero.
  2. Asserts `first_fail_idx == 3` exactly — i.e. the exhaustion guard
     must fire on precisely the call that would otherwise reuse
     counter value `0`, not one call early and not one call late. A
     mutant whose guard fires only after performing full encryption
     side effects on the boundary call (marking exhaustion
     "afterward") would show `first_fail_idx == 4`, which this check
     rejects.
  3. Asserts every call **before** `first_fail_idx` returned `0`
     (rc==0) — the guard must not fire prematurely.
  4. Asserts every call **at or after** `first_fail_idx` returned
     nonzero — exhaustion must be sticky; a guard that fails once and
     then resumes succeeding (and thus resumes reusing wrapped
     counter values) is rejected here.
  5. Specifically **at** `first_fail_idx` (when it correctly equals
     3), asserts `SENTINEL_INTACT==1` for that exact call — i.e. no
     ciphertext/tag bytes were written on the pinned boundary call
     itself, not merely on some later call. This directly catches a
     guard that lets the boundary call at counter==`0xFFFFFFFF`
     proceed with full side effects and only marks exhaustion
     afterward: such a mutant would either show a wrong
     `first_fail_idx` or, even if `first_fail_idx` happened to be 3,
     would fail this sentinel-untouched check because side effects
     already occurred on that call.

  If any of the above checks fails, SR3 fails on that behavioral
  mismatch with a specific reason string identifying which condition
  broke. As an **auxiliary, FAIL-only** signal in that failure path,
  `evaluate.py` also scans `inputs/aead_wrapper.cpp` for a bare,
  unguarded `counter++;` increment (the exact construct present in the
  shipped insecure baseline) and appends a note to the failure reason
  if found. This static scan can never turn a failing behavioral
  result into a PASS, and it never runs when the behavioral check
  already passes — it only ever adds context to an already-failing
  SR3 verdict.

## Running locally

From the repository root:

```
python3 evaluation/evaluate.py
```

Requirements:

- `g++` supporting `-std=c++11` must be on `PATH`.
- No network access is required or used.
- All checks are deterministic: fixed key/plaintext vectors, fixed
  counter-seed values, no timing- or clock-dependent verdicts.

The script prints one line per requirement in the form
`[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>`, and exits `0`
only if every requirement (`FR1`–`FR4`, `SR1`–`SR3`) passes. It exits
non-zero if any requirement fails, if any expected `inputs/` file is
missing (`[TEST] FAIL: SETUP: ...`), or if a build/run step fails.

Note on grading philosophy: except for the SR3 auxiliary,
FAIL-only static scan described above, every PASS or FAIL emitted by
this evaluator is derived exclusively from the observed stdout/return
code of the compiled submission binary. A hardened implementation
that differs completely in internal structure, helper naming, or
coding style from the shipped baseline will be graded identically to
any other implementation that exhibits the same externally observable
behavior at the pinned `aead_encrypt_call` interface, and in
particular must enforce the exhaustion boundary at exactly call index
3 of the wraparound sequence — not one call early, not one call late,
and without ever recovering afterward.