# Constant-Time Modular Exponentiation — Evaluation Harness

This directory contains the evaluation harness for the `modexp_kernel.cpp`
HLS security benchmark. It grades the submission under `inputs/` **in
place**: `inputs/modexp_kernel.cpp` must compile and behave correctly
against the harness below, and must not exhibit exponent-dependent
control flow or forbidden I/O.

## Entry point

Run:

```
python3 evaluation/evaluate.py
```

from the repository root (the directory containing `inputs/` and
`evaluation/`). It prints one line per requirement:

```
[TEST] PASS: <ID>
[TEST] FAIL: <ID>: <reason>
```

and exits `0` only if every requirement (`FR1`, `FR2`, `FR3`, `FR4`,
`SR1`, `SR2`, `SR3`) passes.

## Harness binary (`harness_main.cpp`) argv contract

`evaluation/harness_main.cpp` is compiled together with
`inputs/modexp_kernel.cpp` to produce a small standalone test binary. It
declares the pinned entry point exactly as specified:

```c
extern uint32_t modexp(uint32_t base, uint32_t exponent, uint32_t modulus);
```

Invocation:

```
./harness base exponent modulus
```

- `argv[1]` = `base` (unsigned 32-bit, decimal or `0x`-prefixed hex)
- `argv[2]` = `exponent` (unsigned 32-bit, decimal or `0x`-prefixed hex)
- `argv[3]` = `modulus` (unsigned 32-bit, decimal or `0x`-prefixed hex)

All three are parsed with `strtoul(..., 0)`. The binary calls `modexp()`
exactly once and prints **exactly one** line to stdout:

```
RESULT <decimal-uint32>
```

then exits with status `0`. The harness performs no other stdout
output and no file or network I/O. It is compiled in two distinct
build flavors against the same unmodified source:

1. **Plain build** (`g++ -O0 -std=c++11 -o harness_plain
   modexp_kernel.cpp harness_main.cpp`) — a single combined
   compile-and-link invocation used for the functional known-answer
   checks (FR1, FR2) and as the compile step gating FR3.
2. **Coverage build** (used for the gcov-based structural-invariance
   checks FR4, SR1, SR2) — an **explicit two-step compile-then-link**,
   described below, rather than a single combined `g++` invocation.

### Coverage build details (two-step compile + link)

`evaluation/private/coverage_utils.py`'s `compile_coverage_binary(build_dir)`
stages copies of `inputs/modexp_kernel.cpp` and
`evaluation/harness_main.cpp` into `build_dir`, then builds the
coverage binary as follows, with **every subprocess invocation run
with `cwd=build_dir`**:

1. `g++ --coverage -O0 -std=c++11 -c modexp_kernel.cpp -o modexp_kernel.o`
2. `g++ --coverage -O0 -std=c++11 -c harness_main.cpp -o harness_main.o`
3. `g++ --coverage -o harness_cov modexp_kernel.o harness_main.o`

Compiling each translation unit separately (steps 1–2) causes GCC to
emit `modexp_kernel.gcno` / `harness_main.gcno` notes files whose
relative paths are anchored to `build_dir` and match the corresponding
`.o` files exactly, and running the link step with `--coverage` and
`cwd=build_dir` ensures the runtime coverage library is linked in and
the `.gcda` data files produced at run time land in the same
directory as the `.gcno` notes files.

### Corrected gcov invocation

After running the compiled `./harness_cov` binary (also with
`cwd=build_dir`), `run_and_collect()` invokes:

```
gcov -b modexp_kernel.cpp
```

with `cwd=build_dir` — the same working directory used for every
compile step — so the relative `.gcno`/`.gcda` lookups succeed, and
parses the resulting `modexp_kernel.cpp.gcov` file.

