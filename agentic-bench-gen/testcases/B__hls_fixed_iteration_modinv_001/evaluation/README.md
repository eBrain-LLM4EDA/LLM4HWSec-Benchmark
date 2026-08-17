# Evaluation: Fixed-Iteration Modular Inverse (hls_fixed_iteration_modinv_001)

## What this grader does

`evaluate.py` implements the `compile_and_run` evaluation contract for this
task. It:

1. Verifies that `inputs/modinv_kernel.cpp`, `inputs/modinv_kernel.h`, and
   `inputs/design_brief.md` exist (missing files produce a `SETUP` failure).
2. Compiles `inputs/modinv_kernel.cpp` together with `evaluation/harness_main.cpp`
   using `g++ -std=c++11 -O0 -I inputs -o <tmp>/harness inputs/modinv_kernel.cpp evaluation/harness_main.cpp`,
   with a bounded timeout. `harness_main.cpp` calls the pinned entry point
   `unsigned int modinv(unsigned int a);` and references `MOD` and
   `g_iter_count` exactly as declared in `modinv_kernel.h`.
3. Runs the resulting binary once (bounded timeout) and parses its stdout,
   which prints one machine-readable line per probe:
   - `MOD_VALUE <v>` — the compile-time `MOD` constant.
   - `FUNC a=<a> r=<r>` — `modinv(a)` for every `a` in `[1,250]`.
   - `ITER a=<a> count=<c>` — the value of `g_iter_count` after a fresh
     (zeroed) call to `modinv(a)`, for every `a` in `[1,250]`.
   - `REPEAT a=<a> r=<r>` — results of calling `modinv` on a fixed-seed,
     interleaved/repeated sequence of operands, to catch cross-call state
     corruption.
   - `TIMING_TRIAL a=<a> trial=<t> ns=<elapsed>` — wall-clock time for one
     timed trial (a tight loop of many repeated calls to `modinv(a)`), for
     several independent trials per operand, after an untimed warmup phase.
4. Derives PASS/FAIL for each requirement purely from this observed
   behavior, except for two static fail-on-presence checks (SR2, and part
   of FR2) which scan the submitted source text only to detect the
   presence of a banned construct — never to grant a PASS.
5. If compilation fails, every behaviorally-graded requirement
   (FR1, FR2, FR3, FR4, SR1, SR3) is marked FAIL with a concise compiler
   error summary; SR2's static scan still runs independently. If the
   binary crashes or times out, the run-dependent requirements
   (FR1, FR3, FR4, SR1, SR3) are marked FAIL as a crashed/timed-out probe
   (not `SETUP`).
6. Exits `0` only if every requirement passes; otherwise exits non-zero.

## Requirement pass criteria (one line each)

- **FR1** — For every operand `a` in `[1,250]`, the parsed `FUNC a=<a> r=<r>`
  line satisfies `(a * r) % 251 == 1` (checked arithmetically in Python,
  not against a hardcoded table).
- **FR2** — The submission compiles cleanly with `g++ -std=c++11` (exit
  code 0), AND a fail-on-presence static scan of `modinv_kernel.cpp` finds
  no `malloc`/`calloc`/`realloc`, no `new`, no `std::` usage, and no
  self-recursive call to `modinv` inside its own body.
- **FR3** — The harness-printed `MOD_VALUE` line equals `251`.
- **FR4** — Every `REPEAT a=<a> r=<r>` line (from a fixed-seed, interleaved,
  repeated-call sequence) matches the corresponding `FUNC` result for that
  same operand, showing no leftover-state corruption across calls.
- **SR1** — The `ITER a=<a> count=<c>` value is numerically identical for
  every operand `a` in `[1,250]` (the counter is reset to zero before each
  call), demonstrating the loop executes a fixed number of iterations
  regardless of the operand. This is the **primary, authoritative signal**
  for operand-independent (constant-time) execution: it directly measures
  the invariant the security requirement cares about (fixed iteration
  count), rather than inferring it indirectly from noisy wall-clock
  measurements.
- **SR2** — Fail-on-presence static scan: the innermost `for`/`while` loop
  block that increments `g_iter_count` is located via brace matching, and
  that block's text is searched for `break` or `return` statements; any
  match is an automatic FAIL (banned data-dependent early exit), absence
  is a PASS.
- **SR3** — A **secondary, corroborating** wall-clock check. For each of a
  fixed set of operands, the harness runs an untimed warmup phase followed
  by 15 independent timed trials (each trial = 50000 repeated calls to
  `modinv(a)`). For each operand, `evaluate.py` discards the single fastest
  and slowest trial (outlier trimming) and takes the median of the
  remaining trials as that operand's representative timing. It then
  computes the relative spread `(max_median - min_median) / min_median`
  across all tested operands and asserts it stays below `0.60`.

## Why SR3's tolerance is generous and why SR1 is authoritative

Wall-clock measurement at `-O0`, without CPU pinning, warmup-free
sampling, or multi-trial averaging, is extremely noisy: scheduler
preemption, cache/TLB state, frequency scaling, and background system load
can easily produce 2x+ spread across otherwise-identical repeated
measurements of a provably constant-iteration-count implementation. A
single-sample timing check at a tight tolerance (e.g. 0.25) can therefore
false-reject a genuinely secure, fixed-iteration, branchless submission
purely due to environmental noise — this is a defect in the timing
methodology, not in the submission.

To make SR3 a reliable *corroborating* check rather than the sole
determinant of constant-time behavior:

- The harness performs a warmup phase per operand (20000 untimed calls)
  to avoid cold-cache and frequency-scaling skew contaminating the first
  measurements for that operand.
- The harness runs 15 independent timed trials per operand instead of a
  single sample, so isolated scheduler hiccups affect at most one trial.
- `evaluate.py` trims the single fastest and slowest trial per operand and
  takes the median of what remains, further suppressing the influence of
  rare outlier trials caused by system noise.
- The relative-spread tolerance is set to `0.60`, calibrated to be
  comfortably above the empirically observed noise floor of this
  unpinned, `-O0` measurement environment for a correct constant-iteration
  implementation, while remaining well below the spread produced by the
  insecure baseline's genuinely operand-dependent iteration count (whose
  timing variance is driven by real algorithmic differences in work done,
  not just measurement noise).

Because SR1 already independently and deterministically verifies that the
instrumented iteration count is identical for every operand (the ground
truth signal for this class of timing side channel), SR3 is treated as a
secondary, best-effort corroboration of that same property via wall-clock
behavior — not as an independent gate that could arbitrarily reject a
submission that already passes SR1 due to environmental jitter alone.

## Contract notes

- This task follows the `compile_and_run` evaluation contract: all
  functional and most security properties are graded **behaviorally** by
  compiling and executing a harness binary against `inputs/modinv_kernel.cpp`
  and `inputs/modinv_kernel.h`, never by matching source style.
- The only static checks are **fail-on-presence** exceptions, used solely
  to detect vulnerability/banned constructs that execution cannot reliably
  observe:
  - **SR2**: absence of `break`/`return` inside the core inversion loop
    (a correct, differently-styled implementation simply does not contain
    this construct, so it can never be falsely rejected).
  - **Part of FR2**: absence of dynamic allocation, STL usage, and
    self-recursion, which are synthesizability constraints rather than
    something observable purely from `modinv`'s return value.
- These static checks never grant a PASS by themselves for FR2 — a
  submission must also actually compile successfully; the static scan can
  only additionally turn a would-be PASS into a FAIL.