# Locking Description

## Overview

`locked_netlist.v` is a gate-level, structural Verilog netlist derived from a
small combinational reference circuit. The design has been logic-locked by
inserting a fixed number of key-controlled 2-to-1 multiplexers at internal
wire locations within the netlist.

## Total Number of Inserted Key Gates

The netlist contains exactly **4** key-controlled multiplexer instances.

Any correct analysis of this netlist must account for all 4 instances — no
more, no fewer.

## Locking Mechanism

Each inserted multiplexer is built entirely from basic gate primitives
(`and`, `or`, `not`, etc. — there is no behavioral `mux` construct anywhere
in the file) and implements the standard 2:1 multiplexer function:

```
Y = (S & B) | (~S & A)
```

where:

- **A** is one candidate data input to the multiplexer.
- **B** is the other candidate data input to the multiplexer.
- **S** is the select input, driven by exactly one bit of the bundled `key`
  input port (i.e. `key[i]` for some index `i` in `0..3`).
- **Y** is the multiplexer's output, which feeds into the rest of the
  netlist's downstream logic.

Under this formula the select polarity is fixed:

- When **S = 0**, the multiplexer forwards input **A**.
- When **S = 1**, the multiplexer forwards input **B**.

For each inserted multiplexer, exactly one of its two data inputs is the
signal that reproduces the netlist's intended, correct combinational
behavior; the other data input is a corrupted or otherwise altered variant
of that signal. The correct key bit value at a given locus is therefore
determined entirely by which data input (A or B) carries the correct
behavior at that locus, combined with the S=0→A / S=1→B polarity above:
if input A is the correct signal, the correct key bit is 0; if input B is
the correct signal, the correct key bit is 1. Applying the full correct key
vector across all four locked locations restores the netlist's intended
function.

This description does not identify which multiplexer instance corresponds
to which bit of the `key` port, nor which key bit value is correct at any
given instance — determining that mapping and those values from the
netlist itself is the task.

## Locating Candidate Lock Sites

Every multiplexer instance inserted by the locking process has an instance
name containing the substring `keymux`. You can enumerate all candidate
lock sites in the netlist with a simple text search, for example:

```
grep -n keymux inputs/locked_netlist.v
```

No other instances in the netlist use this naming convention, so this
substring reliably identifies all four inserted locking multiplexers
without requiring any prior knowledge of the specific locking scheme used.