# Locking Scheme Notes

This document gives general background on the class of logic-locking
techniques that may be present in `locked_netlist.v`. It is intended as a
starting point for analysis, not a complete specification of the scheme
actually used.

## General Background

Logic locking schemes insert additional key-controlled logic into a
combinational netlist so that the circuit only computes its intended
function when the correct secret key is applied on the `key[]` input port.
Common families of key-insertion techniques include:

- **Simple key gates**: individual XOR/XNOR (or MUX-based) gates inserted
  along a signal path, where one input is a primary data wire and the
  other is a single key bit. Correct operation requires the key bit to
  match the value the design was synthesized against; an incorrect bit
  typically flips or corrupts the corresponding internal signal.
- **SAT-resistant / point-function-like structures**: larger sub-networks
  built so that most key-input assignments cause a large fraction of
  primary-input patterns to produce a fixed or heavily-biased output,
  with only a rare, narrow region of input space being "discriminating."
  These structures are usually built from two or more sub-networks
  (branches) computed over overlapping sets of primary inputs and key
  bits, whose outputs are then combined (e.g., via AND/XOR/XNOR) to
  produce a gating signal that is merged with the rest of the design's
  functional output.
- Combinations of the above are also possible: a design may use ordinary
  key gates for some key bits and a more elaborate gating sub-network for
  others.

The netlist provided in `locked_netlist.v` may use any single one of these
approaches, a combination, or something structurally different. No
particular family is guaranteed, and you should not assume the locking
scheme matches any one textbook description exactly — treat the netlist
itself as the ground truth and use the background above only as a guide to
the kinds of structures worth looking for.

## What to Look For

When analyzing the netlist:

- Not every key bit necessarily plays the same structural role. Some key
  bits may only affect whether the circuit computes the *correct*
  function for a given primary-input pattern (i.e., they matter for
  functional correctness but are not distinguishable from the netlist
  structure alone without a reference output to compare against). Other
  key bits may participate in gating logic whose structure is more
  directly observable — for instance, if a key input's declared wire
  turns out not to be the actual signal driving the logic at the position
  where a key literal is expected, because some other, non-key-dependent
  signal has been substituted there instead. Such substitutions, when
  present, are a purely structural fact about the netlist and can be
  identified by tracing signal names and instance connections directly in
  the text, without needing to simulate or compare against any oracle.
- Identify any sub-networks that appear designed specifically to gate or
  mask the "real" functional output, as opposed to logic that is part of
  the core function itself. Look at how many primary inputs and key bits
  feed each candidate sub-network, whether there appear to be two or more
  sub-networks computed over similar/overlapping input sets, and how
  their outputs are ultimately combined and merged with the rest of the
  design before reaching the primary output port.
- Pay attention to instance and wire naming — synthesis and locking tools
  often leave descriptive instance names in place, which can be a useful
  (though not guaranteed) hint about a block's role.

## Practical Notes

- The netlist is small — well under 300 gate instances — so it is
  practical to read through the entire file directly, or to load it into
  `yosys` for a structural overview, e.g.:

  ```
  yosys -p "read_verilog inputs/locked_netlist.v; stat; show"
  ```

  `iverilog`/`vvp` can also be used if you want to simulate the netlist as
  given (for example, to sanity-check how a particular gate behaves for a
  chosen set of input values), keeping in mind that no external reference
  output table is provided — any simulation you run is against the
  netlist itself, not against a golden/oracle implementation.

- `inputs/primary_io.txt` lists the primary input and output ports of the
  module (names, bit widths, and directions) for quick reference so you
  can confirm identifiers before cross-referencing them against the
  netlist text.

- Base every claim in your submitted report on concrete, checkable
  evidence from `locked_netlist.v` (instance names, wire connections,
  literal polarities, etc.). Where the netlist does not provide enough
  structural evidence to determine a key bit's value, report that bit as
  unknown rather than guessing.