# Evaluation: hls_key_indexed_lookup_001 — Fixed-pattern lookup for a key-indexed table

This directory contains the behavioral grading harness for the submission
`inputs/lookup_kernel.cpp`. Grading follows the `compile_and_run` evaluation
contract: the submission is compiled with `g++` against harness code we
provide, executed, and PASS/FAIL for each requirement is derived from the
compiled binary's observed behavior. Static source inspection is used only
in the two narrow, fail-on-presence-only places documented below.

## What gets compiled

`evaluate.py` builds **two separate binaries**, each pulling in the
submission file `inputs/lookup_kernel.cpp` exactly **once**, via exactly
**one** translation unit. `inputs/lookup_kernel.cpp` is never passed
directly to the compiler as its own top-level source argument, and it is
never `#include`d twice within the same binary — this avoids any
duplicate-symbol or macro-redefinition compile error regardless of how the
submission structures its own internal helpers, static consts, or
namespaces.

### 1. Plain build (no `TRACE_MODE`)

```
g++ -std=c++11 -O0 -o harness_plain_O0 evaluation/table_accessor.cpp evaluation/harness_main.cpp
g++ -std=c++11 -O2 -o harness_plain_O2 evaluation/table_accessor.cpp evaluation/harness_main.cpp
g++ -std=c++11 -Wall -Wextra -O0 -o harness_warn_O0 evaluation/table_accessor.cpp evaluation/harness_main.cpp
```

Here `evaluation/table_accessor.cpp` is the **only** file that
`#include`s `../inputs/lookup_kernel.cpp` in this build. It does so once,
normally (no macro tricks), and exposes a small `extern "C"` accessor:

```cpp
#include "../inputs/lookup_kernel.cpp"

extern "C" uint8_t harness_get_table_entry(int i) {
    return table[i];
}
```

`evaluation/harness_main.cpp` is compiled as a second, separate
translation unit in this mode. It never includes the kernel source itself
here; it only declares the pinned entry point and the accessor as
`extern` symbols:

```cpp
extern uint8_t lookup(uint8_t value, uint8_t key);
extern "C" uint8_t harness_get_table_entry(int i);
```

Because the kernel source is included exactly once, in exactly one
translation unit, there is no possibility of a duplicate-definition link
error for `lookup`, `table`, or any submission-internal helper — no
matter how the golden restructures, renames, or re-scopes its own code
relative to the baseline. In this build mode, the kernel's own guarded
`TRACE_ACCESS(idx)` macro resolves to whatever no-op the submission itself
defines when the macro is not already defined (per the public interface
contract), so this build measures only externally observable behavior:
the function's return value for given inputs, and the submission's own
table contents read back verbatim. It is used for:

- **FR1** — exhaustive 65536-pair output correctness.
- **FR2** — clean compilation gate (`-O0`, `-O2`, and `-Wall -Wextra`, hard
  errors only — warnings alone do not fail FR2).
- **SR4** — the same exhaustive 65536-pair sweep, framed as the
  correctness-preserved-under-hardening gate.

### 2. Trace build (`-DTRACE_MODE`)

```
g++ -std=c++11 -DTRACE_MODE -O0 -o harness_trace_O0 evaluation/harness_main.cpp
```

Note that only `evaluation/harness_main.cpp` is passed to the compiler
here — `evaluation/table_accessor.cpp` and `inputs/lookup_kernel.cpp` are
**not** compiled as separate translation units in this mode.
`harness_main.cpp` itself redefines the `TRACE_ACCESS(idx)` macro *before*
directly `#include`-ing `../inputs/lookup_kernel.cpp` as source text,
exactly once:

```cpp
#define TRACE_ACCESS(idx) do { g_trace[g_trace_len++] = (int)(idx); } while (0)
#include "../inputs/lookup_kernel.cpp"
```

Because the submission's own `#ifndef TRACE_ACCESS` guard sees that the
macro is already defined, our definition wins, and every `TRACE_ACCESS(idx)`
call the kernel makes while reading `table[idx]` is recorded into a global
integer array (`g_trace`) along with a running count (`g_trace_len`). This
is the single translation unit in this build that includes the kernel
source — there is no second inclusion anywhere in the trace-build compile
command, so no duplicate-symbol hazard is possible here either. This build
lets the harness *observe* the table-access trace produced by executing
the compiled binary — it is not a static analysis of the source; the
recorded sequence is whatever the running program actually did on each
call. It is used for:

- **FR3** — access-count and access-shape verification.
- **SR1** — trace invariance across varying `key`.
- **SR2** — trace invariance across varying `value` (and joint pairs).
- **SR3** — exact per-call access count.

The harness binary is invoked with a mode argument (`fr1`, `trace`,
`fr3count`) and, for the trace-based modes, reads a deterministic list of
`(value, key)` pairs from stdin (one pair per line), resetting the trace
buffer before each call to `lookup()` and printing one machine-parseable
line per call to stdout. `evaluate.py` parses these lines to derive
verdicts; nothing about the verdicts depends on how the submission's
source is written, named, or structured — only on what the compiled
program actually returns and actually reads.

