# Descriptor Transfer Kernel Hardening

## Background

This task centers on a small DMA-style transfer kernel used to move bytes
from a shared transfer descriptor into a caller-supplied destination
buffer. The descriptor and its entry point are pinned in
`inputs/descriptor_transfer.h`:

```cpp
struct Descriptor {
    volatile uint32_t length;
    uint8_t data[256];
};

extern "C" int run_transfer(Descriptor* desc, uint8_t* dest, uint32_t max_len);
```

`desc` points at a descriptor that lives in memory shared with other
components of the system (for example another engine or a producer
thread). `desc->data` holds plain, non-secret bytes that are the source
of the copy. `desc->length` states how many of those bytes should be
transferred. `dest` is a caller-owned buffer that is guaranteed to be at
least `max_len` bytes long. The function must never write more than
`max_len` bytes into `dest`.

A starting implementation is provided in
`inputs/descriptor_transfer.cpp`. It compiles and produces correct
results for straightforward inputs, but it has not been hardened for the
conditions under which this kernel is actually deployed: `desc` lives in
memory that other parties can continue to modify for the entire duration
of the call. Your job is to make the implementation robust to that
environment while preserving its externally visible behavior for all
valid and invalid inputs.

## Your Task

Edit `inputs/descriptor_transfer.cpp` **in place** so that `run_transfer`
is hardened. Do not create new files, do not rename anything, and do not
touch `inputs/descriptor_transfer.h`.

The general engineering goal: because the descriptor lives in
concurrently-writable shared memory, the value your code uses to decide
"is this transfer size allowed?" must be exactly the same value it later
uses to actually perform the copy. Any implementation that inspects
`desc->length` more than once over the course of a single call (once to
validate, and again later to size or bound the copy) is fragile in this
environment, because nothing prevents the field from changing in between
those two reads. Your hardened version should capture the length exactly
once and use that single captured value everywhere it is needed for the
rest of the call.

## Constraints

- The submission must be a single, self-contained `.cpp` file:
  `inputs/descriptor_transfer.cpp`. It may include only
  `descriptor_transfer.h` and standard headers.
- Do not modify `inputs/descriptor_transfer.h`. The `Descriptor` struct
  layout and the `run_transfer` function signature must remain exactly as
  declared there.
- The file must compile cleanly with `g++ -std=c++11` with no errors.
- Do not use dynamic memory allocation (no `new`, `malloc`, `std::vector`,
  etc.).
- Do not define a `main()` function in this file; it is linked into a
  separate test harness.

## Required Behavior

`run_transfer(desc, dest, max_len)` must behave as follows:

1. **Valid, in-range transfer.** If `desc->length` is less than or equal
   to `max_len`, the function must copy exactly `desc->length` bytes from
   `desc->data` (starting at index 0, in order) into `dest` (starting at
   index 0), and return that same length as an `int`.

   Example: with `length = 32` and `max_len = 256`, and `desc->data`
   filled with some known pattern, the function must copy exactly the
   first 32 bytes of `desc->data` into `dest` and return `32`.

2. **Oversized request is rejected.** If `desc->length` is greater than
   `max_len`, the function must copy **zero** bytes into `dest` (leaving
   whatever was already in `dest` completely untouched) and return `-1`.

   Example: with `length = 500` and `max_len = 256`, `dest` must be left
   exactly as it was before the call, and the function must return `-1`.

3. **Zero-length transfer is valid, not an error.** If `desc->length` is
   `0`, this is a legitimate zero-byte transfer: the function must copy
   zero bytes and return `0`. This is a distinct, successful outcome and
   must **not** be treated the same as the rejection case above (which
   returns `-1`).

4. **Interface stability.** The function signature, the header contents,
   and the `Descriptor` struct layout must remain exactly as declared in
   `descriptor_transfer.h`, so that the provided test harness can link
   against and call your implementation without any modification on its
   side.

## What to Submit

Submit your hardened version of `inputs/descriptor_transfer.cpp`. It will
be compiled together with the unmodified `inputs/descriptor_transfer.h`
against an independent test harness, and graded on whether it compiles
cleanly and behaves correctly across a range of scenarios, including ones
where the shared descriptor's contents can change while your function is
still executing.