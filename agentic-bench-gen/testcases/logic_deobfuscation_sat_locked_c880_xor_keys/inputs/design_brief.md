# Design Brief: locked_c880 IP Block

## Overview

`locked_c880` is a combinational logic block derived from a classic
benchmark circuit (in the style of ISCAS-85 `c880`). The block has been
packaged with a *logic locking* mechanism: the design will only reproduce
its intended input/output behavior when supplied with the correct activation
key on a dedicated key input bus.

This brief describes the locking scheme at a high level for engineers or
analysts who need to work with the locked netlist, `locked_c880.v`, without
having access to the original unlocked ("golden") design.

## Key Bus

The design exposes an 8-bit key input bus:

```
keyIn[0:7]
```

All eight bits of `keyIn` must be driven with the correct activation pattern
for the circuit to behave identically to the original golden design. Driving
any bit incorrectly may alter internal signal values and, depending on where
that signal fans out to, may change one or more primary outputs.

## Locking Style

The locking scheme used in this design inserts small key-controlled gates at
various points in the netlist. Each such gate takes one key bit and one
internal signal as its two inputs, and produces a new internal signal that
the rest of the design consumes in place of the original one. Depending on
the specific insertion point, these key-controlled gates may be implemented
using different two-input gate primitives (for example, gates in the XOR/XNOR
family are common choices for this style of locking, since a wrong key bit
inverts the affected signal relative to the correct key). Other gate
primitives are possible in general logic-locking schemes as well.

## Naming Convention

To aid in downstream tooling and documentation, gate instances in the
netlist that are directly wired to a bit of the `keyIn` bus follow a
consistent instance-naming convention: such instances are named `u_keyN`,
where `N` corresponds to the index of the `keyIn` bit driving that instance
(e.g. an instance named `u_key3` is driven by `keyIn[3]`). This convention
applies only to the gate instance that directly consumes a `keyIn` bit as
one of its inputs; downstream logic that consumes the output of such a gate
follows the netlist's ordinary internal naming.

## Notes on Key Recoverability

Because this is a combinational design, the effect of any given key bit on
the circuit's observable behavior depends entirely on whether the internal
signal it gates actually reaches one or more of the primary outputs for the
range of primary-input combinations being exercised. In principle, a key bit
that controls a signal with no observable path to any output under a given
set of test vectors cannot be distinguished from its complement using only
those vectors — both key values would produce identical observed behavior.

Anyone analyzing this design from a finite set of input/output oracle
vectors (rather than from the original golden netlist) should keep this in
mind: some key bits may be fully determinable from the supplied vectors,
while others may not be resolvable with confidence regardless of how many
vectors are examined, depending on the structural location of the gate they
control. Reporting a bit as indeterminate is expected and appropriate when
the evidence does not support a confident conclusion.