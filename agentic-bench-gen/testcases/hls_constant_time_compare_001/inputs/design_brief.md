# Design Brief: MAC Tag Verification for an HLS Pipeline

## Background

This module is a small building block in a larger message-authentication
pipeline that is intended to be synthesized by a high-level synthesis
(HLS) toolchain into hardware. In this pipeline, an authentication tag
is derived locally from a message and a secret key using an upstream MAC
algorithm (not part of this module). Separately, a tag arrives from an
external party — over a network link, a bus interface, or some other
channel — claiming to authenticate the same message.

The job of `verify()` is simple to state: given these two 16-byte tags,
decide whether they are identical. If they are, the message is treated
as authentic; if not, it is rejected. Everything downstream of this
decision — whether a packet is accepted, whether a device unlocks,
whether a firmware image is trusted — depends on this single boolean
coming out right, every time, for every possible pair of 16-byte inputs.

## Why exact-match semantics matter

There is no partial credit in tag verification. A tag that matches in 15
of 16 bytes is exactly as invalid as a tag that matches in none. The
comparison exists purely to answer one yes/no question: are these two
fixed-size buffers, byte for byte, identical? Any implementation that
does not preserve this all-or-nothing semantics — for example, by
special-casing a `it looked plausible so let's simplify` outcome, no
matter how unlikely — would be functionally wrong.

Restating the required behavior in narrative form:

- If every one of the 16 bytes of the locally-computed tag matches the
  corresponding byte of the received tag, `verify()` must return `true`.
  This should hold for essentially any tag value you construct, not just
  a handful of special cases — the function needs to behave correctly
  across a wide variety of randomly chosen 16-byte tags.
- If even a single byte differs anywhere in the 16-byte buffer — first
  byte, last byte, or anywhere in between — `verify()` must return
  `false`. This must hold no matter which byte position the difference
  occurs at, and it must also hold when multiple bytes differ
  simultaneously.
- The code needs to build without drama: a plain `g++` compile against
  the provided header and a standard test harness, with no compiler
  errors and nothing that would reasonably be treated as a fatal
  warning.
- The function needs to be well-behaved on boundary-ish inputs too — the
  all-zero tag and the all-`0xFF` tag are common edge cases worth
  checking explicitly, whether they appear as the computed tag, the
  received tag, or both. The same exact-match rule applies to them as to
  any other tag value.

## Engineering goals beyond "does it return the right answer"

Because this code is meant to be portable into an HLS-synthesized
pipeline, it's worth thinking about more than just whether the boolean
result is correct on paper. A few general design goals are worth keeping
in mind while finishing this implementation:

- **Uniform, predictable execution regardless of buffer contents.** The
  amount of work `verify()` does — how many bytes it inspects, how many
  operations it performs, how it moves through the buffer — should not
  depend on *what values* happen to be sitting in `computed_tag` or
  `received_tag`. Two calls with wildly different tag contents should
  still look, structurally, like the same fixed amount of work.
- **Avoid structural shortcuts tied to where a mismatch occurs.** It's
  tempting to write a comparison that stops as soon as it notices two
  bytes don't match — that's the intuitive, minimal way to write a
  byte-comparison loop. For this module, prefer a comparison strategy
  that always inspects the full 16-byte buffer on every call, and only
  decides the final `true`/`false` outcome once that full, fixed-length
  pass over the data is complete. Think of the loop bound as fixed by
  the buffer size (16), not by anything discovered while examining the
  data.
- **Stick to fixed-size, stack-resident buffers.** Both tags are exactly
  16 bytes, always. There's no need for variable-length buffers, dynamic
  allocation, or pointer-plus-length variants of this interface — those
  add complexity and variability without adding value here. Keep the
  comparison logic simple and bounded to the fixed 16-byte case the
  interface already commits to.
- **Keep the function self-contained and side-effect free.** `verify()`
  should not throw exceptions, should not print any diagnostic output,
  and should not touch the filesystem. It's meant to be a pure function
  of its two input buffers, suitable for embedding in a synthesizable
  hardware description as well as a plain software build.

None of this changes *what* the function computes — the answer for any
given pair of tags is still just "are all 16 bytes equal?" It changes
*how uniformly and predictably* that answer gets computed, which matters
a great deal once this code is compiled down into a hardware pipeline
where consistent, well-bounded behavior across all inputs is a first-class
design requirement, not an afterthought.

## Interface reminder

The function signature is pinned and must not change:

```cpp
bool verify(const unsigned char computed_tag[16], const unsigned char received_tag[16]);
```

- `computed_tag`: the locally-derived 16-byte authentication tag.
- `received_tag`: the 16-byte tag supplied by the external party.
- Return value: `true` if and only if all 16 corresponding byte pairs are
  equal; `false` otherwise.

The declaration lives in `mac_verify.h`; the definition lives in
`mac_verify.cpp`. Only these two files should be modified. Do not
introduce a `main()` function, additional exported symbols, or extra
source files — the evaluation harness supplies its own entry point and
expects to build against exactly `mac_verify.cpp` and `mac_verify.h` as
provided.