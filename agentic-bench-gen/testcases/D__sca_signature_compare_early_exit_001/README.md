# Signature Comparator Characterization Task

## Overview

This task asks you to analyze the cycle-level behavior of a byte-serial
signature comparator implemented in Verilog, and to produce a structured
report describing its internal control flow, its timing behavior as a
function of the input data, and a concrete remediation for any
data-dependent timing variation you find, while preserving correct
match/mismatch results.

The module under test is `signature_compare`, provided in
`inputs/signature_compare.v`. It compares two 16-byte signatures
(`expected` vs. `received`) that are streamed into the module one byte
pair per cycle, and reports a match/mismatch verdict once all necessary
bytes have been consumed.

## Module Interface

Module: `signature_compare` (see `inputs/signature_compare.v`)

| Port | Direction | Width | Description |
|---|---|---|---|
| `clk` | input | 1 | Clock. |
| `rst_n` | input | 1 | Active-low synchronous reset. When low, all internal state and outputs clear on the next posedge `clk`. |
| `start` | input | 1 | Pulse high for exactly 1 cycle to begin a new comparison. Clears `done`/`match` and resets internal counters. |
| `expected_byte` | input | 8 | Current byte of the expected signature. |
| `received_byte` | input | 8 | Current byte of the received signature, sampled the same cycle as `expected_byte`. |
| `byte_valid` | input | 1 | Asserted alongside each new byte pair. The module consumes exactly one byte pair per cycle while `byte_valid` is high. The signature length is fixed at 16 bytes, supplied sequentially starting the cycle after `start`. |
| `done` | output reg | 1 | Moore output. Asserted synchronously and held high starting the cycle after the module has consumed the bytes it needs to determine a verdict. Stays high until the next `start` pulse clears it. |
| `match` | output reg | 1 | Valid and stable only while `done=1`. `1` if all 16 byte pairs were equal, else `0`. |

See `inputs/design_brief.md` for additional context on how this module
is intended to be used and its expected external behavior.

`inputs/testbench_harness.v` is a self-contained iverilog/vvp testbench
that exercises the module against 17 representative cases: a full
16-byte match, and a mismatch injected at each of the 16 byte positions
(0 through 15). It prints, for each case, a description and the number
of cycles elapsed from the cycle after `start` until `done` first
asserts. This harness is provided **for your own reference and optional
cross-checking only** (e.g. via `iverilog -g2012` and `vvp`) — it is
not itself graded, and you do not need to run it to complete the task,
though doing so may help you characterize the module's behavior
precisely.

## Your Task

Analyze `inputs/signature_compare.v` (and, if useful,
`inputs/design_brief.md` and simulation results from
`inputs/testbench_harness.v`) to characterize:

1. What internal signal or condition controls exactly when `done` is
   asserted relative to how many bytes have been consumed.
2. How the number of cycles elapsed before `done` asserts relates to
   the position of the first differing byte between `expected` and
   `received` (if any), across all 16 possible mismatch positions and
   the full-match case.
3. A concrete, code-level change to the module that would make the
   number of cycles until `done` asserts independent of the input data
   (i.e. the same for every mismatch position and the full-match case),
   while still producing correct match/mismatch verdicts in every case.

Report your findings as a single JSON object.

## Required Output

Write your answer to:

```
submission/vulnerability_report.json
```

Do not modify anything under `inputs/`. Your only deliverable is the
JSON file above.

The JSON object must contain exactly the following top-level fields:

- **`early_exit_signal`** (string): The exact Verilog identifier (or an
  unambiguous functional description referencing the same signal) of
  the internal signal/condition in `signature_compare.v` that governs
  when `done` is asserted relative to bytes consumed.

- **`cycle_relationship`** (string): A precise, quantitative
  description or formula relating the number of cycles elapsed before
  `done` asserts to the position of the first mismatching byte (e.g.
  of the form `cycles_to_done = k + C` where `k` is the 0-indexed
  position of the first mismatching byte and `C` is a constant),
  including the value for the full-match case. Express this using
  explicit integers or arithmetic relationships — not vague qualitative
  language such as "it varies" or "roughly proportional".

- **`constant_time_fix`** (string): A concrete description of the
  specific code-level change(s) needed so that the cycle count before
  `done` asserts no longer depends on the input data, while match and
  mismatch verdicts remain correct for every input.

- **`baseline_behavior`** (object) with two string fields, each valued
  `"match"` or `"mismatch"`:
  - **`full_match_verdict`**: the verdict produced when all 16 bytes
    are equal.
  - **`mismatch_at_zero_verdict`**: the verdict produced when only byte
    position 0 differs.

- **`proposed_fix_preserves_correctness`** (boolean): `true` if, in
  your analysis, applying your proposed fix would still produce
  correct match/mismatch verdicts for all 16 possible mismatch
  positions and the full-match case; `false` otherwise.

All fields are required and must be non-empty / correctly typed. The
file must be valid JSON containing exactly this structure (additional
fields are permitted but the ones above are mandatory and are what
will be checked).

## Constraints

- Do not edit `inputs/signature_compare.v` or
  `inputs/testbench_harness.v`. These are reference artifacts only.
- Your submission must be pure JSON/descriptive text — no executable
  code.
- All timing/cycle claims must be stated precisely (explicit integers
  or arithmetic relationships), not qualitative approximations.

## Getting Started

A placeholder file already exists at
`submission/vulnerability_report.json` with the required field names
but uninformative placeholder values. Replace its contents with your
actual analysis before submitting.