# Privilege-Tag Enforcement on Accelerator Register Writes

## Overview

This task asks you to harden the register-write entry point of an HLS
accelerator so that it enforces consistent, uniform access control across
its entire protected register range.

The accelerator exposes a 64-register configuration file (`reg_file`,
indices `0..63`). A sub-range of that file, indices `16` through `47`
inclusive, is reserved for privileged configuration state. Writes to this
range should only be honored when the caller presents a privileged tag.
All other registers are general-purpose and should remain writable by any
caller.

The current implementation in `inputs/reg_write_kernel.cpp` has a gap in
its protection logic: it does not apply the privilege check uniformly
across the whole protected range. Your job is to fix this so that
enforcement is complete and consistent across all 32 protected indices,
without breaking the behavior of unprotected registers or the
out-of-bounds handling.

## What You Need To Do

Edit `inputs/reg_write_kernel.cpp` in place so that it satisfies the
functional requirements below. You must **not**:

- change the function name, signature, parameter order, or return type,
- change the `extern "C"` linkage,
- rename the file,
- introduce dynamic memory allocation or exceptions inside `reg_write`,
- add a `main()` function (a separate test harness will provide one and
  link against your file).

## Required Interface

The file must define exactly this function:

```cpp
extern "C" int reg_write(int reg_index, unsigned int value, int priv_tag,
                          unsigned int *reg_file, int reg_file_size);
```

Parameters:

- `reg_index` — the target register index. Valid range is `0 .. reg_file_size - 1`.
- `value` — the 32-bit value to write.
- `priv_tag` — the requester's privilege tag. `1` means the caller is
  privileged; `0` means the caller is unprivileged.
- `reg_file` — pointer to the register file array, of length
  `reg_file_size`, that the function may mutate.
- `reg_file_size` — number of registers in `reg_file`. The harness will
  supply `64`.

Return value:

- Return `1` if the write was performed (i.e. `reg_file[reg_index]` was
  set to `value`).
- Return `0` if the write was rejected (i.e. `reg_file[reg_index]` was
  left unchanged).

## Functional Requirements

1. **Unprotected indices always writable.** For any `reg_index` in
   `0..15` or `48..63`, calling `reg_write` with any `priv_tag` value
   (`0` or `1`) and any `value` must return `1` and result in
   `reg_file[reg_index] == value`.

2. **Protected indices writable when privileged.** For any `reg_index`
   in the protected range `16..47` (inclusive of both ends), calling
   `reg_write` with `priv_tag == 1` must return `1` and result in
   `reg_file[reg_index] == value`.

3. **Protected indices must reject unprivileged writes, uniformly.**
   For any `reg_index` in `16..47`, calling `reg_write` with
   `priv_tag != 1` must return `0`, and `reg_file[reg_index]` must be
   left unchanged. This must hold for **every** index in the protected
   range — the enforcement must not stop partway through the range or
   only cover a sub-window of it. Ensure the check is applied
   consistently across the full boundary, not just part of it.

4. **Out-of-bounds indices are always rejected.** Calling `reg_write`
   with `reg_index < 0` or `reg_index >= reg_file_size` must return `0`
   and must not modify any element of `reg_file` (no out-of-bounds
   memory access under any `priv_tag` value).

## Constraints

- The register file always has exactly 64 32-bit registers, indices
  `0..63`.
- The protected range is fixed at indices `16` through `47` inclusive.
  This range must be treated as a single, uniform region — every index
  in it follows the same rule.
- The function's name, signature, `extern "C"` linkage, and the file
  name `reg_write_kernel.cpp` must not change.
- The implementation must be self-contained, depending only on the
  standard C++ library (no external headers or libraries beyond that).
- Do not use dynamic memory allocation (`new`/`malloc`) or exceptions
  (`throw`/`try`/`catch`) inside `reg_write`.
- The file must compile cleanly with `g++ -std=c++11 -Wall` as a
  standalone translation unit when compiled together with a test
  harness that provides `main()`.

## How You Will Be Evaluated

Your submission is graded **behaviorally**. The evaluator compiles
`inputs/reg_write_kernel.cpp` together with a test harness (which you do
not see in advance) using `g++ -std=c++11 -Wall`, links the result into
an executable, and runs it. The harness exercises `reg_write` across:

- every register index in the file, under both `priv_tag` values, and
- several out-of-bounds `reg_index` probes, under both `priv_tag`
  values,

checking both the return value and the resulting contents of
`reg_file` (including that memory outside the array is untouched).

A correct, hardened submission must:

- accept writes from privileged callers (`priv_tag == 1`) everywhere in
  the protected range `16..47`,
- reject writes from unprivileged callers (`priv_tag == 0`, or any
  value other than `1`) everywhere in the protected range `16..47`,
  with no exceptions,
- always accept writes to unprotected indices (`0..15`, `48..63`)
  regardless of `priv_tag`,
- always reject out-of-bounds `reg_index` values without writing to
  memory, and
- compile without errors as described above.

## Deliverable

Submit the modified `inputs/reg_write_kernel.cpp` (edited in place). No
other files are required.