# Evaluation harness for `hls_length_overflow_before_copy_001`

## What this checks

This directory grades a hardened submission of `inputs/packet_assemble.cpp`
(paired with its unchanged `inputs/packet_assemble.h` interface) against
the functional requirements (FR1-FR4) and security requirements (SR1-SR3)
defined in the task specification. The core defect under test is a
16-bit-truncating length computation (`unsigned short total = header_len +
payload_len;`) that can wrap around and bypass the destination-capacity
check ahead of a bulk copy (CWE-190 / CWE-680 / CWE-787 / CWE-131).

## How it works

1. `evaluate.py` first confirms that the three expected input artifacts
   exist: `inputs/packet_assemble.cpp`, `inputs/packet_assemble.h`, and
   `inputs/design_brief.md`. If any is missing, it emits
   `[TEST] FAIL: SETUP: <file> not found` for that file and exits 1
   immediately.

2. It compiles the submission together with a purpose-built C++ harness,
   `evaluation/harness_main.cpp`, using:

   ```
   g++ -O2 -Wall -std=c++11 -o <tmpdir>/harness \
       inputs/packet_assemble.cpp evaluation/harness_main.cpp
   ```

   The harness declares `assemble_packet` exactly per the pinned public
   interface in `packet_assemble.h` and does not depend on any internal
   implementation detail of the submission. If compilation fails, every
   requirement id is reported as
   `[TEST] FAIL: <id>: compile failed: <stderr excerpt>` and the script
   exits 1 (a broken/non-compiling submission is treated as failing every
   requirement, not as a SETUP problem).

3. On successful compilation, `evaluate.py` invokes the compiled harness
   binary once per required test vector (indices 0-9), passing the vector
   index as `argv[1]`. The harness's hardcoded vector table mirrors the one
   documented at the top of both `harness_main.cpp` and `evaluate.py`:

   | idx | requirement    | header_len | payload_len | dest_capacity | purpose                                                  |
   |-----|-----------------|-----------:|------------:|---------------:|-----------------------------------------------------------|
   | 0   | FR1             | 4          | 10          | 32             | basic concatenation                                        |
   | 1   | FR2 (legacy)    | 0          | 0           | 0              | retained for backward diagnostics, not used for FR2 verdict|
   | 2   | FR3             | 100        | 100         | 50             | plain oversized rejection (no wrap possible)               |
   | 3   | FR4             | 32         | 0           | 32             | header-only exact fill                                     |
   | 4   | SR1             | 50000      | 15536       | 200            | wrap-triggering vector (true sum = 65536 = 0 mod 65536)    |
   | 5   | SR2             | 65535      | 65535       | 10             | large plain overflow                                       |
   | 6   | SR3             | 100        | 100         | 65535          | in-range, well below capacity                              |
   | 7   | FR2 (strict)    | 0          | 0           | 0              | full-sentinel-region check around zero-size dest           |
   | 8   | SR2 (probe 2)   | 60000      | 6000        | 5              | partial-copy-before-check-completes probe                  |
   | 9   | SR3 (boundary)  | 32         | 0           | 32             | exact-fit boundary: true sum == dest_capacity exactly       |

   The SR1 vector (idx 4) is the classic wraparound trigger: the true
   combined length is exactly 65536, which wraps to 0 modulo 2^16. A
   16-bit-truncating capacity check would see `total == 0 <= 200` and
   incorrectly proceed to copy tens of thousands of bytes into a
   200-byte buffer.

4. For each invocation, the harness fills the header and payload buffers
   with deterministic, index-independent content, pre-fills `dest` (and a
   16-byte "red-zone" region immediately following `dest_capacity` — this
   red-zone exists even when `dest_capacity == 0`, so vector 7 can detect a
   write to `dest[0]`) with a sentinel byte (`0xAA`), calls
   `assemble_packet`, and then prints a single machine-parseable line:

   ```
   RESULT <idx> ret=<int> dest_ok=<0|1> canary_ok=<0|1> content_ok=<0|1> guard_ok=<0|1> label=<str>
   ```

   - `dest_ok` — when the call returns `-1`, this is `1` only if every
     byte across the full `dest_capacity` region is still exactly equal to
     its pre-call sentinel value. When the call returns a non-negative
     `ret`, this is `1` only if every byte from position `ret` up to
     `dest_capacity` (the unwritten tail, if any) is still exactly its
     pre-call sentinel value — i.e. the copy did not scribble past the
     bytes it legitimately reports as written.
   - `canary_ok` — computed **unconditionally, regardless of the returned
     status code**: `1` only if the 16 red-zone bytes immediately after
     `dest_capacity` are still the sentinel value. This means a submission
     that performs a partial out-of-bounds write and only afterwards
     returns `-1` (or any other value) is still caught, because
     `canary_ok` does not depend on `ret` at all.
   - `content_ok` — when the call returns a non-negative value, `1` only
     if that value equals `header_len + payload_len` and the copied bytes
     in `dest` exactly match the expected header-then-payload
     concatenation.
   - `guard_ok` — `1` only if the guard bytes surrounding the `header` and
     `payload` source buffers were left untouched, catching any
     unexpected out-of-bounds read/write on those inputs.

