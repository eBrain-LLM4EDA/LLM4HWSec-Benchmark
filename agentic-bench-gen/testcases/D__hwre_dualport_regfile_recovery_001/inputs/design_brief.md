# Design Brief: Small Dual-Read Storage Block

## Background

This document describes a small storage block that was originally
part of a larger design. During a synthesis pass, the block (along
with everything around it) was flattened into primitive gates, and
the word-level structure — how many entries the block held, how its
write and read ports related in time, and what its address decoding
looked like — was lost in the process. What remains is a gate-level
netlist and a thin wrapper around it. This brief captures what is
known about the block's intended behavior from documentation notes
and observation of the netlist's I/O, so that a clean word-level
replacement can be produced.

## What the block is

The block is a small, fixed-size storage array: four entries, each
eight bits wide. It has one write port and two independent read
ports. It is the kind of small local scratchpad you might find
feeding two consumers that each need to read a (possibly different)
entry in the same cycle, while a separate producer occasionally
writes a new value into one of the four slots.

There is nothing exotic about its size or interface — four
addressable locations, a byte each, one writer, two readers — but the
exact *timing relationship* between the write port and the two read
ports matters a great deal to how it can be safely reused in a larger
design, which is why it is documented carefully here.

## Write behavior

The block has a single write path, qualified by a write-enable
signal and a two-bit address selecting which of the four entries is
being targeted. Writes are clocked: on a rising clock edge where the
write enable is asserted, the entry selected by the write address
takes on the new data value presented at that edge. Only one entry
is ever updated per qualifying edge — the other three entries retain
whatever they held previously. If the write enable is not asserted on
a given edge, no entry changes.

## Reset behavior

The block has a synchronous, active-high reset. While reset is
asserted at a rising clock edge, all four entries are cleared to zero
on that edge, regardless of what the write-enable or write-address
inputs are doing at the same time — reset takes priority over any
write request. The cleared contents become the current state of the
block from that edge onward; they are not something that fades in
gradually or depends on a later access. As long as reset continues to
be held, the entries stay at zero on every subsequent qualifying
edge, and no write is allowed to take effect while it is asserted.

## Read behavior

The block exposes two read ports, each with its own two-bit address
input and its own eight-bit data output. Both read ports behave
identically to each other and operate completely independently: the
two addresses can point at the same entry or at two different
entries, and each port only ever reflects the entry it is currently
addressing.

Both read ports are combinational with respect to the stored
contents and with respect to their own address input. There is no
extra delay between an address changing (or the addressed entry's
stored value changing) and the corresponding read output reflecting
that change — the read output is always a direct reflection of
"whatever is currently stored at the currently addressed entry," with
no additional clock cycle of delay inserted anywhere in the read
path. If you change a read address, the corresponding output tracks
the new entry's contents right away, in the same instant, without
waiting for a clock edge.

## Behavior when a read targets an address that is also being written

Because reads are immediate reflections of the current stored
contents, and because writes update the stored contents exactly at a
rising clock edge, there is a well-defined and simple answer to what
happens when a read port's address happens to match the write address
during a cycle in which a write is committing:

Right up until that clock edge occurs, the entry being written still
holds its old value, so a read port addressing that same entry still
reports the old value during that time. The instant the clock edge
passes and the new data is latched into the entry, the stored
contents have changed, and — because the read ports are immediate,
delay-free reflections of the stored contents — the read output for
that address updates to the new value at that same instant, with no
further waiting. In other words, a read that targets the just-written
entry sees the old value up to the edge and the new value from that
edge onward, exactly as if it were reading any other entry whose
contents happened to change at that moment. No special extra logic is
needed to make this happen and none should be introduced; it is a
direct consequence of clocked storage paired with delay-free combinational
reads.

## Summary of expected observable behavior

- Exactly one entry updates per clock edge that has write-enable
  asserted and reset not asserted.
- Reset (while held) forces all four entries to zero on every
  qualifying edge and blocks any write from taking effect.
- Both read outputs are continuous, delay-free reflections of the
  entries their respective addresses currently point to.
- A read of an entry that was just written on the current edge shows
  the new value starting immediately after that edge, and the old
  value at all times before it — there is no additional cycle of
  delay in either direction.
- The two read ports never interfere with each other and can address
  the same or different entries in the same cycle without any special
  handling.

This description, together with the accompanying gate-level netlist
and wrapper, should be sufficient to reconstruct a clean, word-level
implementation of the block that reproduces its observable timing
exactly.