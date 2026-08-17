# Descriptor Transfer — Evaluation Harness

This directory contains the behavioral evaluation harness for the
`hls_descriptor_double_fetch_001` task. It grades the submission located at
`inputs/descriptor_transfer.cpp` (paired with the unmodified
`inputs/descriptor_transfer.h`) **in place**.

## What gets graded

- `inputs/descriptor_transfer.h` — pinned interface (struct `Descriptor`,
  `extern "C" int run_transfer(Descriptor*, uint8_t*, uint32_t)`). Must not be
  modified by the submission.
- `inputs/descriptor_transfer.cpp` — the hardened implementation under test.

The harness includes `descriptor_transfer.h` via a bare `#include
"descriptor_transfer.h"` directive. The evaluator compiles with `-I inputs`
so this resolves to `inputs/descriptor_transfer.h` regardless of invocation
directory, and calls `run_transfer` exactly as pinned in the task's
`public_spec.interface`.

## How it works

1. `evaluate.py` first confirms `inputs/descriptor_transfer.h`,
   `inputs/descriptor_transfer.cpp`, and `evaluation/harness_main.cpp` all
   exist. If any is missing, it prints
   `[TEST] FAIL: SETUP: <file> not found` for the missing artifact and exits
   with a non-zero status.

2. It compiles the submission together with the harness driver
   (`evaluation/harness_main.cpp`) using:

   ```
   g++ -std=c++11 -O0 -pthread -I inputs -o <tmp>/harness_bin \
       inputs/descriptor_transfer.cpp evaluation/harness_main.cpp
   ```

   If compilation or linking fails, every requirement id (`FR1`-`FR4`,
   `SR1`-`SR3`) is reported as `[TEST] FAIL: <id>: compile failed: ...` with a
   concise excerpt of the compiler's stderr, and the script exits non-zero.
   (Successful compilation/linking is itself the behavioral evidence for
   `FR4`: any deviation in the `Descriptor` layout or the `run_transfer`
   signature would break the build.)

3. On successful build, `evaluate.py` runs the compiled harness binary
   multiple times, once per scenario, passing the scenario name as `argv[1]`:

   - `fr1` — length=32, max_len=256, deterministic data pattern. Expects
     `return == 32` and `dest[0..31]` equal to the pattern, with a guard
     region beyond byte 32 left untouched.
   - `fr2` — length=500, max_len=256, dest pre-filled with sentinel `0xAA`.
     Expects `return == -1` and `dest` completely unchanged.
   - `fr3` — length=0, max_len=256. Expects `return == 0` and `dest`
     unchanged.
   - `sr1_toctou` — runs 300 independent trials. In each trial the harness
     sets `desc.length = 200` (a large, valid value against `max_len = 256`,
     comfortably within `data`'s 256-byte capacity). It starts a mutator
     thread that spins on a shared `std::atomic<int> phase` (initialized to
     0) and, the instant it observes `phase == 1`, enters a tight bounded
     loop (a fixed, deterministic number of iterations — no wall-clock
     sleeps) repeatedly overwriting `desc.length` with `4096`. The harness
     sets `phase = 1` immediately before invoking `run_transfer` once, so the
     mutator's repeated-write burst races the single call and, critically,
     keeps writing throughout essentially the entire duration of that call
     rather than attempting a single one-shot write. The destination
     buffer's first 200 bytes are the validated transfer window; everything
     from byte 200 through a large observation window (4096+64 bytes) is
     pre-filled with a canary value (`0xEE`) and must remain untouched by a
     correct implementation regardless of how the race resolves.

     **Why 200 bytes / 300 trials, not 16 bytes / 200 trials:** an
     implementation that re-reads the shared field inside its copy loop
     (`for (uint32_t i = 0; i < desc->length; i++)`) performs one additional
     load *per iteration*. With a 16-iteration loop there are only 16
     opportunities for that re-read to observe the mutator's write, and the
     mutator previously attempted only a single write immediately after the
     phase flip — making detection a matter of scheduling luck. With a
     200-iteration loop and a mutator that keeps writing `4096` in a tight
     loop for the entire race window, the probability that at least one of
     those 200 re-reads observes the mutated value approaches certainty,
     while an implementation that reads `desc->length` exactly once into a
     local snapshot before looping is completely unaffected no matter how
     long the mutator keeps writing or how the OS schedules the two threads.
     Repeating this across 300 independent trials makes the discrimination
     deterministic in practice rather than a rare race win.

   Each scenario run prints one or more deterministic
   `RESULT:<scenario>:...` lines that `evaluate.py` parses to compute
   PASS/FAIL verdicts. The binary is run under a fixed timeout per
   invocation; a timeout or crash is reported as a failing behavioral probe
   (not `SETUP`).

4. `evaluate.py` maps scenario outcomes to requirement ids and prints exactly
   one line per requirement:

   - `[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>`

   Requirement-to-scenario mapping:

   | Requirement | Scenario(s)   | What is checked |
   |-------------|---------------|------------------|
   | FR1 | `fr1` | Correct 32-byte copy and return value |
   | FR2 | `fr2` | Rejection path: `-1` return, dest untouched |
   | FR3 | `fr3` | Zero-length valid transfer: `0` return, dest untouched |
   | FR4 | (compile/link) | Interface/struct fidelity, proven by successful build |
   | SR1 | `sr1_toctou` | `desc->length` effectively read once — no trial ever reflects the post-mutation value across all 300 races |
   | SR2 | `sr1_toctou` | Value validated == value used to bound the copy, in every trial |
   | SR3 | `fr2` | Rejection path never copies any bytes into `dest` |

5. The script exits `0` only if every requirement id passes; otherwise it
   exits `1`.

## Running locally

```
python3 evaluation/evaluate.py
```

Run this from the task root directory (the one containing both `inputs/` and
`evaluation/` as subdirectories). All paths used by `evaluate.py` are
resolved relative to the current working directory, and the compile command
adds `-I inputs` so the harness's include of `descriptor_transfer.h` works
without requiring the harness source itself to know the exact relative path
depth.

## Notes

- All test vectors and race parameters (trial count, buffer sizes, validated
  length, mutator loop bound, sentinel and canary values) are fixed and
  deterministic; no wall-clock-dependent logic (no `sleep`) is used anywhere
  in the harness or driver — the only synchronization primitive is an
  `std::atomic<int>` phase flag, and the mutator's persistence is achieved via
  a fixed iteration-bounded loop, not a timed delay.
- The harness never modifies files under `inputs/`; all compilation artifacts
  are written to a temporary directory that is cleaned up automatically.
- Only `g++`/`gcc` and the Python standard library are used; no network
  access is required or attempted.
- This design supersedes an earlier, narrower race (16-byte validated length,
  200 trials, single one-shot mutator write) that was found to have
  effectively zero probability of detecting the shipped insecure baseline in
  practice. The widened validated length, repeated-write mutator, and
  increased trial count close that gap without introducing any
  scheduling-dependent (i.e., non-reproducible) pass/fail outcome for a
  correct, single-read implementation.