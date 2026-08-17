# Evaluation Harness — Constant-Time CBC Unpad (`pad_check`)

This directory contains the behavioral grader for
`hls_constant_time_cbc_unpad_001`. It grades the file
`inputs/cbc_unpad.cpp` **in place** — a correctly hardened submission
passes; the shipped insecure baseline fails.

**Entry point:** `evaluation/evaluate.py`. Run it from the repository
root:

```
python3 evaluation/evaluate.py
```

It exits `0` iff every requirement (`FR1`–`FR4`, `SR1`–`SR3`) prints
`[TEST] PASS`, and non-zero otherwise. Every requirement prints exactly
one `[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>` line.

## Toolchain

- Only `g++` is required (invoked via `subprocess`, `-std=c++11 -O0`).
- No network access is used or required.
- All test vectors and timing/probe-vector orderings are fixed,
  deterministic constants (no RNG at grading time, no wall-clock-
  dependent pass/fail thresholds beyond fixed, generous statistical
  tolerances — see SR1/SR3 below).

## Build/run flow

`evaluate.py` builds three separate binaries against
`inputs/cbc_unpad.cpp` in a temporary directory (never under `inputs/`):

1. **`harness_main.cpp`** — linked with `inputs/cbc_unpad.cpp` via
   `g++ -std=c++11 -O0 -o <tmp>/harness_main inputs/cbc_unpad.cpp evaluation/harness_main.cpp`.
   Each invocation of the resulting binary takes one 32-hex-character
   block on `argv[1]`, calls `pad_check` exactly once through the pinned
   signature
   `void pad_check(const unsigned char block[16], int *valid, int *unpadded_len);`,
   and prints a single machine-parseable line:
   ```
   RESULT valid=<0|1> len=<n> block_unchanged=<0|1>
   ```
   This binary drives every FR1–FR3 and SR2 vector, and supplies the
   runtime half of FR4 (block-not-mutated check).

2. **`harness_timing.cpp`** — linked with `inputs/cbc_unpad.cpp` via
   `g++ -std=c++11 -O0 -o <tmp>/harness_timing inputs/cbc_unpad.cpp evaluation/harness_timing.cpp`.
   It takes one or more `label:hexblock` arguments, runs many repeated
   calls to `pad_check` per label per round (batched to amortize
   `std::chrono::steady_clock` overhead), and repeats for several
   rounds, printing:
   ```
   TIMING <label> round=<r> ns_per_call=<value>
   ```
   This is the sole source of SR1's wall-clock timing signal.

3. **`harness_probe.cpp`** — linked with `inputs/cbc_unpad.cpp` via
   `g++ -std=c++11 -O0 -o <tmp>/harness_probe inputs/cbc_unpad.cpp evaluation/harness_probe.cpp`.
   It takes one or more `label:hexblock` arguments and measures a
   **deterministic cycle-counter proxy** (`__builtin_readcyclecounter()`
   where available, falling back to a scaled `std::clock()` reading on
   toolchains without that builtin) per call, batched per round, across
   several rounds, printing:
   ```
   PROBE <label> round=<r> cycles=<value>
   ```
   This is a metric computed via a completely different code path from
   SR1's `steady_clock`-based wall-clock measurement (different clock
   source, different units, different batching/cache-pressure
   variation across rounds), and is the sole, authoritative mechanism
   for SR3 — SR3's pass/fail decision does **not** reuse SR1's
   measurements or SR1's tolerance.

`evaluation/harness_counter.cpp` is a self-test fixture used to
sanity-check the counting methodology in isolation (two build-time
variants — an early-exit scan shape and a full-scan shape — each
instrumented with an explicit iteration counter over a self-contained
reimplementation of the padding-region scan). It never calls the
submission's `pad_check` and never contributes to any requirement's
verdict.

If a compile step fails, `evaluate.py` reports `[TEST] FAIL` (never
`SETUP`) for every requirement that depends on that binary, including
the compiler's stderr tail in the reason so the actual diagnostic is
visible. `FR1`–`FR4` (runtime half) and `SR2` depend on `harness_main`;
`SR1` depends on `harness_timing`; `SR3` depends on `harness_probe`.

## Requirement coverage

### FR1 — valid padding, lengths 1–16
For each `N` in `1..16`, a block is constructed with the last `N` bytes
set to `N` and a non-matching filler prefix. The harness must report
`valid=1, len=16-N` for every length, matching the Python-side PKCS#7
reference oracle (`evaluation/private/reference.py`).

