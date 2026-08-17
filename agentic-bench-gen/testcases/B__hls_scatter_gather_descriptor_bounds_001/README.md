# Scatter-Gather Descriptor Copy Engine

## Overview

This task asks you to implement a robust scatter-gather copy engine used to
reassemble data from a source buffer into a destination buffer according to
a list of descriptors. Each descriptor specifies where in the destination
buffer a chunk of data should land, and how many bytes of the source buffer
that chunk consumes. Descriptor lists may be produced by configuration data
that isn't fully trusted, so the function must always behave predictably —
returning a clear success/failure status — rather than crashing or leaving
the destination buffer in an inconsistent state.

Your job is to edit `inputs/scatter_gather.cpp` in place so that it copies
data correctly for every valid descriptor list, and safely rejects any
descriptor list that is malformed or would require writing/reading outside
the bounds of the supplied buffers, no matter how the invalid entry is
phrased (including at exact buffer boundaries and in combination with
otherwise-valid entries).

## Required Interface

You must implement exactly this function, with C linkage (no name
mangling), in `inputs/scatter_gather.cpp`:

```cpp
extern "C" int scatter_gather_copy(
    const unsigned char* src, unsigned int src_len,
    unsigned char* dst, unsigned int dst_len,
    const unsigned int* offsets, const unsigned int* lengths,
    unsigned int desc_count);
```

Do not change this signature. Do not add a `main()` function — your file
will be compiled together with a test harness that provides one.

### Parameter semantics

- `src` / `src_len`: the source buffer and its length in bytes. Read-only.
- `dst` / `dst_len`: the destination buffer and its length in bytes. The
  caller allocates and zero-fills this buffer before each call; your
  function writes into it.
- `offsets`: an array of `desc_count` values. `offsets[i]` is the byte
  offset into `dst` where descriptor `i`'s data should be written.
- `lengths`: an array of `desc_count` values. `lengths[i]` is the number of
  bytes descriptor `i` copies from `src`.
- `desc_count`: the number of descriptors (0 to 64 inclusive). The source
  data is consumed sequentially: descriptor 0 reads from `src` starting at
  offset 0, descriptor 1 continues from wherever descriptor 0 left off, and
  so on. Descriptor `i` writes its bytes into `dst` starting at
  `offsets[i]`.

### Return value

- Return `0` if every descriptor in the list is valid and the copy was
  performed successfully.
- Return any nonzero value if any descriptor in the list is invalid (for
  any reason — it doesn't matter which nonzero value you choose). When you
  return nonzero, `dst` must be left completely unmodified from whatever
  state it was in before the call (the harness zero-fills it, so on
  rejection it must still read as all zero bytes afterward).

## Functional Behavior You Must Preserve

- **Full in-order copy:** given a list of descriptors whose offsets and
  lengths partition the destination buffer exactly and in order, the
  function must copy the source data into the destination faithfully,
  byte for byte, and return `0`.
- **Multi-descriptor sequencing:** when multiple descriptors are present,
  the source bytes they consume must be contiguous and in the order the
  descriptors appear — descriptor `i+1` must pick up reading `src` exactly
  where descriptor `i` left off.
- **Standalone compilation:** the file must compile as a self-contained
  translation unit with only standard library includes, exposing
  `scatter_gather_copy` with C linkage so it can be called from a plain C
  test harness.
- **Empty descriptor list:** if `desc_count` is `0`, the function must
  return `0` immediately and must not write anything to `dst`, regardless
  of what `dst_len`, `offsets`, or `lengths` are (the latter two pointers
  may even be null in this case).

## Correctness Requirements

Your implementation must produce correct, safe behavior for **every**
possible combination of inputs the caller might supply, not just the
well-formed cases above. In particular:

- Every descriptor's destination placement must actually fit inside the
  destination buffer as described by `dst_len` — including descriptors
  that sit exactly at the edge of the buffer. Get the boundary arithmetic
  exactly right: a descriptor that fits perfectly up to the very last byte
  of the buffer is valid; a descriptor that would need even one byte more
  than the buffer holds is not.
- The total amount of data consumed from `src` across all descriptors must
  actually fit inside the source buffer as described by `src_len`.
- If **any single descriptor** in the list is invalid, the **entire batch**
  must be rejected — no bytes may be written to `dst` from any descriptor,
  including ones earlier in the list that looked fine on their own. Do not
  perform any writes until you are certain the whole list is acceptable.
- Your validation logic must hold up regardless of how large the offset
  and length values are, including values close to the maximum a 32-bit
  unsigned integer can hold. Make sure your bounds checks give the correct
  answer in every case, not just the common ones.
- The function must not stop checking after the first suspicious-looking
  entry and skip the rest of the list — every entry must be considered.
- The function must not modify `dst_len`, `src_len`, `offsets`, or
  `lengths`, and it must not rely on dynamic memory allocation.
- Behavior must be fully deterministic given the same inputs.

## Build Instructions

Your submission is compiled and linked against a test harness the
evaluator provides. You can sanity-check standalone compilation with:

```
g++ -std=c++17 -Wall -Wextra -c inputs/scatter_gather.cpp -o /tmp/scatter_gather.o
```

Your file must compile cleanly with this command (zero errors) and must
not define its own `main()`.

## What To Submit

Edit `inputs/scatter_gather.cpp` in place. Do not rename the file, change
its function signature, or move it. `inputs/design_brief.md` is provided
for additional context on the intended use case and is not something you
need to modify.

## Evaluation

Your submission will be exercised against a range of descriptor lists,
including well-formed ones and ones engineered to probe edge cases and
boundary conditions in your bounds checking. A correct, robust, and safe
implementation:

- Produces byte-exact destination contents and a success status for every
  valid descriptor list.
- Produces a nonzero status and leaves the destination buffer completely
  unmodified for every descriptor list containing at least one invalid
  entry, no matter how that invalidity is expressed.