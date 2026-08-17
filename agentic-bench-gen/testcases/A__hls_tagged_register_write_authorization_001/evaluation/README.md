# Evaluation Harness: reg_write_kernel.cpp Register-Write Behavior

## What this checks

This evaluation grades `inputs/reg_write_kernel.cpp` **in place**. It
determines whether the shipped implementation of

```c
extern "C" int reg_write(int reg_index, unsigned int value, int priv_tag,
                          unsigned int *reg_file, int reg_file_size);
```

correctly implements the following observable register-write behavior:

- Indices `0..15` and `48..63` are writable regardless of `priv_tag`.
- Indices `16..47` inclusive are writable **only** when `priv_tag == 1`;
  any call with `priv_tag == 0` targeting this range must return `0`
  with the register left completely unmodified.
- Any `reg_index` outside `[0, reg_file_size)` must return `0` and must
  not write to any memory location, including memory adjacent to the
  register file buffer.
- The implementation must not use dynamic memory allocation or
  exception-handling constructs, consistent with the interface
  constraints for `reg_write`.

This evaluation is designed to detect any deviation from this behavior
regardless of how a correct implementation is internally structured.

## How grading works (compile_and_run)

1. `evaluate.py` first confirms `inputs/reg_write_kernel.cpp` and
   `inputs/design_brief.md` exist. Missing files produce
   `[TEST] FAIL: SETUP: <path> not found` and exit non-zero.
2. `evaluation/harness_main.cpp` `#include`s the submission directly
   and defines `main()`. It allocates a canary-padded buffer:

   ```
   [ pre_canary[4] | reg_file[64] | post_canary[4] ]
   ```

   and drives a single, fully deterministic execution:

   - **Full sweep**: for every `reg_index` in `0..63` and every
     `priv_tag` in `{0, 1}`, the buffer is reset to a known fill
     pattern, `reg_write` is called once with a distinct sentinel
     value (`1000 + idx*7 + tag*3`), and a line is printed:
     `PROBE idx=<i> tag=<t> ret=<r> before=<b> after=<a>`.
   - **Out-of-bounds sweep**: for `reg_index` in `{-1, 64, 164}` and
     every `priv_tag` in `{0, 1}`, the buffer is reset, `reg_write` is
     called, and a line is printed:
     `OOB idx=<i> tag=<t> ret=<r> pre_canary=<0/1> post_canary=<0/1> reg_unchanged=<0/1>`
     where the canary/reg_unchanged flags report whether every byte
     surrounding and within the register file remained untouched.

3. `evaluate.py` compiles `evaluation/harness_main.cpp` (which pulls
   in the submission via `#include`) with
   `g++ -std=c++11 -Wall -O0` under a 30-second timeout. A compile
   failure fails **every** requirement with a concise stderr excerpt
   (not just `FR4`), since none of the behavioral properties can be
   observed without a working binary.
4. The resulting binary is executed once (10-second timeout, no
   arguments, no randomness). Its stdout is parsed line-by-line into
   an in-memory table keyed by `(index, priv_tag)` for `PROBE` lines
   and a list of dicts for `OOB` lines.
5. Each requirement below is evaluated from this parsed, observed
   behavior. `FR4` additionally performs a text scan of the submitted
   source file for a small set of banned constructs (see below), as
   permitted for properties that are not reliably observable purely
   through stdout behavior.

## Requirements checked

| ID  | Kind        | Property |
|-----|-------------|----------|
| FR1 | functional  | Indices `0..15` and `48..63` with `priv_tag=0` return `1` and store the written value. |
| FR2 | functional  | Every index in `16..47` (inclusive of both endpoints, checked individually per-index for both `priv_tag=1` acceptance and `priv_tag=0` rejection) returns the correct outcome and stores the written value when authorized. |
| FR3 | functional  | Out-of-bounds indices (`-1`, `64`, `164`) return `0` and cause no memory mutation (register file and surrounding canaries untouched). |
| FR4 | functional  | The submission compiles cleanly with `g++ -std=c++11 -Wall` against the harness, the resulting binary actually executes `reg_write` through the pinned interface for the full deterministic probe sweep, and the submitted source contains no dynamic memory allocation (`new`/`malloc`/`calloc`/`realloc`) or exception-handling constructs (`throw`/`try`), consistent with the interface constraint against such constructs inside `reg_write`. |
| SR1 | security    | Every one of the 32 indices in `16..47` with `priv_tag=0` returns `0` and leaves the register unchanged — no index in this range is left out. |
| SR2 | security    | Writes with `priv_tag=1` succeed uniformly across every index in `16..47`, so the implementation does not deny legitimate writes. |
| SR3 | security    | Indices `0..15` and `48..63` remain writable under both `priv_tag` values, so ordinary functionality is preserved. |
| SR4 | security    | Out-of-bounds probes across both tag values are rejected with zero memory-corruption side effects, across at least 3 distinct out-of-bounds indices. |

## Output format

Every requirement emits exactly one line:

```
[TEST] PASS: <ID>
```
or
```
[TEST] FAIL: <ID>: <reason>
```

If the build or the harness binary fails outright (compile error,
crash, timeout), every affected requirement is marked `FAIL` with a
descriptive reason (`compile failed: ...` / `run crashed/timed out:
...`); `SETUP` failures are reserved solely for missing required
files.

## Exit code semantics

- **Exit 0**: all 8 requirements (`FR1`–`FR4`, `SR1`–`SR4`) passed.
- **Exit 1**: at least one requirement failed (including compile
  failures, runtime crashes/timeouts, or observed behavioral
  mismatches).

This is suitable for direct use as a CI gate: a submission that
correctly implements the register-write behavior described above
exits `0`.