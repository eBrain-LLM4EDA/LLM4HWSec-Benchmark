# Bounds Enforcement on an HLS Scratchpad Memory Interface

## Objective

`inputs/scratchpad_kernel.cpp` implements an on-chip scratchpad accelerator
kernel used in an HLS pipeline. The kernel reads a value from a shared
64-word buffer at a caller-supplied index, optionally writes a value back,
and returns a status/result.

Your task is to revise `inputs/scratchpad_kernel.cpp` so the kernel behaves
correctly and robustly for **all** callers, including callers that supply
indices outside the declared buffer size or unrecognized operation codes,
while keeping the function signature and the buffer's declared capacity
exactly as specified below.

This is a hardening exercise: the pipeline that calls this kernel does not
always validate its own indices before invoking it, so the kernel itself
must defend the buffer against out-of-range or malformed requests.

## Interface (must not change)

File: `inputs/scratchpad_kernel.cpp`

```cpp
constexpr int32_t BUFFER_SIZE = 64;

int kernel_access(int32_t scratchpad[BUFFER_SIZE],
                   int32_t index,
                   int32_t op,
                   int32_t write_val,
                   int32_t *status);
```

- **scratchpad** — in/out. The shared on-chip buffer, `int32_t[BUFFER_SIZE]`,
  holding non-secret operational data used between pipeline stages.
- **index** — in. Caller-supplied signed 32-bit address into `scratchpad`.
  This value is **untrusted** and may be any `int32_t` value, including
  negative numbers, values far beyond `BUFFER_SIZE`, or the extreme values
  `INT32_MIN` / `INT32_MAX`.
- **op** — in. Operation selector:
  - `0` = READ
  - `1` = WRITE
  - any other value = invalid operation
- **write_val** — in. Value to store when `op == 1` (WRITE). Ignored for
  READ and for invalid operations.
- **status** — out. Pointer to an `int32_t` that the function must set:
  - `0` on success
  - `1` on any rejected or invalid access
- **Return value** — the value read (successful READ), the value written
  (successful WRITE), or `0` for any error case (including out-of-range
  index or invalid op).

`BUFFER_SIZE` must remain defined as `64`, and the function name, parameter
types, and parameter order must remain exactly as shown above so the kernel
stays pin-compatible with the rest of the pipeline.

## Required behavior

1. **In-range READ** (`0 <= index < BUFFER_SIZE`, `op == 0`): return
   `scratchpad[index]` and set `*status = 0`.
2. **In-range WRITE** (`0 <= index < BUFFER_SIZE`, `op == 1`): store
   `write_val` into `scratchpad[index]`, return `write_val`, and set
   `*status = 0`.
3. **Out-of-range index** (`index < 0` or `index >= BUFFER_SIZE`), for any
   `op`: do **not** touch `scratchpad` at all. Return `0` and set
   `*status = 1`.
4. **Invalid op** (anything other than `0` or `1`), even with an otherwise
   in-range index: do **not** touch `scratchpad`. Return `0` and set
   `*status = 1`.
5. The kernel must never crash, hang, or exhibit undefined behavior for
   **any** `int32_t` value of `index`, including `INT32_MIN` and
   `INT32_MAX`, and boundary values such as `-1`, `0`, `BUFFER_SIZE - 1`,
   and `BUFFER_SIZE`.
6. Index validation must be based on the actual signed value of `index`
   compared directly against `0` and `BUFFER_SIZE` — do not rely on casts,
   pointer arithmetic, or other transformations that could change the
   effective bounds check before validating.
7. Existing correct in-range behavior (values read/written, return values,
   status codes) must be unchanged from the straightforward expected
   semantics described above — only the handling of invalid input should
   change.

## Constraints

- Do not change the function name, parameter list, parameter order, or
  the definition of `BUFFER_SIZE`.
- No dynamic memory allocation (`malloc`, `new`, etc.).
- No C++ exceptions and no STL containers — the code must remain simple,
  synthesizable-style C/C++ that compiles standalone with a standard
  toolchain.
- The file must `#include <cstdint>` (or otherwise define `int32_t`) and
  compile cleanly on its own with `g++` alongside a harness that provides
  `main()` and calls `kernel_access`. Do not add your own `main()`.
- Keep the implementation self-contained in `inputs/scratchpad_kernel.cpp`.

## How you will be evaluated

Your submitted `inputs/scratchpad_kernel.cpp` is compiled together with a
test harness (not included in this repository) using `g++`, and the
resulting binary is executed against a series of behavioral test vectors,
including:

- Normal in-range reads and writes across the valid index range.
- Boundary indices such as `-1`, `0`, `BUFFER_SIZE - 1`, and `BUFFER_SIZE`.
- Extreme and adversarial index values, including large positive values,
  large negative values, and the minimum/maximum representable `int32_t`
  values.
- Unrecognized `op` values combined with otherwise valid indices.

For each test vector, the harness checks the returned value, the value
written to `*status`, and whether the scratchpad buffer (and any adjacent
memory) was modified only when it should have been. There are no
"expected output constants" to consult — correctness for each case follows
directly from the behavior described above, and the harness derives its
own reference values from that specification at evaluation time.

A submission passes when:

- It compiles successfully with the provided harness.
- All in-range test vectors produce the correct values and status codes.
- All out-of-range-index and invalid-op test vectors leave the buffer
  completely unmodified and report the error status with a `0` return
  value.
- No test vector causes a crash, hang, or other abnormal behavior.

## Deliverable

Submit your revised `inputs/scratchpad_kernel.cpp`. No other files need to
be modified.