### FR2 — invalid last byte (0, 17, 255) plus the N=16 boundary
Three explicit invalid-last-byte vectors are checked:

- last byte `0` — invalid.
- last byte `17` — invalid. This specifically catches an off-by-one
  upper-bound mutant that treats `17` as an in-range padding length
  (e.g. checking `n <= 17` instead of `n <= 16`).
- last byte `255` — invalid.

All three must report `valid=0, len=16`. FR2 additionally re-checks the
fully-padded `N=16` boundary vector (last byte `16`, all 16 bytes of
the block equal to `16`) and asserts `valid=1, len=0` for it, catching
a complementary off-by-one bounds mutant on the lower/inclusive side
(e.g. `n < 16` instead of `n <= 16`).

### FR3 — mismatched padding bytes, region-position coverage
For a fixed valid padding length `N=8`, three vectors each corrupt
exactly one byte within the 8-byte padding region (block offsets
`8..15`, with offset `15` always left equal to `8` so the length byte
itself stays well-formed):

- **first** — offset 8, the first byte of the padding region.
- **middle** — offset 11, the middle of the padding region.
- **last** — offset 14, the last byte of the padding region before the
  length byte itself.

Every one of these three vectors must report `valid=0, len=16`. This
explicit first/middle/last coverage of the padding *region* is what
catches a mutant that negates or otherwise corrupts the in-region
predicate (e.g. checking the wrong byte range): such a mutant will
misclassify at least one of these three region-position vectors even
if it happens to get others right.

### FR4 — standalone compile, no mutation of `block[]`, and a ban on non-synthesizable constructs
FR4 combines a runtime half and a static half; both must pass:

1. **Runtime half.** `inputs/cbc_unpad.cpp` must compile cleanly with
   `g++ -std=c++11 -O0` alongside `harness_main.cpp` and link
   successfully against the pinned `pad_check` symbol. A compile or
   link failure fails FR4 (and the other harness-main-dependent
   requirements) with the compiler/linker's stderr included.
   Additionally, the harness snapshots `block[]` before the call and
   compares it byte-for-byte afterward; any difference fails FR4.

2. **Static half (fail-on-presence only, restricted to
   `inputs/cbc_unpad.cpp`).** A regex scan flags, and fails FR4 if
   found:
   - inclusion of an STL container header (`<vector>`, `<map>`,
     `<set>`, `<string>`, `<deque>`, `<list>`, `<unordered_map>`,
     `<unordered_set>`, `<array>`, `<queue>`, `<stack>`),
   - use of a `std::` container type (`std::vector`, `std::map`, etc.),
   - dynamic allocation via `new` or `malloc(`,
   - a C++ exception construct (`throw`, a `try {` block, or
     `catch(`).

   This directly enforces the public constraint that the submitted
   kernel must not use dynamic memory allocation, STL containers, or
   C++ exceptions — a submission that legitimately achieves constant-
   time behavior never needs any of these constructs in the kernel
   itself, so this check cannot false-fail a correct hardened
   submission; it only fails a submission that reintroduces a banned
   construct (e.g. a mutant that adds `#include <vector>` /
   `std::vector` inside `pad_check`). Comments and string/char literals
   are stripped before matching so incidental text can never trigger a
   false positive.

### SR1 — constant-time behavior (distance-from-end framing, wall-clock timing)
This check is purely behavioral: it never inspects source text. For a
fixed `N=8` valid block and three adversarial single-byte-mismatch
variants ordered by increasing "number of bytes that must be scanned
before the mismatch is found in a naive end-to-start early-exit scan"
(near-the-end → middle → far), `harness_timing` measures median
per-call latency (`ns_per_call`, via `std::chrono::steady_clock`) over
many repetitions per round, across 5 independent harness invocations
(majority-vote aggregation via median-of-medians to reduce flakiness).
SR1 fails only if a monotonic increase in latency correlated with
mismatch position is observed **and** the relative spread between the
"far" and "near" vectors exceeds a fixed, generous 30% tolerance —
comfortably above normal `-O0`/scheduler noise but well below the
large, reproducible gap produced by an early-return scan comparing 2
bytes vs. 8 bytes. A constant-time implementation shows flat timings
across all vectors and passes.

