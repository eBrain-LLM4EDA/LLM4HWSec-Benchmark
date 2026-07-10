# Evaluation: Bounds Enforcement on the Scratchpad Kernel

## What is graded

`evaluate.py` grades `inputs/scratchpad_kernel.cpp` **in place**. It does
not read or trust any comments, helper-function names, or coding style
in that file — it grades observed runtime behavior only.

The grading process:

1. Compile `inputs/scratchpad_kernel.cpp` together with a harness
   (`evaluation/private/harness_main.cpp`) using `g++`. If compilation
   fails, every requirement is reported as failed with the first
   compiler error line.
2. Run the resulting binary once per test case, each invocation in its
   own isolated subprocess with a timeout. Each invocation:
   - re-initializes a contiguous memory region containing the
     scratchpad buffer plus adjacent guard/canary words on both sides,
   - captures the full memory region *before* the call,
   - invokes `kernel_access` with a chosen `(index, op, write_val)`,
   - captures the full memory region *after* the call,
   - prints the observed `status`, return value, and before/after
     memory dump.
3. Compare the observed `status`, return value, and memory state
   against the behavior required by the task specification. No part of
   the verdict depends on how the source code is written — only on
   what the compiled binary actually does when run.

A crash, hang, or timeout on any probe is treated as a failure of the
requirement(s) that probe exercises, not as a setup error.

## Interface that must remain unchanged

The submission must keep the exact function signature, parameter order,
and buffer capacity:

```
int kernel_access(int32_t scratchpad[64], int32_t index, int32_t op,
                   int32_t write_val, int32_t *status);
```

- `BUFFER_SIZE` must remain `64`.
- `op == 0` means READ, `op == 1` means WRITE.
- `status` is an output parameter: `0` on success, `1` on any rejected
  or invalid access.
- Return value: the value read (successful READ), the value written
  (successful WRITE), or `0` for any error case.

Any change to the function name, parameter types/order, or buffer size
will cause the harness compilation or linkage to fail, which is scored
as a failure of every behaviorally-graded requirement.

## Required behavior

- For any `index` in `[0, 64)` with `op == 0`, the kernel must return
  the current value stored at `scratchpad[index]` and report
  `status == 0`, without modifying the buffer.
- For any `index` in `[0, 64)` with `op == 1`, the kernel must store
  `write_val` into `scratchpad[index]`, return `write_val`, report
  `status == 0`, and must not modify any other word of the buffer or
  of adjacent memory.
- For any `index` outside `[0, 64)` — including negative values, values
  far beyond the buffer's capacity, and the extreme representable
  32-bit signed values — the kernel must **not** touch the scratchpad
  buffer in any way. It must report `status == 1`, return `0`, and
  leave the entire buffer and all adjacent memory byte-for-byte
  unchanged.
- Any `op` value other than `0` or `1` must be treated the same way as
  an invalid access: `status == 1`, return `0`, no modification to the
  buffer or adjacent memory, regardless of whether `index` itself would
  otherwise have been in range.
- No index value, however unusual, may cause a crash, hang, undefined
  behavior, or any read/write outside the declared buffer. This must
  hold even for values that might trick a naive bounds check via
  overflow, underflow, casting, or pointer-arithmetic tricks.

## What is *not* disclosed here

The exact set of index, operation, and write values used to probe the
submission (including which boundary and extreme values are tested) is
kept private and is not enumerated in this document. Submissions should
satisfy the general behavioral requirements above for *all* possible
`int32_t` index and `op` values, not just a known set of probes.