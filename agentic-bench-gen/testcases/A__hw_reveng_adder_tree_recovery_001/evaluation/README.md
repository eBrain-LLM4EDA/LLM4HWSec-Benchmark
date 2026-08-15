# Evaluation Guide: Adder Tree Recovery

This document explains how `evaluate.py` grades your submission. It does
not modify or depend on anything in `inputs/` beyond reading it for
reference; only `submission/recovered_rtl.v` is graded.

## What you must submit

A single file at:

```
submission/recovered_rtl.v
```

defining exactly one top-level module with this exact name and port list:

```verilog
module recovered_design(input [15:0] a, input [15:0] b, input [15:0] c, input [15:0] d, output [31:0] sum);
```

- `a`, `b`, `c`, `d` are four independent unsigned 16-bit input operands.
- `sum` is the unsigned 32-bit output result.
- No clock or reset ports. The design must be purely combinational:
  `sum` must depend only on the current values of `a`, `b`, `c`, `d`.
- The file must be self-contained (no `` `include `` of any other project
  file) and must compile standalone with a standard Verilog-2001 /
  SystemVerilog-subset toolchain.

## How grading works

`evaluate.py`:

1. Confirms `inputs/flattened_netlist.v`, `inputs/primitive_cells.v`, and
   `submission/recovered_rtl.v` all exist. Any missing file is reported as
   a `SETUP` failure.
2. Runs two static structural gates (SR1, SR2 — see below) directly on
   the text of your submitted file.
3. Generates a deterministic vector list containing:
   - the two known vectors from the spec (`a=1,b=2,c=3,d=4` and
     `a=b=c=d=0xFFFF`),
   - an all-zero corner case,
   - 2000 pseudo-randomly generated 4x16-bit input combinations (fixed
     seed, so the vector set is identical on every run),
   - a repeat of the first known vector at the very end of the run, used
     to confirm your design has no hidden state.
4. Builds a temporary renamed copy of `inputs/flattened_netlist.v`
   (module name changed only, behavior unchanged) so both your design and
   the reference design can be instantiated side by side in one
   testbench (this satisfies the "compile together" acceptance criteria
   and gives you a diagnostic companion signal in the simulation output).
5. Compiles `submission/recovered_rtl.v`, the renamed reference netlist,
   `inputs/primitive_cells.v`, and the generated testbench together with
   `iverilog`.
6. Runs the compiled simulation with `vvp`, applying every vector in the
   generated list and recording your module's `sum` output on every
   vector.
7. Parses the simulation's printed results to derive PASS/FAIL for each
   requirement below.

Compilation failures, simulation crashes, or timeouts are treated as
failures of every behavioral requirement (FR1–FR4), not as `SETUP`
failures — a submission that does not build or run cleanly does not pass.

## Graded requirements

| ID  | What it checks |
|-----|-----------------------------------------------------------------|
| FR1 | For every applied test vector (2000+ randomized, plus known and corner-case vectors), your module's simulated `sum` output must equal the mathematically correct unsigned result of adding all four operand values for that exact vector. This expected value is computed independently for each vector (not read off of any single companion circuit's simulated output), so your recovered design is judged against the true arithmetic definition of the function, not against a particular implementation's raw output. |
| FR2 | The two specific known vectors from the spec produce the exact pinned results: `a=1,b=2,c=3,d=4` → `sum=0x0000000A`, and `a=b=c=d=0xFFFF` → `sum=0x0003FFFC`. |
| FR3 | Your submission compiles cleanly with `iverilog` and simulates to completion with `vvp` without runtime errors, producing a result for every applied vector. |
| FR4 | Your design is purely combinational/stateless: applying the identical input vector again later in the same simulation run produces the identical output, regardless of simulation history. |
| SR1 | Structural non-recovery gate: your submission must not merely instantiate/wrap the primitive gate cells from `inputs/primitive_cells.v` in bulk, must not `` `include `` `inputs/primitive_cells.v` or `inputs/flattened_netlist.v`, and must not be a near-identical copy of `inputs/flattened_netlist.v`. Genuine word-level RTL (using ordinary arithmetic/logical operators) passes this gate; a disguised copy of the flattened netlist does not. |
| SR2 | Timing side-channel gate: your submission must not contain explicit delay-control constructs (e.g. `#5`, `#(expr)`) outside of a `` `timescale `` directive, which could otherwise mirror internal timing/carry-chain structure from the original netlist. |

## A note on FR1

Do not assume that matching the exact bit pattern produced by
`inputs/flattened_netlist.v` on every conceivable vector is the same
thing as recovering the correct word-level function. The grading harness
checks your output against the actual arithmetic definition of the
function described in the task objective, computed independently for
each applied vector. A genuinely correct word-level implementation of
`sum = a + b + c + d` will satisfy this on every vector, including
corner cases and overflow-inducing combinations.

## Exit behavior

`evaluate.py` prints one line per requirement, either:

```
[TEST] PASS: <requirement_id>
```

or

```
[TEST] FAIL: <requirement_id>: <reason>
```

The process exits `0` only if all six requirements (`FR1`–`FR4`,
`SR1`–`SR2`) pass; otherwise it exits non-zero.