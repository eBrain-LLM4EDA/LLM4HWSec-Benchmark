# Evaluation: hls_roundkey_zeroization_001

## Purpose

This directory contains the behavioral grader for the "Zeroize an
expanded round-key array before return" task. It grades the submission
under `inputs/cipher_kernel.cpp` **in place** against the pinned
interface declared in `inputs/cipher_kernel.h` (which must not be
modified by participants).

Participants must only edit `inputs/cipher_kernel.cpp`. No other file
under `inputs/` is read as a submission artifact.

## How to run

From the repository root:

```
python3 evaluation/evaluate.py
```

Requirements:

- `g++` supporting `-std=c++17` must be available on `PATH`.
- Python 3 standard library only (no third-party packages, no network
  access).

The script compiles `inputs/cipher_kernel.cpp` together with
`evaluation/harness_main.cpp` at three optimization levels (`-O0`,
`-O2`, `-O3`), runs the resulting binaries in several modes, and derives
PASS/FAIL for each requirement purely from observed program behavior
(printed ciphertext bytes and printed stack-probe bytes). No check
passes based on how the submission's source code is written; the only
static checks that could ever fail a submission are compiler
diagnostics from an actual build failure.

A pure-Python reference AES-128 implementation is embedded directly in
`evaluate.py` (S-box generated via GF(2^8) multiplicative inversion at
runtime, not hardcoded from memory, with a structural sanity assertion
that it forms a 256-entry permutation) so that known-answer ciphertext
comparisons do not depend on any recalled constant table.

## Which input files are read

Only these three files under `inputs/` are ever opened or compiled by
`evaluate.py`:

- `inputs/cipher_kernel.h`
- `inputs/cipher_kernel.cpp`
- `inputs/design_brief.md`

`inputs/cipher_kernel.h.notusedplaceholder` is a non-functional
placeholder file that is intentionally never referenced, checked for
existence, or compiled by this grader.

## Requirements checked

Functional requirements:

- `FR1` — fixed key/plaintext known-answer vector #1 produces the
  correct ciphertext at `-O0`.
- `FR2` — all-zero key/plaintext known-answer vector #2 produces the
  correct ciphertext at `-O0`.
- `FR3` — the submission compiles cleanly with `g++ -O2 -std=c++17`
  and reproduces FR1/FR2 correctly at `-O2`.
- `FR4` — repeated calls with different keys/plaintexts in sequence
  never carry state over between invocations (a repeated call with the
  first key/plaintext pair reproduces the first output exactly).

Security requirements:

- `SR1` — the 176-byte `round_keys` working buffer is observably
  zeroed on the stack immediately after `encrypt_block` returns, at
  `-O0`.
- `SR2` — the same zeroing is still observable at `-O2` and `-O3`,
  confirming the clearing mechanism survives dead-store elimination
  under optimization.
- `SR3` — the zeroing mechanism does not alter the correctness of the
  returned ciphertext; FR1/FR2 vectors are re-verified against the
  same computed reference at `-O2` and `-O3`.
- `SR4` — a lenient, best-effort heuristic check that adjacent
  uninitialized scratch stack memory does not show distinguishable,
  key-dependent residue across two calls with different keys and the
  same plaintext. This check is designed to never false-fail a
  correct, hardened submission.

## SR1/SR2 probe methodology (multi-attempt, multi-vector)

Earlier versions of this harness derived SR1/SR2 from a single
post-return stack probe: call `encrypt_block` once, then immediately
call a same-depth `probe_stack_frame()` helper that reads an
uninitialized local `unsigned char[176]` and reports its contents.
That single-shot approach turned out to be unreliable in practice: on
a correctly hardened golden submission it intermittently observed
tens of nonzero bytes (stack-layout / register-allocation /
prologue-padding noise that happened to leave *other*, unrelated
stack bytes nonzero at the probed offsets), producing the exact same
qualitative failure shape as a genuinely vulnerable, unzeroed
implementation — meaning the check could not reliably discriminate
hardened from vulnerable behavior across compiler/ABI/optimization
variance.

To fix this without weakening the requirement, `evaluation/harness_main.cpp`
now performs a **repeated, multi-vector sweep** entirely within the
`probe` mode:

1. It exercises `encrypt_block` with **N = 4 fixed key/plaintext
   pairs** (covering the FR1/FR2 known-answer vectors plus two
   additional fixed pairs, including an all-`0xff` pattern), so the
   check is not tied to the bit pattern of any single key.
2. For each pair, it performs **M = 8 repeated attempts**: call
   `encrypt_block`, then immediately call the noinline,
   volatile-qualified `probe_stack_frame()` helper to read back the
   same-depth stack region.
3. Across all `N × M = 32` attempts, the harness tracks the **worst
   case** — the single attempt with the greatest number of nonzero
   probed bytes — and prints only that attempt's 176 bytes as a
   `PROBE:<hex>` line.

`evaluate.py` asserts that this reported worst-case attempt is
all-zero. Because it is a maximum over every attempt across every
key/plaintext pair, an all-zero worst case is a guarantee that *every
single attempt in the entire sweep* was all-zero — a much stronger and
more deterministic signal than any one-shot probe. Conversely, a
submission that leaves `round_keys` unzeroed (or whose zeroing is
eliminated as a dead store under optimization) reliably reproduces
nonzero, key-schedule-shaped bytes on most or all of the 32 attempts,
so the worst case remains strongly nonzero. This sweep is applied
identically at `-O0` (for `SR1`) and at both `-O2` and `-O3` (for
`SR2`), so the same discrimination holds across every tested
optimization level.

Each requirement prints exactly one line, either:

```
[TEST] PASS: <requirement_id>
```

or

```
[TEST] FAIL: <requirement_id>: <reason>
```

The process exits with code `0` only if every requirement passes, and
a nonzero exit code otherwise.