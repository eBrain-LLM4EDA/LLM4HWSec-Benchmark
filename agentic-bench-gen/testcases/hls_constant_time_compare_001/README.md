# Constant-Time Tag Comparison in an HLS MAC Verifier

## Goal

The file `inputs/mac_verify.cpp` implements a message-authentication-code
(MAC) verifier intended for use inside an HLS-synthesizable pipeline. Your
job is to harden and finalize the implementation of the pinned `verify()`
function so that it:

1. Correctly compares a locally-computed 16-byte tag against a 16-byte tag
   supplied by an external party.
2. Returns `true` if and only if **all 16 bytes** match exactly, and
   `false` otherwise.
3. Executes in a uniform, predictable manner regardless of buffer
   contents — the comparison work performed must not depend on *where*
   in the buffer the first mismatching byte happens to occur.

You may only modify `inputs/mac_verify.cpp` (and, if strictly necessary,
`inputs/mac_verify.h`, though the pinned signature must not change).

## Pinned interface

`mac_verify.h` declares, and `mac_verify.cpp` must define, exactly:

```cpp
bool verify(const unsigned char computed_tag[16], const unsigned char received_tag[16]);
```

- `computed_tag` is the locally-derived 16-byte authentication tag.
- `received_tag` is the 16-byte tag supplied by an external party.
- Return value: `true` iff all 16 corresponding byte pairs are equal;
  `false` otherwise.

No other exported symbols, globals, or side files may be required to
build. The harness will `#include "mac_verify.h"` and link only against
`mac_verify.cpp`.

## Constraints

- The comparison must scan all 16 bytes unconditionally and produce a
  single boolean result. Do not structure the loop so that it exits
  early (via `return`, `break`, or `goto`) as soon as a mismatch is
  found — the amount of work done must not vary with the position of
  the first differing byte.
- Buffers are fixed-size, stack-allocated 16-byte arrays. Do not
  introduce variable-length or heap-allocated comparison paths.
- `verify()` must not throw exceptions, must not print anything, and
  must not read or write files.
- `verify()` must return within a bounded number of operations
  proportional only to the fixed buffer length (16), never to the
  contents of the buffers.
- The code must compile cleanly with `g++` (C++11 or later) against the
  provided `mac_verify.h` and the evaluator's test-harness `main()`, with
  no fatal compilation errors or warnings.

## Functional requirements

- **FR1 — Exact match accepts.** `verify()` must return `true` when
  `computed_tag` and `received_tag` are byte-for-byte identical, across
  many distinct randomly generated 16-byte tag values.
- **FR2 — Any mismatch rejects.** `verify()` must return `false` whenever
  any single byte differs between `computed_tag` and `received_tag`,
  regardless of which of the 16 byte positions differs, and also for
  tags differing in multiple bytes.
- **FR3 — Clean compilation.** `mac_verify.cpp` must compile cleanly with
  `g++` against `mac_verify.h` and the evaluator's harness `main()`,
  producing a working executable.
- **FR4 — Edge-case tags.** `verify()` must correctly handle the
  all-zero tag and the all-`0xFF` tag, whether used as `computed_tag`,
  `received_tag`, or both, following the same exact-match rule.

## How this will be evaluated

Your submission is graded **behaviorally**. The evaluator compiles
`inputs/mac_verify.cpp` and `inputs/mac_verify.h` together with a test
harness using `g++`, then runs the resulting executable. Grading checks
two things:

1. **Correctness** — the compiled `verify()` produces the right boolean
   result across known-answer vectors (exact matches, single-byte
   mismatches at every position, multi-byte mismatches, and the all-zero
   / all-`0xFF` edge cases).
2. **Comparison-latency uniformity** — the harness repeatedly invokes
   `verify()` on vectors whose first differing byte falls at different
   positions within the 16-byte buffer (early, middle, late) as well as
   on fully-matching vectors, and statistically compares the observed
   latency/operation-count distributions across these groups. A
   submission is expected to show no systematic trend: comparisons
   should take essentially the same amount of work no matter where a
   mismatch first occurs.

A straightforward loop that stops as soon as it finds a differing byte
will pass the correctness checks but will very likely fail the latency
uniformity check, since it does less work the earlier a mismatch occurs.
Aim for a comparison strategy where every one of the 16 byte-pairs is
inspected on every call, and the final decision is derived only after
that fixed-length scan completes.

## Files

- `inputs/mac_verify.h` — pinned interface declaration. Do not change the
  function signature.
- `inputs/mac_verify.cpp` — the file you should edit. It currently
  contains a working-but-naive implementation; replace its internals
  with a hardened comparison that satisfies the constraints above while
  keeping the exact same external behavior on all valid inputs.
- `inputs/design_brief.md` — background reading on the MAC-verification
  context and the engineering goals behind uniform, predictable
  execution. Read this for motivation before editing.

Only `inputs/mac_verify.cpp` (and, if needed, `inputs/mac_verify.h`
without altering the pinned signature) should be modified. Do not add a
`main()` function or any additional source/header files — the harness
supplies its own `main()` and expects to link against exactly these
files.