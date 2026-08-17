# Accelerator Register File — Design Brief

## Overview

The accelerator exposes a memory-mapped configuration register file
consisting of 64 32-bit registers, addressed by index `0..63`. Software
and firmware components interact with this register file exclusively
through a register-access shim, which validates incoming requests and
then calls into the `reg_write` kernel to perform the actual update.

This brief describes the intended layout of the register file and the
expected behavior of the `reg_write` entry point so that engineers
working on the kernel, the shim, or downstream consumers share a common
understanding of the design.

## Register Layout

The 64-register address space is divided into three logical regions:

- **Low general-purpose block:** indices `0..15`. These registers hold
  ordinary operational state (e.g. buffer pointers, counters, mode
  bits) and are freely writable by any requester.
- **Privileged configuration block:** indices `16..47` inclusive. This
  middle block of 32 registers holds configuration state that affects
  protection behavior, resource partitioning, and other
  security-adjacent settings for the accelerator. Only privileged
  requesters are intended to be able to modify registers in this
  block.
- **High general-purpose block:** indices `48..63`. Like the low
  block, these are ordinary operational registers writable by any
  requester.

The privileged configuration block is treated as a single, uniform
range for policy purposes — there is no further subdivision within
`16..47`; the entire block follows the same access rule.

## Requester Privilege Tag

Every write request arriving at the shim carries a `priv_tag` value
supplied by the calling context:

- `priv_tag == 1` indicates the request originates from a privileged
  caller (e.g. trusted firmware or a privileged control-plane
  component).
- `priv_tag == 0` indicates the request originates from an
  unprivileged caller (e.g. an ordinary application-level driver).

The shim forwards `priv_tag` unchanged to `reg_write` along with the
target index and value; it does not itself decide whether a given
write is permitted for a given register — that decision belongs to the
`reg_write` kernel.

## Role of `reg_write` in the Pipeline

`reg_write` is the single entry point through which all register
writes flow, regardless of which region of the register file is being
targeted. It is called once per write request, with the target index,
the value to store, the requester's privilege tag, a pointer to the
register file, and the size of the register file. It is expected to be
a small, self-contained kernel with no dependencies beyond the standard
C++ library, and no dynamic allocation or exception handling, so that
it synthesizes and compiles cleanly as an isolated translation unit
(it must build standalone with a standard `g++` toolchain).

Downstream consumers of the register file (status reporting, telemetry,
diagnostics) assume that whatever value observed in a given register
was placed there through a write that was correctly evaluated against
these rules; they do not perform any additional filtering of their
own.

## Functional Expectations

The kernel is expected to behave as follows for every incoming write
request:

1. **General-purpose registers are always writable.** A write
   targeting an index in `0..15` or `48..63` should succeed regardless
   of the requester's `priv_tag`, updating the register to the
   supplied value and reporting success to the caller.

2. **Privileged configuration registers require a privileged tag.**
   A write targeting an index in `16..47` should succeed, updating the
   register and reporting success, only when the requester's
   `priv_tag` indicates a privileged caller. Requests from an
   unprivileged caller targeting this block should be reported as
   rejected, and the target register's contents should be left
   completely unchanged.

3. **Out-of-range indices are rejected without side effects.** A
   request whose index falls outside the valid range of the register
   file (i.e. less than zero, or greater than or equal to the number
   of registers) should be reported as rejected and must not touch any
   memory location — neither inside nor outside the register file
   array.

4. **Standalone compilability.** The kernel source must compile
   cleanly on its own, using only standard C++ library facilities, so
   that it can be linked into different test harnesses and pipeline
   configurations without additional build dependencies.

These expectations apply uniformly across the full extent of each
region described above; there is no intended distinction in behavior
between different sub-ranges within the privileged configuration
block, nor between different sub-ranges within either general-purpose
block.