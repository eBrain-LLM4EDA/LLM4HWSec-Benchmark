# Evaluation: Constant-time conditional swap for a scalar-multiplication ladder

This directory contains the automated grader for `inputs/ladder_swap.cpp`.
The grader is fully behavioral where possible: it compiles the submitted
file against a harness, runs the resulting binary in several modes, and
derives PASS/FAIL verdicts from observed program behavior. One static
scan is used only where behavior cannot directly observe the property.

## What gets graded

The submission is `inputs/ladder_swap.cpp`, graded **in place**. It must
implement:

```cpp
void conditional_swap(uint32_t *P, uint32_t *Q, int n, unsigned int ctrl_bit);
```

exactly as specified in the task's public interface. No other file under
`inputs/` is modified or required beyond `design_brief.md`, which is
read only to confirm its presence (context for the participant, not
graded).

## Build step: single-command compile+link

`inputs/ladder_swap.cpp` is compiled together with
`evaluation/harness_main.cpp` in a **single g++ invocation**:

```
g++ -std=c++17 -Wall -Wextra -O0 -o <tmp>/harness_bin inputs/ladder_swap.cpp evaluation/harness_main.cpp
```

Both translation units are passed to the same compiler invocation so
they are compiled and linked in one step, rather than compiled
separately into object files and linked afterward. This matters
because `evaluation/harness_main.cpp` declares:

```cpp
void conditional_swap(uint32_t *P, uint32_t *Q, int n, unsigned int ctrl_bit);
```

using **plain C++ linkage** (no `extern "C"`). Since the submission is
an ordinary C++17 translation unit defining a free function with that
exact signature, its mangled symbol matches the harness's ordinary C++
declaration by construction — there is no linkage-specifier mismatch
to trip over. Any correct implementation of the pinned signature will
therefore link successfully; the harness never assumes any internal
styling, naming, or structure inside the submission beyond the
signature itself.

A non-zero exit code from this build step fails `FR4` and also fails
every other requirement (`FR1-FR3`, `SR2-SR3`) with a "compile failed"
reason, since none of them can be meaningfully evaluated without a
working binary. The static `SR1` scan is still attempted separately,
since it only reads source text and does not require a successful
build.

## Evaluation flow

1. **Setup checks.** Confirm `inputs/ladder_swap.cpp`,
   `inputs/design_brief.md`, and `evaluation/harness_main.cpp` all
   exist. Any missing file is reported as `[TEST] FAIL: SETUP: ...`
   and the run aborts immediately.

2. **Compile (FR4).** See "Build step" above. Compile/link success
   yields `[TEST] PASS: FR4`; failure yields `[TEST] FAIL: FR4` with a
   compiler/linker stderr excerpt, and cascades a "compile failed"
   `FAIL` to `FR1`, `FR2`, `FR3`, `SR2`, and `SR3`.

3. **Functional probes (FR1, FR2, FR3).** The harness is run in
   `functional` mode. It exercises `conditional_swap` on deterministic,
   fixed-seed pseudo-random buffers for `n` in `{1, 2, 64, 4096}`:
   - `ctrl_bit = 1`: the harness asserts the resulting buffers are an
     exact element-wise swap of the original contents (**FR1**).
   - `ctrl_bit = 0`: the harness asserts the resulting buffers are
     byte-identical to the original contents (**FR2**).
   - Both checks running successfully, without crash or timeout, across
     all four sizes constitutes **FR3** (buffer-size robustness).

   The harness prints one `PROBE <name> <PASS|FAIL>` line per case;
   `evaluate.py` parses these lines to determine each requirement's
   verdict. A crash, timeout, or missing probe output is treated as a
   failure of the corresponding requirement(s), not as a setup error.

