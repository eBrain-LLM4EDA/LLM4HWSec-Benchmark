# Design Brief: `perm_check` — 4-bit Permission Comparator

## Purpose

`perm_check` is a small combinational circuit that guards access to a
protected resource. It compares a runtime-presented 4-bit identifier
(`id_in`) against a fixed, hardwired 4-bit authorized identifier
(`id_auth`) and asserts a single-bit `grant` signal only when the two
values are exactly equal, bit for bit.

This document describes the *intended* design as specified to the
synthesis/ECO flow, prior to gate-level mapping. It accompanies
`inputs/netlist.v` as a reference for what the flattened netlist is
supposed to implement.

## Functional specification

```
grant = 1   iff   id_in[3:0] == id_auth[3:0]
grant = 0   otherwise
```

Equivalently, `grant` is the AND-reduction of four per-bit equality
terms:

```
eq[i] = ~(id_in[i] ^ id_auth[i])      for i = 0, 1, 2, 3
grant = eq[0] & eq[1] & eq[2] & eq[3]
```

Note that bitwise equality of two single-bit signals is exactly the
**XNOR** function: two bits are equal exactly when their XNOR is `1`.
No other primitive computes this relationship correctly for a single
bit position — an XOR, for instance, computes the *inequality* of the
two bits and is not appropriate for this role.

## Intended structural decomposition

The design is expected to be synthesized as a flattened two-stage
structure:

**Stage 1 — per-bit equality.** Four instances, one per bit position,
each comparing one bit of `id_in` against the corresponding bit of
`id_auth`:

- `u_eq0` — computes `eq[0]` from `id_in[0]` and `id_auth[0]`
- `u_eq1` — computes `eq[1]` from `id_in[1]` and `id_auth[1]`
- `u_eq2` — computes `eq[2]` from `id_in[2]` and `id_auth[2]`
- `u_eq3` — computes `eq[3]` from `id_in[3]` and `id_auth[3]`

Each of these four instances should be bound to the **`XNOR2`**
primitive cell from `inputs/primitive_cells.v`, with `.A` and `.B`
connected to the corresponding `id_in`/`id_auth` bit and `.Y` driving
the corresponding `eq[i]` net.

**Stage 2 — AND-reduction tree.** The four equality terms are combined
with a small tree of 2-input AND gates to produce the final `grant`
output:

- an instance combining `eq[0]` and `eq[1]` into an intermediate
  "low-pair" term
- an instance combining `eq[2]` and `eq[3]` into an intermediate
  "high-pair" term
- a final instance combining the two intermediate terms to drive
  `grant`

This reduction tree should be built entirely from `AND2` primitive
cells, with no inversions or other logic introduced along the way.

## Expected instance/gate count

A correct flattening of this design should contain exactly:

- 4 two-input equality cells (one per bit, all of type `XNOR2`)
- 3 two-input `AND2` cells forming the reduction tree

for a total of 7 gate instances, with no unused or dangling nets, and
with connectivity matching the bit-slicing and tree structure described
above. No additional gates (inverters, buffers, or extra logic) are
expected anywhere in the design; the netlist should map onto this
seven-gate topology one-for-one.

## Scope of this brief

This document describes design **intent** only — the behavior and
structure the synthesis/ECO flow was asked to produce. It does not
constitute a statement about the correctness of any particular
netlist delivered downstream. Verifying that a delivered gate-level
netlist actually conforms to this intent (in terms of both function
and per-instance cell binding) is the responsibility of whoever
reviews that netlist.