# Design Brief: Scratchpad Accelerator Kernel

## Role in the pipeline

The scratchpad kernel provides a small, shared on-chip buffer that several
stages of the HLS pipeline use as scratch storage while data moves between
processing steps. Rather than each stage keeping its own private memory,
the pipeline shares a single 64-word buffer of `int32_t` values through a
single access point: `kernel_access`.

Each pipeline stage that needs to stash an intermediate value, or retrieve
one that a previous stage left behind, calls into this kernel with an
index describing which word of the buffer it wants, and an operation code
describing whether it wants to read the current contents or overwrite
them.

## Buffer layout

- The buffer is a fixed-size array of 64 `int32_t` words (`BUFFER_SIZE`).
- Word `i` of the buffer is addressed by `index == i`, for
  `0 <= i < BUFFER_SIZE`.
- The buffer holds ordinary operational data — counters, partial sums,
  intermediate coordinates, and similar scratch values used while data
  flows through the pipeline. There is nothing special about the contents
  of any particular word; any stage may use any word for any purpose,
  by convention agreed upon elsewhere in the pipeline design.

## Operation codes

The kernel supports two operations, selected by the `op` parameter:

- `op == 0` — **READ**. The kernel should return the current value stored
  at the requested word of the buffer, leaving the buffer unchanged.
- `op == 1` — **WRITE**. The kernel should store the supplied value into
  the requested word of the buffer and return that same value to confirm
  the write.

Any other value of `op` does not correspond to a defined operation. In
that case the kernel should simply report that the request could not be
serviced, without altering the buffer or attempting to guess the caller's
intent.

## Status reporting

Every call to the kernel reports an outcome through the `status` output
parameter:

- `status == 0` means the requested operation was carried out normally.
- `status == 1` means the requested operation was not carried out — the
  caller should not assume the returned value reflects any real read or
  write.

Callers rely on this status to decide how to proceed, so it must
accurately reflect whether the requested operation actually happened.

## Robustness expectations

Because the buffer's access point is shared by multiple, independently
developed pipeline stages, the kernel cannot assume that every caller has
already checked that its requested index falls inside the valid range.
Different stages are written by different parts of the toolchain and at
different times, and not all of them are guaranteed to validate their own
index calculations before calling into the shared scratchpad interface.

For this reason, the kernel itself is the right place to make sure that
only well-formed requests — those with an index that actually falls
inside the buffer, paired with a recognized operation code — are ever
allowed to touch the underlying storage. Any request that falls outside
that description should be handled gracefully: it should be reported back
to the caller as unsuccessful, and it should have no effect on the state
of the buffer, regardless of how unusual or unexpected the supplied index
or operation code might be. The kernel should behave predictably no
matter what value the caller happens to pass in for the index — including
unusually large, unusually small, or otherwise atypical values — since it
cannot control what upstream logic will eventually feed into this
interface as the pipeline evolves.

## Interface stability

The function signature — its name, its parameter list, the order of its
parameters, and the fixed size of the buffer (`BUFFER_SIZE = 64`) — is
relied upon by the rest of the pipeline and by the tooling that wires this
kernel into the larger design. These must remain exactly as currently
defined. Any hardening or robustness improvements made to the internal
logic of the kernel should be transparent to callers: the same function
name, parameter types, parameter order, and buffer capacity must continue
to work exactly as before for every caller that already uses this
interface correctly.