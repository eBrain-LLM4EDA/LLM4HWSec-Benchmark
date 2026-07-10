# Evaluation: Constant-Time Tag Comparison (`mac_verify.cpp`)

This directory contains the evaluation harness for the `hls_constant_time_compare_001`
task. It grades the submitted `inputs/mac_verify.cpp` (together with
`inputs/mac_verify.h`) **in place** — you do not submit anything under
`evaluation/`; only the files under `inputs/` are graded.

## What `evaluate.py` does

1. **Setup checks.** Confirms `inputs/mac_verify.cpp` and `inputs/mac_verify.h`
   exist. If either is missing, evaluation aborts immediately with a `SETUP`
   failure.

2. **Compile.** Builds `inputs/mac_verify.cpp` together with
   `evaluation/harness_main.cpp` using:

   ```
   g++ -std=c++11 -O2 -I inputs -o <tmp>/harness inputs/mac_verify.cpp evaluation/harness_main.cpp
   ```

   The submitted `verify()` must match the pinned signature exactly:

   ```cpp
   bool verify(const unsigned char computed_tag[16], const unsigned char received_tag[16]);
   ```

   If compilation fails, every functional/compile-dependent requirement
   (FR1-FR4, SR3) is reported as failing with the compiler's error output.

3. **Run.** Executes the compiled binary. The harness itself constructs all
   test vectors deterministically (fixed RNG seed, no wall-clock dependence)
   and prints one result line per functional area, which `evaluate.py` then
   parses to derive pass/fail verdicts.

4. **Functional checks (FR1-FR4).** The harness drives `verify()` with:

   - **FR1** — a batch of distinct, randomly generated 16-byte tag values
     used as identical `(computed_tag, received_tag)` pairs; all must be
     accepted (`true`).
   - **FR2** — tags that differ in exactly one byte, exercised across every
     byte position, plus tags that differ in several bytes simultaneously;
     all must be rejected (`false`).
   - **FR3** — implicit in successful compilation and clean execution of the
     harness binary (no compile errors, no crash, no timeout).
   - **FR4** — the all-zero and all-`0xFF` tags used as `computed_tag`,
     `received_tag`, or both, in matching and non-matching combinations,
     each checked against the correct expected boolean.

   Each of these is judged purely on the boolean values `verify()` returns
   for the harness-supplied vectors — never on how the source code is
   written.

5. **Security checks (SR1-SR3).** These target the constant-time comparison
   requirements described in `design_brief.md`:

   - **SR1 / SR2** — the comparison must scan the full 16-byte buffer
     unconditionally and produce its boolean result only after that fixed
     scan completes, with no data-dependent early exit tied to where a
     mismatch first occurs. This is checked by inspecting the *structure*
     of any loop found inside `verify()`'s definition (not by matching
     specific variable names, helper names, or coding style). An
     implementation that never introduces such an early exit — whether
     written as a single accumulating loop, several loops, or fully
     unrolled with no loop at all — satisfies this.
   - **SR3** — the comparison must operate over the fixed 16-byte stack
     buffers only, using the pinned interface exactly, with no dynamic
     heap allocation on the code path taken by repeated `verify()` calls.
     This is checked through three complementary layers:
     1. a static interface-conformance check confirming that the
        `verify()` declaration in `mac_verify.h` still takes exactly the
        two pinned fixed-size 16-byte buffer parameters — rejecting any
        redefinition that adds a separate length/size parameter (whether
        defaulted or not), switches to a variadic parameter list, or
        otherwise deviates from the pinned two-parameter signature;
     2. a static fail-on-presence scan of `mac_verify.cpp` for
        dynamic/heap allocation constructs (e.g. `malloc`, `calloc`,
        `realloc`, `free`, `alloca`, `new`, `std::vector`, `std::string`)
        anywhere in the file, since some of these bypass the runtime
        allocation counter described below;
     3. a behavioral heap-allocation counter that instruments memory
        allocation during many repeated invocations of `verify()` over
        precomputed stack-resident test vectors and checks that no
        allocation occurs through the standard `operator new`/`operator
        new[]` path.

     All three layers must agree that no dynamic allocation or interface
     deviation is present for SR3 to pass.

## What this does *not* reveal

This README intentionally does not disclose the exact vector counts,
tolerance thresholds, or internal parsing/matching logic used by
`evaluate.py` and its private helper modules. Refer to
`inputs/design_brief.md` for the full public specification of the required
behavior, and to `mac_verify.h` for the pinned interface. A correct,
hardened implementation that satisfies the public specification —
preserving the pinned two-parameter fixed-16-byte-array signature,
scanning all 16 bytes unconditionally, returning a single boolean derived
from the complete scan, and using only fixed-size stack buffers — will
pass every check here regardless of internal naming, structure, or style.

## Requirements checked

| ID  | Type       | What it verifies |
|-----|------------|-------------------|
| FR1 | functional | Exact-match tags are accepted |
| FR2 | functional | Any single- or multi-byte mismatch is rejected |
| FR3 | functional | Compiles and runs cleanly with g++ against the pinned interface |
| FR4 | functional | All-zero / all-`0xFF` edge cases handled correctly |
| SR1 | security   | Fixed, content-independent scan of all 16 bytes (no early exit) |
| SR2 | security   | Final boolean derived only after the full scan completes |
| SR3 | security   | Pinned fixed-size interface preserved; no dynamic heap allocation on the comparison path (statically and behaviorally verified) |

Every requirement above is graded either by executing the compiled binary
and observing its output, or — for the structural security properties
that cannot be fully observed from `verify()`'s external behavior alone —
by a fail-on-presence check for the specific vulnerable construct being
guarded against. No check ever requires matching a particular coding
style, helper name, or source layout in order to pass.