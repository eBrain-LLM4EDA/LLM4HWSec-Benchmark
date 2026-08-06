# Design Brief: Undocumented Quadrature Decoder Block

## Background

This block was pulled from an undocumented motion-control subsystem. Field
engineers report that it monitors two Gray-coded position lines — commonly
labeled `a` and `b` in quadrature encoder datasheets — and produces some kind
of running position count plus a direction flag. There is also evidence of a
fault/error output, though its exact assertion behavior was never written
down. All that survives in the design database is a **flattened gate-level
netlist** (see `quadrature_netlist.v`) and an **obfuscated integration
wrapper** (see `quadrature_wrapper.v`) that instantiates it inside a larger
harness with renamed nets. Your task is to recover the intended word-level
behavior from these artifacts.

## Functional Intent (what the block is believed to do)

At a high level, this class of block works as follows:

- Each clock cycle, the block samples the current values of the two
  quadrature lines, `a` and `b`, together as a 2-bit pattern.
- It also remembers the pattern that was sampled on the *previous* cycle.
- Comparing the previous pattern to the current pattern tells you what kind
  of motion event (if any) just occurred:
  - **No change** — the mechanism did not move (or bounced back to the same
    reading before the next sample). No position update should occur.
  - **A single-bit change in one direction** — this corresponds to one
    legitimate "forward" step of the mechanism. The position count should
    advance by one, and a direction indicator should reflect "forward."
  - **A single-bit change in the other direction** — a legitimate "reverse"
    step. The position count should retreat by one, and the direction
    indicator should reflect "reverse."
  - **Both bits changing at once** — this cannot happen during normal
    mechanical motion of a two-phase quadrature sensor (you cannot skip a
    valid intermediate state in one sampling interval). This condition is
    considered an error/fault and must be flagged distinctly from ordinary
    motion, without corrupting the position or direction values that were
    already latched.

The specific mapping of which single-bit transitions count as "forward" vs.
"reverse" follows the standard Gray-code adjacency pattern used by two-phase
quadrature encoders, where only one line changes state at a time as the
mechanism moves in a consistent direction, and reversing the mechanism
retraces the same states in the opposite order. The exact adjacency table and
cycle-by-cycle timing relationship between sampled inputs and registered
outputs are not restated here in formula form — see "Authoritative
Specification" below.

## Netlist Structure (reverse-engineering hints)

The flattened netlist in `quadrature_netlist.v` is built entirely from
primitive gates and flip-flops, with no word-level operators, which is why
the higher-level intent is obscured. In general terms, the structure
contains:

- A pair of single-bit flip-flops holding the **current sampled state** of
  the two quadrature lines.
- A second pair of single-bit flip-flops holding the **previous sampled
  state** — i.e., what the current-state flops held one cycle earlier.
- A set of **XOR gates** comparing corresponding bits of the current and
  previous state pairs. These comparisons are what distinguish "no change,"
  "one bit changed," and "both bits changed" cases.
- A small **decode/multiplexer tree** built from AND/OR/NOT/MUX primitives
  that consumes the current and previous state bits (and the XOR comparison
  results) to decide, each cycle, whether the situation is a hold, a forward
  step, a reverse step, or an illegal jump.
- A small **ripple-style adder/subtractor** built from full-adder gate
  primitives that adjusts the position accumulator by +1, -1, or not at all,
  depending on the decode logic's decision.
- Separate single-bit registers holding the direction flag and the fault
  ("invalid transition") flag, updated according to the same decode logic.

None of this needs to be preserved structurally in your recovered design —
you are expected to reimplement the same *behavior* using clean, word-level
Verilog (e.g., comparing `{a,b}` to a registered previous value, and using a
small case/if structure keyed on the Gray-code adjacency relationship),
rather than instantiating gate primitives.

## Interface and Reset (informal restatement)

The recovered module must be named `quad_decoder` with a clock input, a
reset input, the two quadrature inputs `a` and `b`, a signed 8-bit position
output, a direction output, and an invalid/fault output — matching the
pinned port list exactly (see the Authoritative Specification below for the
literal port declaration).

Reset behavior is synchronous and active-high: asserting reset at a clock
edge causes the position, direction, and invalid outputs to be driven back
to their zero/idle values, observable from the next cycle onward. There is
no separate asynchronous reset path and no additional clock domains — this
is a single-clock, fully synchronous design.

All three outputs are registered (Moore) outputs: they change value on a
clock edge as a result of comparing sampled input states across two
consecutive cycles, not combinationally in the same cycle the raw input pins
change. The invalid/fault indication is expected to be transient — a
momentary flag rather than a level that lingers indefinitely — but the exact
number of cycles it holds, and the precise cycle-by-cycle relationship
between input sampling and output update, are timing details that must be
taken from the authoritative specification, not inferred from this brief.

## Authoritative Specification

This brief describes the *intent* of the block at a functional level only.
It intentionally does not restate exact bit-widths, exact cycle-latency
formulas, or the literal Verilog port declaration — those are pinned
precisely in `README.md` and `metadata.json` (field `interface`). If
anything in this brief appears to conflict with those documents, the pinned
`interface` text in `metadata.json` (and its restatement in `README.md`) is
authoritative and must be followed exactly when implementing
`submission/recovered_rtl.v`.