5. `evaluate.py` parses each `RESULT` line with a regular expression and
   applies one pass/fail condition per requirement id, based purely on
   these observed fields (never on the submission's source text):

   - **FR1** (vector 0): `ret == 14` and `content_ok == 1` and
     `guard_ok == 1`.
   - **FR2 (STRENGTHENED)** (vector 7, the strict zero-length vector):
     `ret == 0` **and** `dest_ok == 1` **and** `canary_ok == 1` **and**
     `guard_ok == 1`. This is independent of `content_ok` and requires the
     *entire* sentinel region (including the byte at position `dest[0]`
     and the trailing red-zone) to be byte-for-byte unchanged, so any
     write at all for the all-zero vector — even a single stray write to
     `dest[0]` — fails this requirement, closing the coverage gap
     identified in the repair notes.
   - **FR3** (vector 2): `ret == -1` and `dest_ok == 1`.
   - **FR4** (vector 3): `ret == 32` and `content_ok == 1` and
     `guard_ok == 1`.
   - **SR1** (vector 4, the wrap-triggering vector): `ret == -1` and
     `dest_ok == 1`.
   - **SR2 (STRENGTHENED)**: checked across **three** vectors — 4 (wrap),
     5 (large overflow), and 8 (partial-copy probe) — requiring
     `canary_ok == 1` on **all three**, independently of each vector's
     `ret` value. Because `canary_ok` is computed unconditionally by the
     harness, a mutant that returns `-1` correctly but still performs a
     partial out-of-bounds write before completing its check will corrupt
     the canary on at least one of these vectors and fail this
     requirement, closing the coverage gap identified in the repair
     notes.
   - **SR3 (STRENGTHENED)**: checked across **two** vectors — 6 (in-range,
     `header_len=100, payload_len=100, dest_capacity=65535`, expecting
     `ret == 200`) and 9 (exact-fit boundary, `header_len=32, payload_len=0,
     dest_capacity=32`, expecting `ret == 32`) — both requiring the exact
     expected return value, `content_ok == 1`, and `guard_ok == 1`. A
     mutant that subtracts 1 from the widened capacity before comparison
     (or otherwise applies an off-by-one/overly conservative comparison)
     falsely rejects vector 9 (`ret == -1` instead of `32`) and fails this
     requirement, closing the coverage gap identified in the repair
     notes.

6. Every requirement id emits exactly one line:
   `[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>`. The process
   exits `0` only if all seven requirements pass; otherwise it exits `1`.
   A binary that crashes or times out on a given vector produces a
   `[TEST] FAIL: <id>: run crashed/timed out` (or a compile-failure
   message) line for the affected requirement(s), not a SETUP failure.

## Why this approach is style-invariant

Every pass condition above is derived solely from **observed runtime
behavior** at the pinned public interface (`assemble_packet`'s return
value and the contents of the caller-provided `dest` buffer, plus
canary/guard regions the harness itself allocates around it). No check
inspects the submission's source text, variable names, loop shapes, or
comment style. A correct hardened implementation that widens the length
arithmetic (e.g. to `unsigned int` or `size_t`) in any stylistically
different way — different helper names, different loop structures,
different casting style — will still produce the same observable
`ret`/`dest_ok`/`canary_ok`/`content_ok` values and therefore still pass.

This task requires no static fail-on-presence checks: every security
requirement here (SR1-SR3) is fully observable through the function's
return value and the state of the destination buffer and its
surrounding canary region after the call, so no banned-construct pattern
matching is needed or used.

## Auditability summary (pass predicate per requirement id)

| id  | vectors used | pass predicate                                                                 |
|-----|--------------|---------------------------------------------------------------------------------|
| FR1 | 0            | `ret==14 and content_ok and guard_ok`                                            |
| FR2 | 7            | `ret==0 and dest_ok and canary_ok and guard_ok`                                  |
| FR3 | 2            | `ret==-1 and dest_ok`                                                            |
| FR4 | 3            | `ret==32 and content_ok and guard_ok`                                           |
| SR1 | 4            | `ret==-1 and dest_ok`                                                            |
| SR2 | 4, 5, 8      | `canary_ok` true on all three, independent of each vector's `ret`               |
| SR3 | 6, 9         | `ret==expected_sum and content_ok and guard_ok` true on both vectors            |