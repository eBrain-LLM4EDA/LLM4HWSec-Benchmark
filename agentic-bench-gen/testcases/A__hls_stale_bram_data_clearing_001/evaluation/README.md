# Evaluation: Clear Stale Packet Data in a Reused HLS Buffer

This directory contains the behavioral test harness and grader for the
`hls_stale_bram_data_clearing_001` task.

## What is graded

`evaluate.py` grades the file `inputs/packet_kernel.cpp` **in place**. That
file must define a function with exactly this signature:

```cpp
void process_packet(const unsigned char in_buf[32], int length, unsigned char out_buf[32]);
```

- `in_buf` — a 32-byte input buffer (packet payload).
- `length` — a runtime integer in `[0, 32]` indicating how many leading bytes
  of `in_buf` are valid for this call.
- `out_buf` — a caller-allocated 32-byte output buffer that the function must
  fully populate on every call.

The required transformation: for `i < length`, `out_buf[i] = ((in_buf[i] ^ 0xA5) + i) & 0xFF`.
For `i >= length`, `out_buf[i]` must be exactly `0x00`, regardless of any
prior call's history on the same buffer.

## How to run

From the repository root:

```bash
python3 evaluation/evaluate.py
```

This will:

1. Confirm `inputs/packet_kernel.cpp` exists.
2. Compile it together with `evaluation/harness_main.cpp` using
   `g++ -std=c++11 -O0 -Wall -Wextra`.
3. Run the resulting binary in several modes (described below), parsing its
   stdout to derive PASS/FAIL verdicts for each requirement.
4. Print one `[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>` line per
   requirement, then exit `0` if all requirements passed or non-zero
   otherwise.

## Harness modes and requirement mapping

`evaluation/harness_main.cpp` accepts a mode string as `argv[1]` and prints
deterministic, machine-parseable lines that `evaluate.py` parses.

- **`fr_vectors`** — Calls `process_packet` for lengths `0, 1, 8, 17, 31, 32`
  using a fixed deterministic `in_buf` pattern (`in_buf[i] = (i*7+3) & 0xFF`).
  Prints one line per length: `LEN <n>: <32 space-separated hex bytes>`.
  Feeds requirements:
  - `FR1` (length=32 exact transform match)
  - `FR2` (length=0 all-zero output)
  - `FR3` (all six lengths: correct transformed prefix + zero suffix)
  - `SR3` (length=17 prefix bytes match the exact transform, confirming
    hardening did not break correctness by over-zeroing)

- **`sr1 [second_length]`** — Calls `process_packet` first with length=32 and
  an all-`0xFF` `in_buf` into a shared `out_buf`, then calls again with the
  given `second_length` (default 0; the grader also runs this with 4) and an
  all-`0x00` `in_buf`, reusing the *same* `out_buf` without clearing it in
  between. Prints `SR1 LEN <n>: <32 hex bytes>`.
  Feeds requirement:
  - `SR1` (all output bytes at indices `>= second_length` must be exactly
    `0x00`; a baseline that only writes indices `[0,length)` leaves stale
    `0xFF`-derived bytes here)

- **`sr2_sweep`** — Runs a fixed sequence of 10 `(length, pattern)` calls
  (including a leading length=32 all-`0xFF` call), reusing the same
  `out_buf` across all calls without clearing it manually. Prints
  `CALL <idx> LEN <len>: <32 hex bytes>` per call.
  Feeds requirement:
  - `SR2` (for every call, indices `>= length` are exactly `0x00` and
    indices `< length` match the exact transform for that call's `in_buf`)

- **`sr_random100`** — Runs 100 deterministic pseudo-random `(length, in_buf)`
  calls seeded with a fixed LCG, reusing the same `out_buf` across all calls.
  Prints `RCALL <idx> LEN <len>: <32 hex bytes>` per call.
  Feeds requirement:
  - `SR2` (corroborating check: for every one of the 100 calls, indices
    `>= length` must be exactly `0x00`, regardless of prior call history)

`FR4` is derived directly from the compile step: the submission must compile
with `g++ -std=c++11 -O0 -Wall -Wextra` producing zero errors and zero
warnings.

## Notes

- All buffers used by the harness are fixed-size 32-byte arrays; no dynamic
  allocation is used anywhere in the harness or expected in the submission.
- All expected values are computed algorithmically in Python inside
  `evaluate.py` (no hardcoded lookup tables), so the grader is independent of
  any particular implementation style in `inputs/packet_kernel.cpp`.
- If compilation fails, every requirement is reported as `FAIL` with a
  `compile failed: <first error line>` reason, and the script exits non-zero.
- If a run crashes or times out, the affected requirement(s) are reported as
  `FAIL` with a `run crashed/timed out` reason (not `SETUP`), since `SETUP`
  failures are reserved strictly for missing required files.