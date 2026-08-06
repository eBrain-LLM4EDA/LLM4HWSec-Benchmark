# Fixed-Pattern Lookup Kernel

## Task

You are given a small HLS-style C++ kernel in `inputs/lookup_kernel.cpp` that
implements a substitution-style lookup used in a synthesizable pipeline
stage. The kernel combines a public input byte `value` with a byte `key`
and returns a byte from a fixed 16-entry table.

Your job is to **harden the kernel** so it satisfies two things at once:

1. **Same behavior.** For every possible `value` (0..255) and `key`
   (0..255), `lookup(value, key)` must return exactly
   `table[(value ^ key) & 0x0F]`.
2. **Uniform memory access.** The pattern of table reads performed by
   `lookup()` — which entries of `table` are touched, in what order, and
   how many times — must be the *same on every single call*, regardless
   of what `value` or `key` are. In other words, looking only at the
   sequence of table indices accessed (not the return value), an observer
   should not be able to tell anything about the inputs.

You must edit `inputs/lookup_kernel.cpp` in place. Do not create new files
or rename the function.

## Interface (must not change)

```cpp
uint8_t lookup(uint8_t value, uint8_t key);
```

- `value` — a public input byte.
- `key` — an input byte.
- Return value — the substituted output byte.
- `table` — a fixed 16-entry `uint8_t` array already declared in the file.
  Keep its name, its size (16), and its contents exactly as provided.

## Constraints

- Keep the exact function signature `uint8_t lookup(uint8_t value, uint8_t key)`.
  Do not add parameters, overloads, or rename it.
- Keep `table` as a 16-entry `uint8_t` array with its existing contents
  unchanged.
- Only fixed-trip-count `for` loops are allowed (loop bounds must be
  compile-time constants, e.g. `for (int i = 0; i < 16; i++)`). No
  `while` loops whose condition depends on `value` or `key`, and no loop
  bound derived from either of them.
- No dynamic memory allocation (`new`, `malloc`, etc.), no STL containers
  or iterators, no recursion, and no exceptions anywhere in the kernel
  body.
- No control-flow branch (`if`/`else`, ternary `?:`, or `switch`) whose
  condition depends on `value`, `key`, or any value derived from them.
  The sequence of operations the function performs must be identical for
  every input.
- The file provides a macro `TRACE_ACCESS(idx)`. Every time your code
  reads an element of `table`, it must call `TRACE_ACCESS(idx)` exactly
  once, passing the literal integer index (0..15) being read — this lets
  the test harness observe which table entries were touched. Do not call
  `TRACE_ACCESS` for indices you don't actually read from `table`.
- The header already includes a default no-op definition of
  `TRACE_ACCESS` so the file compiles standalone even without the test
  harness defining it.

## What "uniform access" means in practice

A correct hardened version reads through the whole table on every call —
touching all 16 entries, in the same fixed order, the same number of
times — and combines the results in a way that produces the correct
answer without ever using `value` or `key` to pick which single address
gets dereferenced. Think in terms of "scan and select" rather than
"compute an address and jump to it directly."

## How this will be evaluated

Your submitted `inputs/lookup_kernel.cpp` will be compiled standalone
with `g++` at both `-O0` and `-O2` against a harness the graders provide.
It must compile cleanly with no warnings treated as errors.

The harness does two kinds of checks:

1. **Functional check.** It calls `lookup(value, key)` for a large sweep
   of `(value, key)` pairs and compares the result against a reference
   implementation computed independently by the evaluator. All outputs
   must match exactly — there is no published table of expected values
   here; correctness is determined by re-executing the algorithm
   described above on the actual inputs.
2. **Access-pattern check.** A second, instrumented build defines
   `TRACE_ACCESS(idx)` to append `idx` to a log. The harness runs
   `lookup()` across many different `(value, key)` combinations and
   inspects the recorded sequence of accessed indices for each call. It
   requires that this sequence be the same length and same order on
   every single call, no matter what `value` or `key` was used.

Both checks must pass for the submission to be accepted. A version that
returns correct results but reads the table using a value- or
key-dependent shortcut (for example, computing an index and reading only
that one entry) will fail the access-pattern check even though its
outputs are correct.

## Files

- `inputs/lookup_kernel.cpp` — the kernel you must harden. Edit this file
  in place.
- `inputs/design_brief.md` — background context on how this block is
  used, for reference only.

## Submission

Submit your modified `inputs/lookup_kernel.cpp`. No other files are
required.