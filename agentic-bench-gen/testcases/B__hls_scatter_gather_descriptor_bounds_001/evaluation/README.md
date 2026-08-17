# Scatter-Gather Descriptor Bounds Evaluation

## What this evaluates

This directory grades `inputs/scatter_gather.cpp` — the submitted hardened
implementation of:

```c
extern "C" int scatter_gather_copy(
    const unsigned char* src, unsigned int src_len,
    unsigned char* dst, unsigned int dst_len,
    const unsigned int* offsets, const unsigned int* lengths,
    unsigned int desc_count);
```

Grading is entirely **behavioral**: the submission is compiled and executed
against a fixed test harness, and every requirement (functional and
security) is decided from the harness's observed runtime behavior. There
are no static source-text checks in `evaluate.py` — nothing is judged by
inspecting how the code is written, only by what the compiled binary
actually does when run against known descriptor batches.

## How it works

1. `evaluate.py` confirms `inputs/scatter_gather.cpp` and
   `inputs/design_brief.md` exist. If either is missing, it emits
   `[TEST] FAIL: SETUP: <path> not found` and exits 1.
2. It compiles `inputs/scatter_gather.cpp` together with
   `evaluation/harness_main.cpp` using:

   ```
   g++ -std=c++17 -Wall -Wextra -O0 -o <tmpdir>/harness \
       inputs/scatter_gather.cpp evaluation/harness_main.cpp
   ```

   If compilation fails, every requirement (FR1-FR4, SR1-SR4) is reported
   as `[TEST] FAIL: <id>: compile failed: <compiler error excerpt>` and the
   script exits nonzero.
3. On successful compilation, `evaluate.py` runs the resulting binary once
   per probe name: `<tmpdir>/harness FR1`, `<tmpdir>/harness FR2`, ...,
   `<tmpdir>/harness SR4`, each with a timeout. Each invocation exercises
   exactly one fixed descriptor scenario and prints a single machine
   parseable line of the form:

   ```
   RESULT <PROBE> status=<int> dst_ok=<0|1> canary_ok=<0|1> [subA_ok=<0|1> subB_ok=<0|1>]
   ```

   - `status` is the raw return value of `scatter_gather_copy`.
   - `dst_ok` indicates whether the destination buffer's content matched
     what is required for that probe (either byte-exact expected copied
     data for functional probes, or "still all zero / unmodified" for
     rejection probes).
   - `canary_ok` indicates whether sentinel bytes placed immediately after
     the logical destination (and, where relevant, source) region are
     still intact, i.e. no out-of-bounds write/read was observed.
   - `subA_ok` / `subB_ok` are only emitted by the SR4 probe, which checks
     two boundary sub-cases in one run.
4. `evaluate.py` parses each `RESULT` line and applies a per-requirement
   verdict rule (described below), printing exactly one
   `[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>` line per
   requirement. The process exits 0 only if all eight requirements pass.
5. If a probe binary crashes, hangs, or produces no parseable `RESULT`
   line, that requirement is reported as
   `[TEST] FAIL: <id>: run crashed/timed out ...` rather than as a SETUP
   failure — a crash or a mangled/missing symbol is itself security- or
   correctness-relevant evidence, not an infrastructure problem.

## The eight probes

| Probe | High-level scenario |
|-------|----------------------|
| **FR1** | Full in-bounds copy: 3 descriptors covering a 30-byte `dst` exactly, `src` filled with sequential bytes 0..29. Expects `status==0` and `dst` byte-exact equal to `src`. |
| **FR2** | Multi-descriptor sequential source consumption: 2 descriptors on a 10-byte buffer, verifying descriptor `i+1` continues reading `src` immediately after descriptor `i` finished, in order. Expects `status==0` and byte-exact `dst`. |
| **FR3** | Compile/link check: a single trivial in-bounds descriptor call proves the submission compiles cleanly with `g++ -std=c++17 -Wall -Wextra`, links against the harness, and exposes `scatter_gather_copy` with C linkage callable from the pinned `extern "C"` declaration. Passing this probe requires only that the binary ran and printed a parseable `RESULT FR3 ...` line. |
| **FR4** | Zero-descriptor no-op: `desc_count=0` with `offsets`/`lengths` passed as `nullptr`. Expects `status==0` and `dst` left completely unmodified (still all-zero). |
| **SR1** | 32-bit overflow wraparound descriptor: `offsets[0]=0xFFFFFFF0`, `lengths[0]=0x20`, whose sum overflows 32-bit unsigned arithmetic and wraps to a small in-range-looking value. Expects the batch to be rejected (`status!=0`), `dst` left all-zero, and canary bytes placed right after the logical `dst` region untouched. |
| **SR2** | Partial-batch-then-invalid rejection: a valid descriptor, followed by an out-of-bounds descriptor, followed by another valid descriptor. Expects the *entire* batch rejected with `dst` left completely unmodified — catching implementations that write earlier valid-looking entries before validating the rest of the list. |
| **SR3** | Source overrun via cumulative length: destination offsets are individually in-bounds, but the sum of descriptor lengths exceeds `src_len`. Expects rejection (`status!=0`), `dst` left unmodified, and sentinel bytes placed immediately after the logical `src` region unchanged (no over-read past `src`). |
| **SR4** | Exact-boundary handling: sub-case A uses `offset + length == dst_len` exactly (must be accepted and copied correctly); sub-case B uses `offset + length == dst_len + 1`, one byte over (must be rejected with `dst` left unmodified). Both sub-cases must behave correctly for SR4 to pass. |

## Verdict rules

- **FR1, FR2, FR4** pass when `status == 0` and `dst_ok == 1` (the observed
  `dst` contents match what the requirement mandates for that scenario).
- **FR3** passes when the binary compiled, ran, and printed a parseable
  `RESULT FR3 ...` line at all — this alone demonstrates the required
  C-linkage/compile/run compatibility.
- **SR1, SR2, SR3** pass when `status != 0` (the batch was rejected),
  `dst_ok == 1` (the destination was left completely unmodified rather
  than partially written), and `canary_ok == 1` (no out-of-bounds write or
  read was detected via the adjacent sentinel bytes).
- **SR4** passes when both `subA_ok == 1` (the exact-fit boundary case was
  accepted and copied correctly) and `subB_ok == 1` (the one-byte-over
  case was rejected with `dst` left unmodified).

## Notes

- No static analysis of `inputs/scatter_gather.cpp` source text is
  performed anywhere in this grading pipeline. Every PASS/FAIL decision is
  derived from compiling the submission and observing the runtime
  behavior of the compiled binary against the fixed descriptor scenarios
  above.
- All buffers, descriptor values, and canary/sentinel placements are fixed
  and deterministic; there is no reliance on wall-clock time, randomness,
  or environment-dependent behavior.
- A submission that fails to compile is scored as failing every one of
  the eight requirements, with the compiler's error output (truncated)
  included in each failure reason so the specific diagnostic is visible.