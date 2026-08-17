# Design Brief: Packet Assembly Kernel

## Purpose

This kernel is a small building block inside a larger HLS packet-processing
pipeline. Upstream stages parse an incoming packet into two logical parts —
a header region and a payload region — each described by a length field.
This kernel's job is to concatenate those two regions into a single
contiguous destination buffer that downstream stages can consume without
needing to know that the data originally arrived in two separate pieces.

## Interface summary

The kernel operates on the following fixed-width fields, matching the
public interface in `packet_assemble.h`:

- `header`, `header_len` — the header bytes and their count.
- `payload`, `payload_len` — the payload bytes and their count.
- `dest`, `dest_capacity` — the destination buffer and its declared
  capacity.

Both `header_len` and `payload_len` are 16-bit unsigned quantities
(`unsigned short`), each independently ranging from `0` up to `65535`.
`dest_capacity` is likewise a 16-bit unsigned quantity describing how many
bytes of storage the caller has made available at `dest`.

## Capacity check semantics

Before any bytes are copied, the kernel must decide whether the combined
length of the header and payload actually fits inside the destination
buffer:

- If the combined length of `header_len` and `payload_len` exceeds
  `dest_capacity`, the kernel must reject the request outright — no bytes
  are written to `dest`, and the caller is informed that assembly failed.
- Otherwise, the kernel copies the header bytes followed immediately by the
  payload bytes into `dest`, and reports back exactly how many bytes were
  written (which equals the combined length).

This check exists precisely so that the destination buffer's declared
capacity is never treated as a suggestion — it is a hard upper bound that
the copy step must respect in every case.

## Buffer layout notes

`dest` is always caller-provided and is guaranteed by the caller to have
storage for at least `dest_capacity` bytes — no more, no less can be
assumed. The kernel does not own this buffer, does not resize it, and does
not allocate any buffer of its own; it only writes into the space it has
been given. The expected layout after a successful call is simply:

```
dest[0 .. header_len-1]                  = header bytes, in order
dest[header_len .. header_len+payload_len-1] = payload bytes, in order
```

with nothing written beyond that range, and nothing written at all if the
capacity check fails.

## Robustness goal

Because `header_len`, `payload_len`, and `dest_capacity` are independently
chosen 16-bit fields, the kernel needs to behave correctly across the
*entire* representable range of these values — not just for the small,
everyday packet sizes seen in typical test traffic. In particular, the
kernel must remain correct when `header_len` and `payload_len` are both
large, close to the top of the 16-bit range, since their combined length
in that regime can be substantially larger than either field alone might
suggest.

The kernel must behave correctly across the full range of representable
header/payload lengths, including large values near the 16-bit limit,
without corrupting adjacent memory. Any implementation of this capacity
check and copy step should be reviewed with this full input range in mind,
rather than only the common small-packet case, since HLS pipelines built
on top of this kernel rely on its bounds being trustworthy under all
inputs it might realistically be asked to handle.