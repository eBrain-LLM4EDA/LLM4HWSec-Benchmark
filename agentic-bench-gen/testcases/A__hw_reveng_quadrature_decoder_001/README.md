# Hardware Reverse Engineering: Quadrature Position/Direction Decoder

## Objective

You are given a **flattened gate-level netlist** implementing an undocumented
quadrature decoder block used in a motion-control subsystem, along with an
obfuscated RTL wrapper that instantiates it. Your job is to **reverse-engineer
the word-level behavior** of this block and reimplement it as a clean,
synthesizable Verilog module named `quad_decoder` that matches the pinned
interface below.

The netlist and wrapper are built only from primitive gates and flip-flops
(DFFs, XOR/AND/OR/NOT/MUX primitives, and a ripple adder made of full-adder
cells). This obscures the fact that the design is really tracking a 2-bit
Gray-code state machine and a small position accumulator. Your recovered
design should express that intent directly in word-level RTL, not by copying
gate structure.

## Input Artifacts

All files under `inputs/` are **reference-only**. Do not modify them; they
describe the design you must reverse-engineer and are not part of your
submission.

- `inputs/quadrature_netlist.v` — the flattened gate-level netlist
  (`module quad_decoder_gates`), including its own primitive submodules
  (DFF, and2, or2, xor2, not1, mux2, fadd1) so it elaborates standalone.
- `inputs/quadrature_wrapper.v` — an obfuscated wrapper
  (`module quad_decoder_wrapper`) that instantiates the gate-level netlist
  with renamed signals, showing how it plugs into a clk/rst/a/b/pos/dir/invalid
  boundary. Its port names deliberately do **not** match the pinned interface
  — you must recover the intended word-level behavior, not just rename ports.
- `inputs/design_brief.md` — a plain-language design brief describing the
  building blocks of the netlist (current/previous state registers, XOR
  compare gates, decode/mux tree, position accumulator) and the general
  intent of the block, without giving away exact timing formulas or Verilog
  code.

## Required Interface (pinned — must match exactly)

Your submitted module **must** be named exactly `quad_decoder` and declared
with exactly this port list:

```verilog
module quad_decoder (
    input  wire        clk,
    input  wire        rst,
    input  wire         a,
    input  wire         b,
    output reg  signed [7:0] pos,
    output reg          dir,
    output reg          invalid
);
```

Port semantics:

- `clk` — rising-edge clock.
- `rst` — **synchronous, active-high** reset. While `rst=1` at a rising edge,
  on that same edge `pos` loads to `8'sd0`, `dir` loads to `0`, and `invalid`
  loads to `0`. These reset values become observable starting the cycle
  immediately after the reset edge (all three outputs are registered Moore
  outputs).
- `a`, `b` — sampled quadrature inputs. Each cycle, `{a,b}` is expected to
  hold a stable 2-bit Gray-code value. A legal transition changes only one
  of the two bits between consecutive sampled cycles; a simultaneous change
  in both bits is illegal.
- `pos`, `dir`, `invalid` — registered (Moore) outputs, updated on the rising
  clock edge based on comparing the `{a,b}` value sampled at the end of the
  previous cycle to the `{a,b}` value sampled at the end of the current
  cycle. There is exactly one clock cycle of latency from an input transition
  to the corresponding output update — no extra pipeline stages.

## Functional Requirements (informal summary)

The full precise timing contract lives in `metadata.json` (field
`interface`, copied verbatim from the pinned specification) — that document
is authoritative. In plain terms, your design must satisfy:

- **FR1 (forward sequence):** Driving `a,b` through the forward Gray
  sequence `00 -> 01 -> 11 -> 10 -> 00`, one pattern per cycle after reset
  release, `pos` must increment by 1 per legal step, `dir` must read 1
  during/after these transitions, and `invalid` must stay 0.
- **FR2 (reverse sequence):** Driving `a,b` through the reverse sequence
  `00 -> 10 -> 11 -> 01 -> 00` must decrement `pos` by 1 per legal step,
  `dir` must read 0, and `invalid` must stay 0.
- **FR3 (stationary / bounce):** If the same `{a,b}` pattern is sampled on
  two or more consecutive cycles, `pos` and `dir` must not change and
  `invalid` must read 0.
- **FR4 (illegal diagonal jump):** If `{a,b}` jumps directly between
  diagonal states (`00<->11` or `01<->10`) in one cycle, `invalid` must pulse
  to 1 for exactly one cycle following detection, then return to 0 (absent a
  further illegal jump), while `pos` and `dir` remain unchanged by that
  illegal transition.

No expected numeric waveforms are published here — the algorithm above (and
in `design_brief.md`) fully determines correct behavior, and grading is done
by simulating your submission against an independently built reference
design driven by the same stimulus.

## Submission

Submit your recovered design as a **single self-contained Verilog file** at:

```
submission/recovered_rtl.v
```

This file must contain **exactly one module**, named `quad_decoder`, matching
the pinned port list above. Do not include a testbench, package, or any
additional top-level modules.

A placeholder/naive stub already exists at that path — it is intentionally
incorrect (it always outputs zero) and is provided only to show the expected
file location and module skeleton. Replace it entirely with your real
recovered design.

## Constraints

- Your submission must be a **single file** at `submission/recovered_rtl.v`.
- Use only **synchronous, edge-triggered logic** driven by `posedge clk`. No
  additional clocks, latches, or asynchronous resets are permitted.
- `pos` must be exactly an 8-bit **signed** register that wraps using
  two's-complement arithmetic on overflow/underflow.
- The module name and port list must match the pinned interface **exactly**,
  including bit widths and directions.
- Do **not** modify any files under `inputs/` — they are reference-only.
- Your submission must compile cleanly with `iverilog` using standard,
  synthesizable Verilog-2001/2005 constructs.

## Evaluation

Evaluation is **behavioral**: your submitted RTL is compiled and simulated
with a testbench driving forward, reverse, stationary/bounce, and illegal
transition sequences, and its cycle-by-cycle outputs are compared against an
independently authored reference implementation of the same specification.
There are no shortcuts around correct behavior — static inspection of your
source is not how requirements are judged (only used to reject clearly
disallowed constructs). Focus on getting the cycle-accurate timing and the
Gray-code adjacency logic right.