4. **SR1 — static fail-on-presence branch detector.** This is the
   *only* static check in this evaluation, and it is fail-on-presence
   only: it never causes a PASS by finding a pattern, only a FAIL. It
   scans the submitted source (with comments stripped) for any
   `if`/`while`/`for`/ternary construct whose condition textually
   references `ctrl_bit` directly, or a simple local variable that was
   assigned straight from an expression containing `ctrl_bit` and then
   used inside a later branch condition. This mirrors the shipped
   insecure baseline's `if (ctrl_bit & 1u) { ... }` structure. A
   constant-time implementation that computes a bitmask from
   `ctrl_bit` (e.g. `mask = 0 - (ctrl_bit & 1)`) and uses that mask
   purely in bitwise arithmetic — with no branch condition anywhere
   referencing `ctrl_bit` or a variable derived from it — will not
   match this pattern and will correctly **PASS**. This check can only
   ever cause a FAIL; it never determines a PASS based on the presence
   of any particular helper name, coding idiom, or style.

5. **SR2 — dynamic access-trace comparison.** The harness is run in
   `access_trace` mode at a fixed `n`, once for `ctrl_bit=0` and once
   for `ctrl_bit=1`. For each run it reports, in a fixed ascending
   index order, how many indices were visited/classified — a
   structural signal independent of the actual (secret-dependent)
   values written. `evaluate.py` requires this structural signal
   (index count / iteration shape) to be identical between the two
   `ctrl_bit` values. An implementation that skips the update loop
   entirely for one control value (as in the insecure baseline) would
   produce a different iteration/visitation shape and fail; a
   masked/branchless implementation that always touches every index
   in the same order for both control values will pass.

6. **SR3 — dynamic timing differential.** The harness is run in
   `timing` mode at a large `n`, executing many repeated calls to
   `conditional_swap` for each `ctrl_bit` value and reporting the
   median wall-clock time (after a warm-up). `evaluate.py` computes the
   ratio of the two medians and requires it to stay below a generous
   threshold (3x). This is deliberately loose to absorb normal system
   jitter while still catching a gross branch-skipping implementation
   where one control value's call is trivially fast because the whole
   loop body was skipped.

## Marker format

Every requirement produces exactly one line of the form:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <brief reason>
```

Requirement IDs used: `FR1`, `FR2`, `FR3`, `FR4`, `SR1`, `SR2`, `SR3`.
The process exits `0` only if every requirement line is a `PASS`;
otherwise it exits non-zero.

### Marker-completeness guarantee

`evaluate.py` guarantees that every requirement id listed above emits
exactly one `[TEST] PASS`/`[TEST] FAIL` line on every run, including
when compilation itself fails or when an earlier check block raises an
exception. Each stage (functional probes, SR1's static scan, SR2's
access-trace comparison, SR3's timing comparison) is wrapped in its own
`try`/`except` block, so an unexpected exception or crash in one stage
never prevents subsequent stages from running and reporting their own
verdicts. In particular, `SR3`'s marker (`[TEST] PASS: SR3` or
`[TEST] FAIL: SR3`) is always emitted with an id that matches the
requirement map character-for-character, regardless of whether earlier
checks (functional, SR1, SR2) passed, failed, or raised an exception.

If `g++` reports a non-zero exit code (or times out / cannot be
invoked), `FR4` is failed with the compiler's stderr excerpt, and
`FR1`, `FR2`, `FR3`, `SR2`, and `SR3` are immediately failed with a
"compile failed" reason each — none of them are silently skipped just
because the binary never came into existence. `SR1` is independent of
compilation success since it is a pure source-text scan, so it always
runs and reports its own verdict regardless of whether the build
succeeded.

As a final safety net, after all checks run, `evaluate.py` scans the
full requirement id list one more time and fails (rather than silently
omitting) any id that still has no verdict recorded, so no internal gap
in the grader logic can result in a missing marker. `[TEST] SKIP` is
never emitted for any requirement.

## Notes on static vs. behavioral checks

Only `SR1` uses a static source scan, and it is strictly
fail-on-presence: it can only cause a `FAIL` by finding a banned
branch-on-secret construct in the source text. It never causes a
`PASS` based on the presence of any particular coding pattern, helper
name, or style. All other requirements (`FR1-FR4`, `SR2`, `SR3`) are
graded purely from the observed behavior of the compiled, executed
binary — output correctness, structural access-visitation shape, and
timing ratios — so that any implementation satisfying the public
specification will pass regardless of naming, formatting, or internal
structure, as long as it avoids branching on the secret control bit.