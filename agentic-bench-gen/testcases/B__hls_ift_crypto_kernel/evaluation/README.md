# Evaluation: `hls_ift_crypto_kernel`

This directory contains the behavioral evaluator for the `crypto_kernel` HLS
component. It grades the files you submit under `inputs/` **in place** —
there is nothing to copy or rename. The three files that matter are:

- `inputs/crypto_kernel.cpp`
- `inputs/crypto_kernel.h`
- `inputs/design_brief.md`

## What gets built

`evaluate.py` compiles your `inputs/crypto_kernel.cpp` together with a
harness we ship, `evaluation/harness_main.cpp`, using:

```
g++ -std=c++11 -O2 -Wall -Iinputs -o <tmpdir>/harness \
    inputs/crypto_kernel.cpp evaluation/harness_main.cpp
```

The `-Iinputs` flag means `evaluation/harness_main.cpp`'s
`#include "crypto_kernel.h"` resolves against your submitted header
regardless of where the harness file physically lives. Nothing is copied
into `inputs/`, and nothing under `inputs/` is modified.

The harness calls your implementation through exactly the pinned public
signature — no more, no less:

```c
void crypto_kernel(const unsigned char plaintext[16],
                    const unsigned char key[16],
                    unsigned char ciphertext[16],
                    unsigned char *status);
```

If your `crypto_kernel.cpp`/`crypto_kernel.h` do not expose this exact
signature (name, parameter types, parameter order, arity), the build will
fail to link/compile against the harness. That compile failure is itself
how the "signature must match the header prototype" requirement is
enforced — there is no separate text/AST inspection of your function
declaration.

## How grading works

Every requirement (FR1-FR4, SR1-SR4) is checked **behaviorally**: the
compiled binary is executed, its observable outputs are captured (via
plain hex/text files it writes, or, for the silent-output check, via the
raw stdout/stderr bytes of the process itself), and PASS/FAIL is derived
strictly from what was observed. Nothing about how you wrote your source
(helper function names, loop style, pointer-vs-array syntax, formatting)
is inspected to grant a PASS. The only place static source inspection
could ever appear is as a *fail-on-presence* check for a banned
construct (e.g. `malloc`, `new`, or recursion, which are disallowed by
the HLS-synthesizable-subset constraint) — such a check can only ever
cause a FAIL when the banned construct is found; it can never be the
reason a submission PASSes.

The harness binary supports several modes, invoked as:

```
./harness <mode> <infile> <outfile>
```

where `<infile>`/`<outfile>` are plain hex/text files (never stdout or
stderr), so any bytes the evaluator observes on the process's actual
stdout/stderr can only have come from your submitted `crypto_kernel.cpp`
itself, not from harness control/data plumbing:

- **`kat`** — runs a single fixed known-answer plaintext/key vector and
  writes the resulting ciphertext and status (as hex) to the output file.
  Used to probe FR1.
- **`random`** — reads a batch of plaintext/key pairs from the input
  file and writes one ciphertext/status line per pair to the output
  file. Different Python-generated vector sets (uniformly random pairs,
  edge-case keys, fixed-plaintext/many-key batches, etc.) are driven
  through this same mode to probe FR2, FR3, SR1, and SR3.
- **`timing`** — reads two groups of keys (against a shared fixed
  plaintext) and a repeat count, times many repeated invocations of your
  `crypto_kernel` per group using a monotonic clock, and reports the
  summed elapsed time per group. Used to probe SR2 (statistical
  independence of timing from key content).
- **`sr4_silent`** — runs a batch of plaintext/key pairs, writing all
  computed results only to the output file via `fopen`, and is coded to
  emit nothing itself on stdout/stderr in this mode. `evaluate.py`
  captures the subprocess's stdout and stderr directly; any non-empty
  bytes observed can only have originated from your `crypto_kernel`
  implementation. Used to probe SR4.

`evaluate.py` generates all test vectors, key distributions, repeat
counts, and tolerance values deterministically (fixed random seed, no
wall-clock dependence) so that every run of the evaluator against the
same submission produces the same verdicts. Exact vector counts and
numeric tolerances are intentionally not published in this document;
what is guaranteed is that they are fixed ahead of time and applied
identically to every submission.

## Requirements checked

| ID  | What is probed |
|-----|-----------------|
| FR1 | Known-answer vector: ciphertext = plaintext XOR key, status = 0x00. |
| FR2 | Many random plaintext/key pairs: ciphertext = plaintext XOR key for every byte, every pair. |
| FR3 | status = 0x00 for every tested plaintext/key pair, with no exceptions. |
| FR4 | Submission compiles cleanly (`g++ -std=c++11 -Wall`) and links against the pinned signature. |
| SR1 | With plaintext fixed and many distinct keys, status never varies (no key-dependent value reaches the public status output). |
| SR2 | With plaintext fixed, measured execution time does not statistically diverge between differing key distributions beyond a generous, pre-set tolerance. |
| SR3 | No output other than ciphertext depends on key content beyond the specified XOR combination; status and any other observed output never correlates with raw key bytes. |
| SR4 | No bytes are ever written to the process's stdout or stderr while `crypto_kernel` executes. |

## Build/run failure handling

- If the submission fails to compile against the harness, **every**
  requirement (FR1-FR4, SR1-SR4) is reported as `FAIL` with a
  `compile failed: ...` reason, and the evaluator exits non-zero. A
  broken build is treated as failing all behaviorally-graded
  requirements, not as a setup problem.
- If the harness binary crashes or times out during any probe, that
  specific requirement is reported as `FAIL` with a
  `run crashed/timed out` reason.
- `FAIL: SETUP: ...` is reserved strictly for missing required files
  (e.g. `inputs/crypto_kernel.cpp` not present) — it does not occur for
  compile or runtime problems with a present submission.

## Output format

Each requirement produces exactly one line:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <brief reason>
```

The evaluator exits `0` only if all eight requirement lines are `PASS`;
otherwise it exits non-zero.