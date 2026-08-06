# Hardware Reverse Engineering: Recover an FSM from a Flattened Sequential Netlist

## Background

You are handed a small, flattened gate-level netlist of a synchronous sequential
circuit. It was produced by some upstream toolchain and shipped to you with no
comments, no state diagram, and no documentation beyond the black-box behavioral
contract in `inputs/design_brief.md`. All internal signal names are meaningless
(`n1`, `n7`, `n13`, ...), and the logic is built entirely out of primitive gates
and flip-flops instantiated from `inputs/primitives.v`.

Your job is to reverse-engineer what this circuit *does*, and re-express that
behavior as clean, human-readable, word-level Verilog RTL — a proper FSM
description using a state register and `always`/`case`/`if` logic — that is
functionally identical to the original netlist for every possible input
sequence.

## What you're given (`inputs/`)

- `flattened_netlist.v` — the reference gate-level netlist, module
  `flattened_netlist(clk, rst, in, out)`. This is the ground-truth circuit
  whose behavior you must reproduce. **Do not modify this file.**
- `primitives.v` — the gate/flip-flop primitive library
  (`NAND2`, `NOR2`, `XOR2`, `INV`, `DFF`) that `flattened_netlist.v` instantiates.
  **Do not modify this file.**
- `stimulus.txt` — a sample input sequence you can use to exercise the circuit
  yourself (see format below). **Do not modify this file.**
- `design_brief.md` — the public behavioral contract for the circuit: what the
  ports mean and how reset behaves. It intentionally does **not** tell you what
  the circuit's internal logic computes — that's the part you need to figure
  out by reading the netlist and/or simulating it.

You may build your own scratch testbenches to simulate `flattened_netlist.v`
together with `primitives.v` while you investigate (using `iverilog`/`vvp`,
which are available in this environment). Nothing under `inputs/` should be
edited, and nothing you build for your own exploration needs to be submitted —
only the final recovered RTL matters.

## What you must submit

A single file at:

```
submission/recovered_rtl.v
```

containing exactly one Verilog module with this exact name and port list:

```verilog
module recovered_fsm(
    input  clk,
    input  rst,
    input  in,
    output out
);
```

- `clk` — free-running clock (driven by the evaluator).
- `rst` — synchronous, active-high reset. While asserted, the circuit must
  return to its initial state on the next rising clock edge and hold that
  state's output.
- `in` — single-bit input sampled on every rising edge of `clk`.
- `out` — single-bit Moore output reflecting the current internal state; it
  must remain stable between clock edges and only change in response to a
  `clk` edge.

## Constraints

1. **Do not modify anything under `inputs/`.** Only `submission/recovered_rtl.v`
   is graded.
2. **The submitted file must be self-contained**: exactly one module, no
   `` `include `` directives, no dependency on other source files.
3. **No gate-primitive instantiation.** You must not instantiate `NAND2`,
   `NOR2`, `XOR2`, `INV`, `DFF`, or any other primitive from `primitives.v`
   inside your submission, and you must not paste the contents of
   `flattened_netlist.v` (or a lightly-renamed copy of it) into your
   submission. The whole point of this exercise is to express the *recovered
   intent* at the word/register level — a state register plus behavioral
   transition/output logic (e.g. an `always @(posedge clk)` block with a
   `case` or `if/else` chain) — not to repackage the original gates.
4. **Single clock domain, synchronous active-high reset**, matching the
   behavior described in `design_brief.md`.
5. Your recovered FSM does **not** need to use the same internal state
   encoding or number of state bits as the original netlist — only equivalent
   observable behavior (same `out` sequence for the same `rst`/`in` sequence)
   is required.

## Stimulus file format

`inputs/stimulus.txt` is a plain-text file, one line per clock cycle, with two
space-separated 0/1 values per line:

```
rst in
```

For example, a line `0 1` means: on this rising clock edge, `rst=0` and
`in=1`. There is no header line and no `out` column shipped in this file —
you're expected to determine the corresponding `out` values yourself by
simulating `inputs/flattened_netlist.v` (together with `inputs/primitives.v`)
with your own testbench, rather than being handed the answer. Use this file as
a convenient worked example to sanity-check your understanding of the reset
and input behavior before you write your recovered RTL.

## How you'll be evaluated

Grading is fully behavioral: your `submission/recovered_rtl.v` is compiled
with `iverilog` alongside a testbench (which you do not need to write) and
simulated with `vvp`. Its `out` waveform is compared, cycle by cycle, against
a simulation of the reference `inputs/flattened_netlist.v` circuit.

The comparison is not limited to the shipped `stimulus.txt` sequence — the
evaluator also generates additional pseudo-random input sequences and
adversarial/edge-case sequences (e.g. sequences designed to probe boundary
cases and repeated resets) at grading time and checks agreement on those too.
Expected `out` values are always derived by simulating the reference netlist
itself, never from a hand-computed answer key, so make sure your design is
genuinely equivalent rather than tuned to one example trace.

At a high level, your submission is scored on:

- **compile_success** — does `iverilog` compile your file cleanly with the
  evaluator's testbench?
- **structural_match_accuracy** — does your module have exactly the required
  name and port list (`recovered_fsm` with `clk`, `rst`, `in`, `out`, all
  1-bit, correct directions)?
- **word_recovery_rate** — is your design actually expressed at the
  word/behavioral level (state register + `always`/`case`/`if` logic), rather
  than being a wrapper around the original gate primitives?
- **functional_equivalence** — does your `out` sequence match the reference
  netlist's `out` sequence, cycle by cycle, across the shipped stimulus and
  the evaluator's hidden random/adversarial sequences?

## Deliverable summary

- `submission/recovered_rtl.v` — a single self-contained Verilog file defining
  `module recovered_fsm(input clk, input rst, input in, output out);` that is
  cycle-accurate behaviorally equivalent to `inputs/flattened_netlist.v`,
  written using ordinary word-level/behavioral RTL constructs.