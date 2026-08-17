# Design Brief: AES-128 Block Cipher Kernel

## Purpose

This document describes the intended data flow of the block cipher
kernel implemented in `cipher_kernel.cpp`, and gives general engineering
guidance for hardening its resource usage. It is a functional/design
note, not a specification of a particular vulnerability class — treat it
as ordinary code-quality guidance for an HLS-style kernel that may run in
a shared execution environment.

## Interface

The kernel exposes exactly one entry point, fixed by `cipher_kernel.h`
and not to be modified:

```c
void encrypt_block(const unsigned char key[16],
                    const unsigned char plaintext[16],
                    unsigned char ciphertext[16]);
```

- `key` — 16 bytes, the secret key used to derive the round-key
  schedule.
- `plaintext` — 16 bytes, the block to be encrypted.
- `ciphertext` — 16-byte output buffer, allocated by the caller; the
  kernel writes its result here.

## Data Flow

1. **Key expansion.** The 16-byte input key is expanded into a full
   11-round key schedule (11 round keys of 16 bytes each, 176 bytes
   total) using the standard substitution/rotation/round-constant
   expansion process. This schedule is stored in a local, stack-resident
   working array. For this kernel, that array must be named exactly
   `round_keys` and declared as `unsigned char round_keys[176]` — a
   plain automatic array, never dynamically allocated, static, or
   global. Downstream tooling that inspects this kernel's memory
   behavior locates this array by that exact name and size, so the
   declaration must match precisely.

2. **State initialization.** The 16-byte plaintext block is copied into
   a local working "state" buffer.

3. **Round processing.** The state undergoes the standard round
   transformation sequence combining substitution, row shifting, column
   mixing, and combination with the appropriate slice of the round-key
   schedule, repeated for the required number of rounds (with the final
   round omitting the column-mixing step), consuming successive 16-byte
   slices of `round_keys` as it proceeds.

4. **Output.** Once round processing completes, the resulting state is
   copied byte-for-byte into the caller-supplied `ciphertext` buffer.
   The function then returns.

## Resource-Sharing Considerations

This kernel is intended to run in a resource-constrained,
time-multiplexed execution environment (e.g. an HLS accelerator or
embedded context) where on-chip memory and/or stack scratch space is
reused across many successive, logically unrelated invocations — not
just repeated calls to this same kernel, but potentially entirely
different computations scheduled onto the same physical storage
afterward.

As a matter of general engineering hygiene in this kind of environment,
any local scratch buffer that only exists to hold *intermediate*
computation state — and is not the function's actual output — should not
be left populated with that intermediate data once the function is done
with it. Concretely for this kernel: `round_keys` is working state used
only to drive the round transformations; it is not itself an output.
Once the last round has consumed it, its contents no longer serve any
purpose to this call, and leaving them sitting in reused stack space
after return is undesirable from a robustness standpoint, independent of
any specific threat scenario.

**Practical implication:** before `encrypt_block` returns, on its one
and only return path, the full 176 bytes of `round_keys` should be
overwritten with zero.

## A Note on Optimization

Be aware that straightforward attempts at this kind of buffer clearing
can be silently undone by an optimizing compiler. If a clearing
operation (for example, a call to `memset` on the buffer) is placed
right before the function returns and the buffer is never read again
afterward, an optimizer may correctly determine that the write has no
observable effect on the program's result and eliminate it entirely as
a "dead store" — especially at `-O2` and above. The buffer would then
end up unchanged from how it looked mid-computation, despite the source
code appearing to clear it.

To be effective in practice, the clearing operation needs to be written
in a way the compiler cannot reason away as pointless — for example, by
performing the overwrite through a pointer that has been qualified
`volatile`, so that each write is treated as an observable side effect
the compiler must preserve regardless of whether the memory is read
again. Other equivalent techniques that achieve the same "the compiler
cannot elide this write" property are also acceptable.

Whatever technique is used, it must be scoped narrowly to the clearing
operation itself. Broadly disabling optimization for the whole file or
function is not an appropriate way to achieve this and defeats the
purpose of building an efficient kernel.

## Correctness Constraints

Any hardening applied to this kernel must satisfy the following, without
exception:

- The computed ciphertext written into the caller's `ciphertext` buffer
  must be byte-for-byte identical to what the unmodified round-based
  encryption logic produces, for every key/plaintext input, including
  degenerate cases such as an all-zero key paired with an all-zero
  plaintext.
- This must hold identically whether the kernel is built with `-O0`,
  `-O2`, or `-O3`. Functional behavior must never depend on the chosen
  optimization level.
- The clearing behavior itself must also hold at every one of those
  optimization levels — it is only useful if it actually survives
  compilation, not just in an unoptimized build.
- There is a single success path through `encrypt_block`; that path must
  perform the clearing step unconditionally before returning. No
  shortcut or early exit should bypass it.