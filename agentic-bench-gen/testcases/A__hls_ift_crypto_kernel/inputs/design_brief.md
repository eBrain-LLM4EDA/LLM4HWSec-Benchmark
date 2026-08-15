# Design Brief: `crypto_kernel` Block Component

## Overview

`crypto_kernel` is a small, self-contained block-processing component
intended for use inside a larger embedded data-path pipeline. It is
designed to be synthesized through a high-level synthesis (HLS) flow and
integrated as a fixed-function hardware/software co-simulation block. This
brief describes its role, expected data flow, and the synthesis-oriented
constraints it must respect. It complements `README.md` (task instructions)
and `crypto_kernel.h` (the fixed interface).

## Role in the System

The component sits on a data path that repeatedly processes fixed-size
16-byte blocks. Upstream logic supplies a 16-byte plaintext block and a
16-byte key block on every invocation; `crypto_kernel` combines them into a
16-byte ciphertext block and reports a single status byte indicating that
the fixed-size operation ran to completion. Downstream logic consumes the
ciphertext buffer and inspects the status byte before advancing the
pipeline.

## Intended Data Flow

At a high level, the intended data flow for each invocation is:

```
plaintext[0..15] ---\
                      >---  byte-wise XOR  --->  ciphertext[0..15]
key[0..15]       ---/

(plaintext, key) --- fixed-size block op --->  status  (completion code)
```

Each output byte of the ciphertext buffer is produced by combining the
corresponding plaintext and key bytes at the same index. The status byte is
produced once per invocation and reflects that the fixed-size, 16-byte
block operation completed as expected.

## Engineering Expectations

- **Determinism.** For a given plaintext/key pair, the component must
  always produce the same ciphertext and the same status byte. The block
  operation has a fixed size (16 bytes) and a single well-defined outcome;
  there is no variable-length processing and no error condition intrinsic
  to correctly-sized inputs.
- **HLS synthesizability.** The implementation must use only fixed-size
  arrays and constructs that map cleanly onto an HLS toolchain: no dynamic
  memory allocation, no STL containers, no recursion, and no unbounded
  loops. Loop bounds and array sizes should be fixed at 16 throughout.
- **Single co-simulation entry point.** `crypto_kernel` is invoked as a
  leaf function inside a synthesized co-simulation harness. It must not
  define a `main()` of its own, and it must not perform any console or
  file I/O (no `printf`, `fprintf`, logging, or similar side effects). In
  an HLS/co-simulation context, any such output is not meaningful hardware
  behavior and can interfere with how the surrounding toolchain drives and
  observes the block — the function's only observable effects should be
  through its output parameters (`ciphertext` and `status`).
- **Stable resource usage.** Because the component will eventually be
  mapped onto fixed hardware resources, its internal control flow and
  memory access pattern should be simple and predictable across
  invocations, consistent with a fixed-size, fixed-latency block operation
  rather than a data-dependent one.

## Summary

`crypto_kernel` is a small, fixed-size, side-effect-free block combiner:
16 bytes of plaintext and 16 bytes of key go in, 16 bytes of ciphertext and
one status byte come out, and — given the same inputs — the component
should behave the same way every time it runs.