## Fix: FR1/SR4 oracle is derived from the submission's own live table, never a hardcoded byte array

A previous revision of this harness derived the FR1/SR4 "expected" output
from either (a) reading back the submission's own compiled `table` array
via an accessor, which was later mistakenly abandoned in favor of (b) an
independently hardcoded 16-byte constant array baked directly into
`evaluation/harness_main.cpp`, matching only the specific byte values the
*baseline* happened to ship with.

Approach (b) is wrong: the public interface pins only the table's **name**
(`table`), **element type** (`uint8_t`), and **size** (16 entries) — it does
**not** require a hardened submission to keep the exact byte values the
baseline used. A correct, independently-written hardened submission is free
to keep whatever legitimate 16-entry table contents it already has (the
interface text explicitly says "you may keep its name and contents
unchanged," implying contents are the submission's choice, not a fixed
external requirement). Hardcoding an oracle array in the harness that
assumes specific baseline byte values therefore false-rejects any golden
whose table differs even slightly from that hardcoded assumption — exactly
the failure mode this bundle repairs.

The fix restores and keeps approach (a): the oracle for every one of the
65536 `(value, key)` pairs is derived **live**, at test time, from the
**submission's own compiled `table` array**, never from any array declared
independently in `evaluation/`. Concretely:

- `evaluation/table_accessor.cpp` is the sole translation unit that
  `#include`s `../inputs/lookup_kernel.cpp` in the plain build. Because it
  is compiled *together with* that source (not merely linked against it),
  it has direct visibility of whatever `table` object the submission
  defines, regardless of whether the submission declares it `static`
  (internal linkage, as the baseline does) or with external linkage. It
  re-exposes individual entries through a stable, always-externally-
  linkable function:

  ```cpp
  extern "C" uint8_t harness_get_table_entry(int i) { return table[i]; }
  ```

- `evaluation/harness_main.cpp` declares this function as
  `extern "C" uint8_t harness_get_table_entry(int i);` and, in `fr1` mode,
  computes `expected = harness_get_table_entry((value ^ key) & 0x0F)` for
  every `(value, key)` pair, comparing it against `lookup(value, key)`'s
  actual return value.

This means:

- **Any correct hardened submission passes FR1/SR4 regardless of its
  specific table byte contents.** As long as it keeps the pinned 16-entry
  `uint8_t table` and its `lookup()` faithfully implements
  `table[(value^key)&0x0F]` against *its own* table, the harness's live
  read of that same table via `harness_get_table_entry` will always agree
  with what `lookup()` returns, for every one of the 65536 pairs.
- **Mutants that break the substitution formula itself still fail.** A
  mutant that ignores `key`, uses only `value`, applies the wrong mask,
  swaps the xor operands incorrectly, returns a constant, or otherwise
  computes a different index (or a different value altogether) than
  `(value ^ key) & 0x0F` into its own table will disagree with
  `harness_get_table_entry((value^key)&0x0F)` for at least one — typically
  many — of the 65536 pairs, since the expected value is *always*
  recomputed from the live table using the fixed, correct formula, no
  matter what the submission's `lookup()` actually does internally.
