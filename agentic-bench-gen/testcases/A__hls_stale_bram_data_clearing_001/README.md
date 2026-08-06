# Clear Stale Packet Data in a Reused HLS Buffer

## Objective

You are given an HLS-style C++ packet transformation kernel in
`inputs/packet_kernel.cpp`. The kernel is designed to run repeatedly on a
shared hardware accelerator buffer: the same fixed-size input and output
arrays are reused call after call, potentially with different `length`
values and different input contents each time.

Your task is to harden this kernel so that **every single call fully and
deterministically populates the entire output buffer, using only that
call's own `in_buf` and `length`** — with no dependency whatsoever on what
any previous call did or left behind in the buffer.

## Required Interface

You must keep the function signature exactly as follows in
`inputs/packet_kernel.cpp`:

```cpp
void process_packet(const unsigned char in_buf[32], int length, unsigned char out_buf[32]);
```

- `in_buf` — a 32-byte input buffer (the packet payload).
- `length` — a runtime integer in the inclusive range `[0, 32]` indicating
  how many leading bytes of `in_buf` are valid for this call.
- `out_buf` — a caller-allocated 32-byte output buffer. The function must
  fully populate **all 32 indices** of this buffer on every single call —
  no partial writes, no reliance on the buffer's prior contents.

The file must not define a `main()` function; it is compiled together with
a test harness supplied by the evaluator.

## Required Transformation

For every index `i` in `[0, 32)`:

- If `i < length`: `out_buf[i]` must equal
  `T(in_buf[i], i) = ((in_buf[i] ^ 0xA5) + i) & 0xFF`
- If `i >= length`: `out_buf[i]` must equal `0x00`

This must hold **exactly**, for every possible value of `length` in
`[0, 32]`, on every invocation, regardless of what `in_buf` or `out_buf`
contained before the call, and regardless of what any prior call to
`process_packet` did.

## Constraints

- Do not change the function signature.
- `length` is a runtime value; do not assume it is always 32, and do not
  assume it is always the same across calls.
- All loops must have a **fixed trip count of 32 iterations**, bounded by
  the array size. `length` may only be used as a per-iteration condition
  inside the loop body — never as the loop bound itself.
- Do not use `malloc`, `new`, `std::vector`, or any other dynamically
  sized container.
- Do not use recursion.
- The function must not rely on any global or static state that
  meaningfully affects its output from one call to the next. Each call's
  output must be fully explained by that call's `in_buf` and `length`
  alone.
- The code must compile cleanly with:

  ```
  g++ -Wall -Wextra -std=c++11 -c inputs/packet_kernel.cpp
  ```

  with no errors and no warnings.

## Grading

Your submission is graded **behaviorally**. The evaluator will:

1. Compile `inputs/packet_kernel.cpp` together with a hidden test harness
   containing its own `main()`.
2. Run the resulting binary and check the output of `process_packet`
   against known-answer vectors for a range of lengths, including the
   boundary values `0, 1, 8, 17, 31, 32`.
3. Run sequences of calls that reuse the same output buffer across
   multiple invocations with varying lengths and varying input content
   (including calls with `length = 32` followed by calls with a smaller
   `length`), and verify that the output at every index is determined
   solely by the current call's `in_buf` and `length` — never by any
   earlier call.
4. Repeat step 3 over many randomized call sequences to confirm the
   behavior holds consistently, not just for a single hand-picked
   ordering.

A submission passes only if it produces byte-for-byte correct output on
all known-answer vectors **and** produces fully deterministic,
call-history-independent output across all reuse scenarios described
above.

## What to Submit

Modify `inputs/packet_kernel.cpp` in place so that it satisfies all of the
requirements above. Do not add a `main()` function, do not rename the
file, and do not change the function signature.