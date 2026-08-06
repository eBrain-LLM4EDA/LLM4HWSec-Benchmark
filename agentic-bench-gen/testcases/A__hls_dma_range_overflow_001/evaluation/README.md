# Evaluation: Overflow-safe DMA range validation

## What this grader does

`evaluate.py` behaviorally grades `inputs/dma_validate.cpp` against the
pinned interface:

```
extern "C" int validate_dma(uint32_t base, uint32_t length,
                             uint32_t region_start, uint32_t region_size);
```

It never inspects the submission's source text. Correctness of
`validate_dma` is fully determined by its observable input/output
behavior at this interface, so every requirement (FR1-FR4, SR1-SR4) is
checked by compiling and running the code, never by pattern-matching
how it is written.

## Steps performed by `evaluate.py`

1. **Presence check.** Confirms `inputs/dma_validate.cpp` and
   `inputs/design_brief.md` exist. If either is missing, every
   requirement is reported as `[TEST] FAIL: SETUP: <file> not found`
   and the script exits 1.

2. **Compile.** Builds the submission together with the harness driver
   using:

   ```
   g++ -std=c++17 -O0 -o <tmpdir>/harness inputs/dma_validate.cpp evaluation/harness_main.cpp
   ```

   with a 60-second timeout. If compilation fails, every requirement
   id (FR1-FR4, SR1-SR4) is reported as
   `[TEST] FAIL: <id>: compile failed: <first stderr line>` and the
   script exits 1. This ensures a broken/mutated submission that fails
   to build is correctly counted as failing every requirement rather
   than being skipped.

3. **Run vectors.** `evaluation/harness_main.cpp` is a thin CLI wrapper:
   it takes `base`, `length`, `region_start`, `region_size` as decimal
   command-line arguments, calls `validate_dma`, and prints the integer
   return value on stdout. For each requirement id, `evaluate.py` spawns
   one subprocess invocation per test vector (with a 5-second timeout
   per run) and parses the single printed integer as the observed
   result.

4. **Ground truth.** For each vector, the expected result is computed in
   Python using **exact, unbounded integer arithmetic** (Python `int` has
   no fixed width, so there is no wraparound in the reference
   computation itself):

   ```python
   def ground_truth(base, length, region_start, region_size):
       if length == 0:
           return 0
       if base < region_start:
           return 0
       if base + length > region_start + region_size:
           return 0
       return 1
   ```

   This is the half-open-interval containment predicate from the task
   specification: `[base, base+length)` must be non-empty and fully
   contained within `[region_start, region_start+region_size)`.

5. **Compare and report.** For each requirement id, every associated
   vector's observed value is compared to the Python-computed expected
   value. A requirement is reported `[TEST] PASS: <id>` only if all of
   its vectors match; otherwise it is reported
   `[TEST] FAIL: <id>: <first mismatching vector and values>`. A crash
   or timeout on any vector for a requirement is also reported as a
   failure for that requirement (not as a `SETUP` failure, since the
   build already succeeded).

6. **Exit code.** The script exits `0` only if all eight requirements
   (FR1-FR4, SR1-SR4) print `[TEST] PASS`; otherwise it exits `1`.

## Requirement coverage

- **FR1-FR4**: fixed known-answer vectors taken directly from the
  public functional requirements (full containment at region start,
  length exceeding region size, base before region start, zero-length
  rejection).
- **SR1**: vectors where the true (unbounded) `base + length` exceeds
  `UINT32_MAX`; a fail-closed implementation must return 0 even though a
  naive 32-bit-only adder would wrap.
- **SR2**: vectors specifically constructed so that `base + length`
  overflows 32-bit arithmetic and wraps to a value that is spuriously
  `<= region_start + region_size` under naive `uint32_t` addition, while
  the true unbounded end address lies outside the region.
- **SR3**: zero-length vectors across multiple base/region alignments,
  including `base == region_start`, all of which must be rejected
  unconditionally.
- **SR4**: partial-containment vectors (base before region start with
  end inside; end exceeding region bound; and cases where
  `region_start + region_size` itself overflows 32 bits), each checked
  against the exact Python containment verdict rather than an assumed
  fixed expected value.

## Why no static source inspection is used

Every requirement here is observable purely through the function's
return value on well-chosen inputs — there is no timing, side-channel,
or code-shape property in this task that execution cannot capture.
Because of this, `evaluate.py` contains no fail-on-presence or
pass-on-presence static pattern checks: a correct hardened
implementation may use any internal representation (widened 64-bit
arithmetic, saturating checks, reordered comparisons, differently named
helpers, etc.) as long as it produces the mathematically correct
containment decision for every vector, and this grader will accept it.

## Running standalone

```
python3 evaluation/evaluate.py
```

Requires `g++` supporting `-std=c++17` to be available on `PATH`.