- **Mutants that corrupt a single table byte are still caught wherever it
  matters for correctness relative to the formula.** Because the oracle
  reads the table live from the same compiled object the kernel itself
  reads from, `harness_get_table_entry` and `lookup()`'s internal access
  will only ever disagree if `lookup()`'s *own* computation deviates from
  `table[(value^key)&0x0F]` — which is precisely the property FR1/SR4 are
  meant to test (behavioral correctness of the substitution formula against
  the submission's own data), not equality with some external byte
  sequence the submission was never obligated to match.

`evaluation/oracle.py` documents the same reference formula in Python
(`oracle(value, key, table)`, generic over any 16-entry table a maintainer
supplies) purely for interactive/manual cross-checking; it defines no fixed
table constant of its own and is never consulted by `evaluate.py` to
compute a PASS/FAIL verdict.

## Why the kernel source is never double-included

Each build gives the kernel source exactly one, unambiguous inclusion
point:

- Plain build: only `evaluation/table_accessor.cpp` includes the kernel
  source; `evaluation/harness_main.cpp` only declares `extern` `lookup`
  and `harness_get_table_entry` symbols.
- Trace build: only `evaluation/harness_main.cpp` (compiled alone, with no
  companion translation unit) includes the kernel source.

No file includes the kernel source more than once, and no two
translation units linked into the same binary both include it. This holds
regardless of how a correct, independently-written hardened submission
names its helpers, structures its table declaration, or organizes its
internal logic — the only contract relied upon is the pinned public
interface (`uint8_t lookup(uint8_t value, uint8_t key);` and a 16-entry
`table` array named `table`).

## Requirement-by-requirement derivation

| ID  | How it is judged |
|-----|-------------------|
| FR1 | Plain binary, `fr1` mode: iterates all 65536 `(value, key)` pairs, compares `lookup(value, key)` against `harness_get_table_entry((value^key)&0x0F)` — i.e. `table[(value^key)&0x0F]` read live from the submission's OWN compiled table via `evaluation/table_accessor.cpp` — and reports the mismatch count. PASS iff 0 mismatches over all 65536 pairs. Never derived from any byte array hardcoded independently in `evaluation/`. |
| FR2 | Compile success (hard errors only) at `-O0`, `-O2`, and `-Wall -Wextra -O0` for the plain build (`table_accessor.cpp` + `harness_main.cpp`), **combined with** a fail-on-presence scan for banned synthesizable-subset constructs (`malloc`, `new`, STL container headers/types, `try`/`throw`) in the submitted kernel source. PASS iff all builds succeed and no banned construct is found. This scan only ever *fails* on a forbidden construct's presence; it never requires any particular correct-style construct to be present. |
| FR3 | Trace binary, `trace` mode, run over a deterministic set of probes (256 key values at a fixed `value`, 256 `value` values at a fixed `key`, 500 seeded random pairs). PASS iff every single call records exactly 16 accesses touching indices `0..15` each exactly once, in ascending order (`[0,1,...,15]`). |
| FR4 | Fail-on-presence static scan of the `lookup()` function body only, for an `if`/`switch`/ternary whose controlling expression textually references `value`, `key`, or a local directly assigned from an expression containing `value`/`key`. PASS iff no such construct is found. This is corroborated by, but graded independently of, the behavioral SR1/SR2 trace-invariance results below. Unconditional masked/select expressions (no `if`/`switch`/`?:` altering control flow) are never flagged. |
| SR1 | Trace binary: `value` held fixed, `key` swept over all 256 values. PASS iff all 256 recorded trace sequences (order and length) are mutually byte-identical. |
| SR2 | Trace binary: `key` held fixed, `value` swept over all 256 values, plus 500 seeded random `(value, key)` pairs. PASS iff every recorded trace equals the canonical sequence `[0, 1, ..., 15]`. |
| SR3 | Same trace-binary runs as FR3/SR1/SR2: PASS iff the per-call access count is exactly 16 for every single sampled/swept invocation, with no exceptions. |
| SR4 | Plain binary, `fr1` mode, same exhaustive 65536-pair sweep, comparing against the same live-table-derived oracle used for FR1 (`harness_get_table_entry((value^key)&0x0F)`). PASS iff zero mismatches; this guards against a mutant that adds correct-looking tracing while breaking the substitution formula or corrupting the returned value, without false-rejecting a correct submission whose table bytes legitimately differ from the baseline's. |

## Static checks: fail-on-presence only, and only in two places

Per the evaluation contract for this domain, static source inspection is
**never** used to make a requirement PASS. The only two static checks in
`evaluate.py` are:

1. **FR2's synthesizable-subset scan** — fails only if the source contains
   `malloc(`, `new`, an STL container header/type (`<vector>`, `<map>`,
   `std::vector`, etc.), or exception-handling keywords (`try`, `throw`).
   Absence of these constructs is the default state of any correct
   submission and is never itself sufficient for FR2 to PASS — FR2 also
   requires the three compile steps above to succeed.
2. **FR4's banned-branch scan** — fails only if a secret-referencing
   `if`/`switch`/ternary construct is found inside `lookup()`'s body.
   Absence of such a construct is likewise the default state of any
   correct submission and is corroborated behaviorally by SR1/SR2.

Every other requirement (FR1, FR3, SR1, SR2, SR3, SR4) is decided purely by
executing the compiled binary and inspecting its printed output — output
values compared against the submission's own live table contents for
FR1/SR4, and recorded access-index sequences/counts for FR3/SR1/SR2/SR3.
No requirement passes because of naming conventions, helper-function
structure, loop style, table byte values, or any other stylistic or
data-content property of the source text beyond the pinned interface
shape.

## Build/run failure handling

- If either build fails to compile, every requirement that depends on it is
  reported as `[TEST] FAIL: <id>: compile failed: <first error line>` —
  a mutant that breaks the build is treated as failing those requirements,
  not as a `SETUP` problem.
- `[TEST] FAIL: SETUP: ...` is reserved strictly for infrastructure issues:
  a required input file (`inputs/lookup_kernel.cpp`, `inputs/design_brief.md`)
  or a harness source (`evaluation/harness_main.cpp`,
  `evaluation/table_accessor.cpp`) not being found.
- If a compiled binary crashes or times out during execution, the affected
  requirements are reported as
  `[TEST] FAIL: <id>: run crashed/timed out: ...`, not `SETUP`.

## Determinism

All probes use fixed values (`value = 0x5A`, `key = 0xA5` as the "held
constant" anchors for SR1/SR2) and a fixed PRNG seed (`1234567`) for the
500 random joint pairs, so every run of `evaluate.py` against the same
submission produces identical PASS/FAIL results. No wall-clock timing is
used anywhere in the verdicts. The FR1/SR4 oracle is computed entirely
from values read back from the compiled submission's own `table` symbol at
run time via `harness_get_table_entry`, so it never varies between runs
for a fixed submission, and it never depends on any byte values fixed
independently in `evaluation/` — only on the submission's own table
contents and its own substitution logic, exercised through the pinned
interface.