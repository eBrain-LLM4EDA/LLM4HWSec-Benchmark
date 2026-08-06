# Locking Description

## Overview

This netlist has been protected using a MUX-based logic locking scheme. A total
of **4 key gates** have been inserted at internal wire locations within the
original combinational circuit.

## Locking Mechanism

Each key gate is implemented as a 2-to-1 multiplexer (`mux2x1`) instantiated at
an internal wire of the original design. Every such multiplexer instance name
contains the substring `keymux` so that candidate lock locations can be
identified structurally without prior knowledge of the exact scheme.

Each inserted multiplexer has the following interface:

- `A`: one candidate data input
- `B`: the other candidate data input
- `S`: select line, driven by a single bit of the `key` input port (`key[i]`)
- `Y`: multiplexer output, which replaces the original internal wire and feeds
  all downstream logic that previously consumed that wire

For each locking site, exactly one of the two data inputs (`A` or `B`) carries
the original, functionally-correct signal from the unlocked design. The other
data input carries a corrupted/decoy variant of that signal, obtained by
altering the correct signal (e.g. via inversion) so that selecting it produces
incorrect circuit behavior.

The correct key value at a given lock is whichever select value (0 or 1)
causes the multiplexer to forward the functionally-correct data input to its
output. Applying the full correct key vector across all 4 locks makes the
locked netlist functionally equivalent (identical truth table over all
primary input combinations) to the original unlocked reference circuit.

## Key Port

The locked netlist exposes a bundled input port named `key` whose width equals
the number of inserted key gates (4 bits in this instance). Each bit of `key`
drives the select line of exactly one `keymux` instance.

## What Is Withheld

This document intentionally does not disclose:

- The specific instance names assigned to the inserted multiplexers
- Which data input (`A` or `B`) is functional versus decoy at each site
- The correct key bit values

Recovering this information from netlist structure and/or simulation is the
objective of the analysis task.