The invocation deliberately does **not** pass the `-n` / `--no-output`
flag, since that flag suppresses writing the per-source `.gcov` text
report to disk entirely (only a percentage summary is printed to
stdout). With `-n` removed, `gcov -b modexp_kernel.cpp` writes
`modexp_kernel.cpp.gcov` into `build_dir` alongside the colocated
`.gcno`/`.o`/`.gcda` files from the two-step build described above, and
`run_and_collect()` can read it directly.

Any stale `modexp_kernel.gcda`, `harness_main.gcda`,
`modexp_kernel.cpp.gcov`, or `harness_main.cpp.gcov` left over from a
previous run in the same `build_dir` is removed before each run so
that per-exponent coverage data is never contaminated by a prior
invocation.

## Check categories

Every requirement is graded one of two ways; static source inspection
is **never** used to make a requirement PASS, only to make it FAIL on
a detected banned construct.

### 1. Behavioral compile-and-run checks

The submission is compiled with `g++` against `harness_main.cpp` and
executed as a subprocess; PASS/FAIL is derived strictly from observed
program output.

- **FR1** — Compiles the plain binary and runs it against a fixed
  vector set: an `exponent = 0` case, an `exponent = 1` case, a
  `modulus = 2` case, plus 6 additional vectors generated with
  `random.seed(20240501)` (`modulus` in `[2, 65535]`, `base < modulus`,
  `exponent` any 32-bit value). Each expected result is computed
  independently in Python via the standard-library `pow(base,
  exponent, modulus)`. Any returned value that does not match exactly,
  or any compile failure, fails FR1.
- **FR2** — Reuses the plain binary and checks the two modexp
  conventions: `modexp(0, e, m) == 0` for `e > 0, m > 1`, and
  `modexp(b, 0, m) == 1` for `b > 0, m > 1`.
- **FR3** — Reuses the FR1 plain-build compile result (a compile
  failure fails FR3 too) and additionally performs a fail-on-presence
  scan of `inputs/modexp_kernel.cpp` for `malloc(`, `new `,
  `std::vector`, `std::map`, `printf(`, `exit(`, `abort(`.
- **FR4** — Compiles the coverage build (two-step compile + link,
  see above) and runs it for four fixed exponents (`0`, `1`,
  `0xFFFFFFFF`, and one value from `random.seed(77)`) with a fixed
  `base = 3`, `modulus = 257`. Using `gcov` per-line hit counts (now
  reliably produced by the corrected `gcov -b` invocation described
  above), it verifies that every source line containing `for`/`while`
  has an identical hit count across all four exponents, and that at
  least one such line's count is `32` or `33` (confirming a fixed
  32-iteration schedule is actually exercised).

### 2. gcov-based structural-invariance behavioral checks (SR1, SR2)

These reuse the same 4-run coverage evidence gathered for FR4 (own
build directory, same fixed exponents/base/modulus, same two-step
coverage build and corrected `gcov -b` invocation):

- **SR1** — Compares the full ordered list of per-line execution
  counts across all four exponents. A secure, constant-schedule kernel
  produces byte-for-byte identical counts on every executable line
  regardless of exponent value. On the shipped baseline, the guarded
  multiply line inside `if ((exponent >> i) & 1u) { ... }` shows `0`
  hits for `exponent = 0` but `32` hits for `exponent = 0xFFFFFFFF`,
  which this check detects and fails.
- **SR2** — Compares the full ordered list of `gcov -b` branch-taken
  annotations across the same four exponents, catching any
  exponent-dependent control-flow path even if aggregate per-line
  counts happened to coincide.

### 3. Static fail-on-presence scans

Used only where behavior at the interface cannot directly observe the
construct, and only in a FAIL-on-presence direction (a correct,
hardened submission simply does not contain the pattern, so it can
never be falsely rejected):

- **FR3** (partial) — banned dynamic-allocation/STL/exit/debug tokens.
- **SR3** — a two-part scan (see below).

#### SR3 in detail (strengthened exponent-leakage detector)

SR3 must catch the CWE-200 exponent-leakage vulnerability, not just
banned I/O calls. It fails on presence of either of the following:

