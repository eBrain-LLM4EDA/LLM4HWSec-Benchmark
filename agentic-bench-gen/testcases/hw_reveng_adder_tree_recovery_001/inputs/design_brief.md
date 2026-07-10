# Design Brief: Flattened Combinational Netlist

## Context

The file `inputs/flattened_netlist.v` was produced by an internal
synthesis/obfuscation flow starting from an unknown combinational RTL
design. During flattening:

- All module hierarchy was collapsed into a single flat netlist of
  primitive gate instances (see `inputs/primitive_cells.v` for the cell
  library used).
- Every internal net was renamed to a generic label (`n1`, `n2`, `n3`, ...)
  with no correspondence to the original signal names.
- No comments, module boundaries, or word-level groupings from the
  original design were preserved.

The result is a netlist that is fully simulatable and behaviorally
identical to the original design, but from which the original design
intent is not obvious by inspection alone.

## Interface

The flattened netlist exposes a fixed, stable port list:

```verilog
module recovered_design(
    input  [15:0] a,
    input  [15:0] b,
    input  [15:0] c,
    input  [15:0] d,
    output [31:0] sum
);
```

- Four independent 16-bit input buses: `a`, `b`, `c`, `d`.
- One 32-bit output bus: `sum`.
- The design is purely combinational: there is no clock, no reset, and no
  internal state anywhere in the netlist. The output is a pure function of
  the four input buses.

This is the same port list your recovered design must expose, since the
grading harness instantiates both the reference netlist and your submitted
module side by side and drives them with identical input vectors.

## What is known

- The design takes four 16-bit operands and produces a single 32-bit
  result.
- The internal implementation is built entirely from small combinational
  primitives (basic gates and a handful of small compound cells), wired
  together in a way that reflects the original design's logic, but with
  no naming or grouping clues left behind.
- The number of gates, their fan-in/fan-out relationships, and any
  repeating structural patterns in the netlist are the only structural
  evidence available besides black-box simulation.

## What is not given

- No original RTL, no netlist comments, and no signal-name mapping are
  provided.
- No description of the specific arithmetic or logical function computed
  is given in this brief. You should not assume any particular operation
  (arithmetic, logical, comparison, or otherwise) without evidence.

## Suggested approach

You are free to use any combination of the following (and other techniques
you find useful):

- **Black-box behavioral probing.** Simulate `inputs/flattened_netlist.v`
  (together with `inputs/primitive_cells.v`) against your own test
  vectors using `iverilog`/`vvp`. Structured vectors — e.g. varying one
  input bit at a time, holding others at zero; sweeping single operands
  while others are fixed; testing boundary values such as all-zero or
  all-max operands — can reveal a great deal about the underlying
  word-level function.
- **Structural inspection.** Read `inputs/flattened_netlist.v` and
  `inputs/primitive_cells.v` to understand what each primitive computes,
  and look at how instances are wired together. Repeating structural
  motifs, bit-slice patterns, and fan-in shapes can hint at word-level
  operations even when names are meaningless.
- **Hypothesis testing.** Once you have a hypothesis for the word-level
  function, write a small reference model and compare it against the
  flattened netlist over a wide range of inputs (including corner cases)
  before committing to your final recovered RTL.

## Deliverable

Your analysis should culminate in a single, clean, word-level Verilog RTL
module — expressed using standard arithmetic/logical operators over the
`a`, `b`, `c`, `d`, and `sum` buses — that reproduces the flattened
netlist's behavior for every input combination. See the top-level
`README.md` for the exact submission requirements and grading process.