### SR2 — full known-answer equivalence
Every vector from FR1, FR2, and FR3 (valid lengths including the N=16
boundary, invalid last bytes 0/17/255, and adversarial region-position
mismatches) is also checked against the reference oracle for
bit-identical `valid`/`unpadded_len` output. This confirms that
constant-time behavior is not achieved by sacrificing correctness.

### SR3 — secret-dependent early-exit detection (authoritative: independent cycle-counter probe)
SR3's pass/fail verdict is decided by a **mechanism deliberately
independent of SR1's**: `harness_probe.cpp`, compiled and linked
against the submission separately from `harness_timing.cpp`, measures
a deterministic cycle-counter proxy (`__builtin_readcyclecounter()` or
a `std::clock()`-based fallback — never `steady_clock`) per call,
applied to the same padding-*region*-position vectors used for FR3
(first/middle/last byte of the fixed `N=8` padding region, offsets
8/11/14). Between rounds, the harness relocates the working block to
varying cache-line offsets within a scratch buffer, changing
surrounding cache pressure round-to-round without altering the 16
logical content bytes, so this probe is not a mere renamed clone of
`harness_timing`.

A naive end-to-start (`index 15 -> 8`) early-exit scan finds a
mismatch at offset 14 almost immediately (2nd comparison), a mismatch
at offset 11 after scanning roughly half the region, and a mismatch at
offset 8 only after scanning the *entire* 8-byte region — i.e. the
"first" vector should measure a reproducibly higher cycle-proxy value
than the "last" vector under a vulnerable implementation. SR3
aggregates median-of-medians proxy values across 5 independent probe
invocations, using its **own separately tuned tolerance (25%)**,
distinct from SR1's (30%) and computed from a distinct metric/binary,
so a mutant narrowly tuned to slip under SR1's specific
tolerance/aggregation on wall-clock timing cannot automatically also
evade SR3's independently-scaled verdict. SR3 **fails** only if a
monotonic, position-correlated increase beyond its own tolerance is
observed in the cycle-proxy metric — the observable signature of a
secret-dependent `break`/`return` inside the scanning loop, regardless
of how that early exit is spelled in source. A constant-time
implementation shows flat cycle-proxy readings across all three
region-position vectors and passes.

A lightweight static regex scan (looking for a literal `return;` or
`break;` inside a loop that indexes `block[...]`, guarded by an `if`
comparing a `block[...]` element) is still run and its result is
printed as an `[INFO]` note purely for diagnostic/corroborating value.
This static note **never** affects the SR3 verdict: it cannot flip a
behavioral PASS into a FAIL, and it is never consulted as the basis
for a PASS either. The independent cycle-counter probe above is the
sole authoritative mechanism for SR3.

`evaluation/harness_counter.cpp` exists only as a self-contained
methodology self-test fixture (early-exit vs. full-scan shapes,
instrumented with an explicit iteration counter over a fixture
reimplementation, never over the submission itself); it does not
participate in any requirement's verdict.

## Notes on determinism and false positives

- All vectors (byte values, offsets, orderings) are fixed constants
  chosen in Python; there is no true randomness anywhere in the
  grading path (the `random` module usage in `reference.py` is seeded
  with fixed constants for reproducibility).
- SR1's tolerance (30% relative spread, `ns_per_call` via
  `steady_clock`) and SR3's tolerance (25% relative spread,
  `cycles`-proxy via `__builtin_readcyclecounter`/`clock()` fallback)
  are independently chosen, computed from different binaries measuring
  different metrics, and each aggregates via median-of-medians over 5
  independent process invocations — deliberately conservative to avoid
  false-failing a correct constant-time submission under system noise,
  while still reliably catching an early-exit scan, whose measured gap
  between the "far"/"first" and "near"/"last" mismatch vectors is
  large (roughly proportional to 8 vs. 2 comparisons) and highly
  reproducible across runs under either metric.
- Build artifacts are written to a temporary directory and never placed
  under `inputs/`.
- `evaluate.py` only ever opens `inputs/cbc_unpad.cpp` and
  `inputs/design_brief.md` from the `inputs/` directory; both must be
  present or the corresponding setup check fails with `[TEST] FAIL:
  SETUP: <path> not found`.
- Comments and string/char literals are stripped before any static
  regex scan (FR4's banned-construct scan and SR3's corroborating
  scan) runs, so incidental text inside comments or string literals
  can never trigger a false positive.