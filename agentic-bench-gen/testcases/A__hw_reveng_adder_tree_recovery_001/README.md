# Hardware Reverse Engineering: Recover a Word-Level Design from a Flattened Netlist

## Background

You have been handed a gate-level Verilog netlist that was produced by a
synthesis/obfuscation flow. All hierarchy has been flattened into primitive
gates, and every internal signal has been renamed to a generic label
(`n1`, `n2`, `n3`, ...). The original word-level intent of the design is no
longer visible just by reading signal names or module structure.

Your job is to analyze this netlist, figure out what combinational function
it actually computes over its inputs, and produce a clean, synthesizable,
**word-level** Verilog module that reproduces the same input/output behavior
for every possible input combination.

This is a black-box/gray-box reverse-engineering exercise: you may read the
netlist structurally, simulate it with your own test vectors, and reason
about gate fan-in/fan-out patterns, but you should not assume any particular
word-level structure in advance — recover it from evidence.

## Provided artifacts (`inputs/`)

- **`inputs/flattened_netlist.v`** — the flattened gate-level netlist you
  must reverse-engineer. It defines a module with a fixed port list (see
  below) and instantiates only primitive cells internally.
- **`inputs/primitive_cells.v`** — the primitive gate/cell library used to
  build `flattened_netlist.v` (basic logic gates and small cells). You may
  read this to understand what each primitive does, and you may simulate
  `flattened_netlist.v` together with it to probe behavior. **Do not
  instantiate these primitives directly in your submission** — your
  recovered design must be expressed at the word/RTL level, not as a copy
  or rewiring of the primitive netlist.
- **`inputs/design_brief.md`** — a short public description of the design's
  black-box context (interface, expected analysis approach). It does not
  reveal the internal algorithm.

Do not modify any file under `inputs/`. Only your submission is graded.

## What you must submit

A single self-contained Verilog file at:

```
submission/recovered_rtl.v
```

It must define **exactly one** top-level module, with **exactly** this name
and port list:

```verilog
module recovered_design(
    input  [15:0] a,
    input  [15:0] b,
    input  [15:0] c,
    input  [15:0] d,
    output [31:0] sum
);
```

Requirements:

- `a`, `b`, `c`, `d` are four independent unsigned 16-bit input operands.
- `sum` is the unsigned 32-bit output result.
- The design must be **purely combinational** — no clock or reset ports, no
  latches, no internal state. The output must be a pure function of
  `a, b, c, d`.
- The file must be **self-contained**: no `` `include `` of
  `flattened_netlist.v`, `primitive_cells.v`, or any other project file, and
  no instantiation of the primitive cells defined in
  `inputs/primitive_cells.v`.
- The module name and port list must match exactly, or the grading harness
  will not be able to instantiate your design alongside the reference
  netlist.
- Your recovered RTL should describe the design's behavior directly in
  word-level Verilog (e.g. using arithmetic/logical operators on the
  16/32-bit buses), not merely re-express the gate netlist in different
  syntax.

## How grading works

Your submission is graded **behaviorally**, not by reading your code for
"the right answer." The evaluator:

1. Compiles `submission/recovered_rtl.v` together with a generated
   testbench and `inputs/flattened_netlist.v` (plus
   `inputs/primitive_cells.v`) using `iverilog`, instantiating both your
   `recovered_design` and the reference netlist's module under the same
   test harness.
2. Runs the simulation with `vvp` and applies a large suite of test
   vectors — at least 2000 randomized 4×16-bit input combinations, plus
   dedicated corner cases (all-zero inputs, all-max inputs) and a couple of
   fixed known vectors — comparing the `sum` output of your design against
   the reference netlist's `sum` output, vector by vector.
3. Declares PASS only if your design's output matches the reference
   bit-for-bit on **every** applied vector, compilation succeeds, and your
   submission passes a basic structural sanity check confirming it is an
   independent recovered design rather than a trivial copy/wrapper of the
   provided netlist or its primitives.

A submission that fails to compile, produces mismatched outputs on any
vector, or is a thin wrapper around the provided netlist/primitives will
not pass.

## Example known behavior

As two sanity-check data points you can use while developing and testing
your own recovered design locally:

- For `a=16'h0001, b=16'h0002, c=16'h0003, d=16'h0004`, note what `sum`
  the reference netlist produces and make sure your recovered design
  agrees.
- For `a=16'hFFFF, b=16'hFFFF, c=16'hFFFF, d=16'hFFFF`, likewise check that
  your recovered design's output matches the reference netlist's output.

These are just two of the thousands of vectors the evaluator will actually
apply — treat them as a starting point for validating your own
understanding of the design's behavior, derived by simulating
`inputs/flattened_netlist.v` yourself, not as numbers to hard-code.

## Constraints checklist

- [ ] Single file: `submission/recovered_rtl.v`
- [ ] Module name and port list match exactly
- [ ] No includes of any files under `inputs/`
- [ ] No instantiation of primitives from `inputs/primitive_cells.v`
- [ ] Purely combinational (no clock/reset, no latches)
- [ ] Compiles cleanly with `iverilog` and simulates cleanly with `vvp`
- [ ] Matches the reference netlist's output for every input vector the
      evaluator applies

Good luck — analyze carefully, verify broadly, and submit RTL that truly
recovers the design's word-level behavior rather than one that merely
happens to look plausible.