1. **Banned I/O calls** — `printf(`, `std::cout`, `fprintf(` anywhere
   in `inputs/modexp_kernel.cpp`, which would leak the exponent (or
   any secret-derived state) through an unintended output channel.
2. **The CWE-200 global-leak pattern** — the co-occurrence, all in the
   same file, of:
   - a namespace-scope (file-scope), non-`const` mutable scalar
     variable declaration (e.g. `static uint32_t g_last_exponent;`),
   - an assignment of the raw `exponent` parameter's value (optionally
     through a direct cast) to that variable *inside the body of
     `modexp()`* (e.g. `g_last_exponent = exponent;`), and
   - an additional externally-visible function definition (any
     function other than `modexp` itself) whose body contains a
     `return` of that same variable (e.g. `uint32_t
     get_last_exponent() { return g_last_exponent; }`).

   All three sub-conditions must co-occur for SR3 to FAIL. A submission
   that declares an unrelated global, or an unrelated helper function
   that happens to share a variable name pattern, is not falsely
   rejected — the scan requires the exact combination of a qualifying
   global, an in-`modexp()` assignment from `exponent` into it, and an
   accessor elsewhere that returns it.

This remains a **fail-on-presence-only static check**, consistent with
the `compile_and_run` evaluation contract: it can never be the reason
a requirement PASSes, only the reason it FAILs. Absence of both
patterns PASSes SR3 — which is the case for the shipped insecure
baseline (its vulnerability is the branchy square-and-multiply loop
caught by SR1/SR2, not an exponent leak through global state) and for
any correct hardened submission. A synthetic mutant that copies its
`exponent` parameter into a file-scope static variable and exposes it
via an extra accessor function reintroduces exactly the pattern in (2)
above and must produce `[TEST] FAIL: SR3`.

## Toolchain

- `g++` — compiles both the plain and coverage-instrumented binaries
  (C++11). The coverage build uses two separate `g++ --coverage -c`
  compile invocations followed by a `g++ --coverage` link invocation,
  all run with a consistent working directory.
- `gcov` — bundled with the same GCC installation as `g++`; invoked as
  `gcov -b modexp_kernel.cpp` (no `-n`) from the same working
  directory used at compile time, so it can locate the colocated
  `.gcno`/`.gcda` files and actually writes the `modexp_kernel.cpp.gcov`
  report used to extract per-line and per-branch execution counts
  after each run.

No other external tools are required. Python 3 stdlib only is used by
`evaluate.py` and its private helper modules; the domain toolchain is
invoked exclusively via `subprocess`.

## Deterministic seeds and fixed vectors

All checks are fully deterministic and reproducible:

- **FR1 / FR2 vectors**: `random.Random(20240501)` generates 6
  additional randomized `(base, exponent, modulus)` triples on top of
  3 fixed edge-case vectors (`exponent = 0`, `exponent = 1`,
  `modulus = 2`), plus 2 fixed edge vectors for FR2
  (`base = 0` / `exponent = 0`).
- **FR4 / SR1 / SR2 coverage runs**: exponents `{0, 1, 0xFFFFFFFF,
  random.Random(77).randint(0, 0xFFFFFFFF)}`, with fixed `base = 3`
  and `modulus = 257` in every run, so the same 4-run coverage
  evidence characterizes both the functional (FR4) and security
  (SR1, SR2) invariance properties.

## Environment notes

- No network access is used or required anywhere in the harness.
- Every `subprocess` invocation (each coverage compile/link step,
  plain compilation, binary execution, and `gcov` invocation) uses an
  explicit 30-second timeout. A timeout is treated as a failing
  behavioral probe for the requirement being checked (`run
  crashed/timed out`), not as a `SETUP` failure.
- `SETUP` failures are reserved strictly for missing required files
  (`inputs/modexp_kernel.cpp`, `inputs/design_brief.md`,
  `evaluation/harness_main.cpp`) and are checked before any
  requirement-specific logic runs.