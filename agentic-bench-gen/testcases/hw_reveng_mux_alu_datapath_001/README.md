# Recover a MUX-based ALU Datapath's Word-Level Function

## Task ID
`hw_reveng_mux_alu_datapath_001`

## Objective

You are given a flattened, bit-level gate netlist of a small combinational
datapath with two 8-bit data inputs, a 2-bit select input, and an 8-bit
output. The netlist was produced by bit-blasting a word-level design into
primitive gates (AND, OR, XOR, NAND, NOR, XNOR, NOT, and multiplexers built
from these), which obscures the original word-level operation performed for
each select value.

Your job is to analyze the netlist and produce a clean, word-level Verilog
module that is **functionally equivalent** to the original gate-level design
for every possible input combination.

The datapath implements four common ALU-style operations across two data
operands `a` and `b`, chosen by a 2-bit select signal `sel`. The exact
mapping from `sel` value to operation is *not* stated here — you must
determine it yourself by studying the netlist structure and/or simulating
it, exactly as a reverse engineer would when given only a flattened netlist.

## Provided Inputs

All reference materials live under `inputs/` and **must not be modified**.
Your submission is graded against these files as the ground truth; editing
them will not change how you are scored (the evaluator uses its own private
copies).

- `inputs/gate_netlist.v` — the reference flattened gate-level netlist,
  module `gate_netlist`, with ports:
  ```
  module gate_netlist(input [7:0] a, input [7:0] b, input [1:0] sel, output [7:0] y);
  ```
  This is the ground-truth behavioral oracle. Read it, trace it, simulate
  it — but do not alter it.

- `inputs/design_brief.md` — a short narrative description of the design's
  origin and some hints about how to approach tracing the gate structure
  (e.g. what to look for when distinguishing arithmetic behavior from
  bitwise behavior). It intentionally does **not** hand you the
  select-to-operation mapping.

- `inputs/testbench_template.v` — a minimal, standalone testbench skeleton
  that instantiates `gate_netlist` and prints `a, b, sel, y` for some
  stimulus. Use it (or something like it) to explore the netlist's behavior
  locally with `iverilog`/`vvp` before you commit to a word-level
  hypothesis. It is a starting point for your own exploration, not the
  official grading harness.

## What You Must Submit

Create exactly one file:

```
submission/recovered_rtl.v
```

It must define **exactly one module** named `recovered_datapath` with this
exact port list (name, order, widths, directions):

```verilog
module recovered_datapath(
    input  [7:0] a,
    input  [7:0] b,
    input  [1:0] sel,
    output [7:0] y
);
```

- `a` — 8-bit operand A
- `b` — 8-bit operand B
- `sel` — 2-bit operation select
- `y` — 8-bit result output

No additional ports. No clock. No latches. The module must be purely
combinational and must reproduce, bit-for-bit, the output of
`inputs/gate_netlist.v` for every `(a, b, sel)` combination that the
evaluator exercises.

## Constraints

1. **Do not modify anything under `inputs/`.** The evaluator reads its own
   reference copies of these files; changes on your side have no effect on
   grading and may cause your submission to be rejected outright.
2. **`recovered_datapath` must be purely combinational** — no `always @(posedge ...)`
   blocks, no inferred latches, no internal state.
3. **Standard Verilog only.** Do not instantiate vendor-specific primitives,
   IP cores, or simulator-specific constructs. The module must be
   synthesizable/simulatable standalone with only standard Verilog.
4. `y` must be driven for every possible value of `sel` (all four 2-bit
   encodings are valid and must produce a defined result).
5. Only the single file `submission/recovered_rtl.v` is graded. Do not add
   extra modules with conflicting names, and do not rely on files outside
   `submission/` and `inputs/`.

## How You Will Be Graded

Grading is **behavioral**, not textual. The evaluator will:

1. Compile your `submission/recovered_rtl.v` together with
   `inputs/gate_netlist.v` and a generated testbench using `iverilog`.
2. Run the simulation with `vvp` over a broad sweep of `(a, b, sel)` test
   vectors — a mix of randomized combinations and directed edge cases
   (e.g. `a=0`, `a=255`, values that trigger arithmetic overflow/underflow,
   non-commutative operand pairs that would expose a swapped
   add/subtract or reversed subtraction order).
3. Compare, cycle by cycle, the output `y` of your `recovered_datapath`
   against the output `y` of the reference `gate_netlist` for every vector.

Your submission passes a given check only if the simulated outputs match
**exactly** for all exercised vectors — there is no partial credit for
"close" arithmetic and no static/source-only pass path. A design that
merely looks plausible but disagrees with the reference netlist's simulated
output on even one vector will fail that check.

This README intentionally does **not** publish any expected `(a, b, sel) -> y`
table. Any "correct answer" you need is defined by simulating
`inputs/gate_netlist.v` itself — use the provided testbench template (or
your own) to compute expected values locally rather than trusting any
hand-derived arithmetic.

### Metrics you will be scored on

- **word_recovery_rate** — fraction of the four underlying operations
  (add, subtract, bitwise AND, bitwise OR) that your module correctly
  implements, as measured by per-operation simulation pass/fail.
- **structural_match_accuracy** — how closely your module's port list and
  combinational structure conform to the pinned interface above (correct
  module name, correct port widths/directions, no clocked logic).
- **functional_equivalence** — percentage of the full randomized + directed
  test vector sweep for which your module's output matches the reference
  netlist's output exactly, via `iverilog`/`vvp` simulation.

## Baseline Submission

A placeholder file already exists at `submission/recovered_rtl.v`. It
compiles and exposes the correct port list, but its internal logic is a
trivial stub that does not implement the real behavior. It is expected to
**fail** the functional checks — replace its contents entirely with your
own recovered implementation.

## Suggested Approach

1. Read `inputs/design_brief.md` for context.
2. Open `inputs/gate_netlist.v` and identify recurring per-bit structures
   (look for repeated gate clusters across bit positions 0–7 — this is a
   strong signal of a bit-sliced word-level operation).
3. Use `inputs/testbench_template.v` as a starting point to simulate
   `gate_netlist` for a handful of hand-picked `(a, b, sel)` values and
   observe how `y` behaves as you vary each input independently. Pay
   particular attention to carry-like propagation between bit slices when
   `sel` selects certain values — this is often the distinguishing feature
   between arithmetic and bitwise operations.
4. Form a hypothesis for what each `sel` encoding computes, write your
   candidate `recovered_datapath` module, and re-simulate against
   `gate_netlist` yourself to check agreement before submitting.
5. Iterate until you are confident your module matches the reference for
   all four operations across the full input range, then place your final
   module at `submission/recovered_rtl.v`.