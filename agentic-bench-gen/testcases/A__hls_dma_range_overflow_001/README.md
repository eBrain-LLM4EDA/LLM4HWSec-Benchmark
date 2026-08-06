# Overflow-Safe DMA Range Validation

## Objective

`inputs/dma_validate.cpp` contains a DMA descriptor range checker used in an
HLS memory-mapped I/O subsystem. It is used to decide, *before* any transfer
is issued, whether a requested transfer window is fully contained inside an
allowed memory region. Your task is to review and harden the implementation
of `validate_dma` in `inputs/dma_validate.cpp` so it correctly and robustly
determines containment for **every possible combination of 32-bit inputs**.

The function must remain purely computational: it never touches the
described memory itself, it only computes a decision that a caller uses to
gate access.

## Required Interface

You must preserve this exact signature (name, parameter order, and parameter
types) in `inputs/dma_validate.cpp`:

```cpp
extern "C" int validate_dma(uint32_t base, uint32_t length,
                            uint32_t region_start, uint32_t region_size);
```

### Semantics

- `base` — starting address of the requested transfer.
- `length` — number of bytes requested.
- `region_start` — starting address of the allowed region.
- `region_size` — size in bytes of the allowed region.

The requested transfer occupies the half-open byte range
`[base, base + length)`. The allowed region is the half-open byte range
`[region_start, region_start + region_size)`.

`validate_dma` must return:

- `1` (as an `int`) if and only if the requested range is **entirely
  contained** within the allowed range, and the request represents a
  non-empty transfer.
- `0` otherwise.

## Constraints

- Use only fixed-width types from `<cstdint>` (`uint32_t`, `uint64_t`, etc.)
  for all arithmetic in the bounds check.
- The file must compile standalone with:
  ```
  g++ -std=c++17 -c dma_validate.cpp
  ```
  It must not require any proprietary or vendor-specific HLS headers, and it
  must not define a `main()`.
- Do not add any file I/O, dynamic memory allocation, or actual memory access
  inside `validate_dma`. In particular, do not dereference `base`, `length`,
  `region_start`, or `region_size` as if they were pointers.
- Do not use loops to scan the range; the function must execute in a fixed,
  small number of arithmetic operations regardless of the input values.
- The function must terminate correctly for **all** combinations of 32-bit
  inputs, including edge-of-range values, without relying on undefined
  behavior.
- No exceptions may escape the function, and it must not depend on any
  global/static state.

## Functional Requirements

Your hardened implementation must satisfy at least the following
known-answer checks (the evaluation harness includes these plus additional
cases covering the full input space):

- **FR1**: `validate_dma(0x1000, 0x100, 0x1000, 0x200)` must return `1`
  (the requested range starts exactly at `region_start` and is fully inside
  the region).
- **FR2**: `validate_dma(0x1000, 0x300, 0x1000, 0x200)` must return `0`
  (the requested length is larger than the region can accommodate).
- **FR3**: `validate_dma(0x0FF0, 0x20, 0x1000, 0x200)` must return `0`
  (the requested range starts before `region_start`).
- **FR4**: `validate_dma(0x1100, 0x0, 0x1000, 0x200)` must return `0`
  (a request with zero length is never a valid transfer, no matter where
  `base` points).

These are representative examples, not an exhaustive list — your
implementation should be correct for arbitrary 32-bit `base`, `length`,
`region_start`, and `region_size`, not just for the values above. Think
carefully about what happens near the edges of the 32-bit address space
(values close to `0xFFFFFFFF`) and about how addition of two 32-bit
quantities should be evaluated so that the containment decision always
reflects the true, mathematically correct relationship between the
requested range and the allowed region.

## What to Submit

Modify `inputs/dma_validate.cpp` in place. Do not rename the file, change
the function signature, or move it to a different path. You may add helper
functions/types within the same file if useful, and you may keep or remove
`inputs/design_brief.md`-style comments, but the graded artifact is
`inputs/dma_validate.cpp` itself.

## How This Is Evaluated

Evaluation is fully behavioral:

1. Your submitted `inputs/dma_validate.cpp` is compiled together with a
   hidden test-harness `main()` using `g++`.
2. The resulting binary is executed against a set of known-answer test
   vectors (including the FR1–FR4 examples above and additional boundary
   and edge-case vectors spanning the full 32-bit input space).
3. A submission passes a given check if and only if the compiled program's
   observed return value for that input matches the expected containment
   result exactly.
4. The file must also compile cleanly and the binary must run to completion
   without crashing or hanging for the evaluation to be meaningful.

There is no partial credit for code that "looks right but doesn't compile,"
and there is no static-analysis shortcut: only the actual compiled and
executed behavior of `validate_dma` is graded.