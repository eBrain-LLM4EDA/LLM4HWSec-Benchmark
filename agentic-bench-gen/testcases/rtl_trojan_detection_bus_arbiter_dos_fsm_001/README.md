# RTL Design Review: 4-Master Bus Arbiter FSM

## Background

`inputs/bus_arbiter.v` implements a finite-state-machine-based arbiter that
grants a shared bus to one of four requesting masters at a time, using a
round-robin priority scheme. The module ports are:

| Port      | Direction | Width | Description                                            |
|-----------|-----------|-------|----------------------------------------------------------|
| `clk`     | input     | 1     | System clock                                            |
| `rst_n`   | input     | 1     | Active-low asynchronous reset                            |
| `req`     | input     | 4     | Per-master bus request lines (`req[i]` = master i wants bus) |
| `gnt`     | output reg| 4     | One-hot grant vector (`gnt[i]` = master i granted bus)    |
| `busy`    | output reg| 1     | Asserted while a grant is outstanding                     |

The intended behavior is documented in `inputs/design_brief.md`: the arbiter
should cycle through an `IDLE` state and four `GRANT0`..`GRANT3` states,
granting the bus to a requesting master for one cycle and then either
returning to `IDLE` (no other requests pending) or rotating to the next
requesting master in round-robin order.

## Your Task

You are performing a design review of this arbiter before it is signed off
for integration. Your job is to analyze the finite-state behavior of the
FSM implemented in `inputs/bus_arbiter.v` and answer the central liveness
question:

> **Does this FSM ever reach a state from which it stops granting the bus
> to any master, for all subsequent cycles, absent a full reset?**

You should treat this as an open-ended RTL analysis exercise: enumerate the
states the design actually implements (not just the ones described in the
design brief), trace the transition conditions between them, and determine
whether every reachable state can eventually lead back to servicing a
request, or whether some state acts as a terminal "sink" that the design
brief does not account for.

You may find it useful to:

- Read the `case` statement(s) controlling next-state logic in
  `inputs/bus_arbiter.v` directly, rather than relying solely on
  `inputs/design_brief.md`.
- Enumerate every state encoding value that appears in the RTL, including
  any that are not named in the design brief.
- Trace, for each state, which `req` values keep the FSM there, which move
  it to another documented state, and whether there is any `req` value for
  which no legitimate exit exists.
- Build a small testbench and simulate with `iverilog` / `vvp` (and
  optionally inspect synthesis-level structure with `yosys`) to confirm any
  hypothesis about a sequence of `req` values and reset conditions that
  drives the FSM into a state from which `gnt` stays `4'b0000` indefinitely.

**Do not modify `inputs/bus_arbiter.v`.** Your analysis and any simulation
harnesses you build for your own verification are not part of the graded
submission — only the report described below is graded.

## Deliverable

Write your findings to `submission/trojan_report.json`. This file must be
valid JSON and must match the following schema exactly:

```json
{
  "candidates": [
    {
      "state_name": "string — a state name/encoding literally present in inputs/bus_arbiter.v",
      "trigger_condition": "string — precise signal values/timing that drive the FSM into this state",
      "confidence": 0.0,
      "rationale": "string — why you believe this, referencing specific RTL constructs",
      "impact": "string — what happens to gnt/busy/masters once this state is reached"
    }
  ],
  "overall_assessment": "string",
  "recommended_fix": "string"
}
```

Requirements for a well-formed report:

- **`candidates`** must be a non-empty array. Each entry must have
  non-empty `state_name`, `trigger_condition`, `rationale`, and `impact`
  string fields, plus a numeric `confidence` field between `0.0` and `1.0`
  inclusive.
- Candidates must reference **concrete state names and signal
  conditions that literally appear in `inputs/bus_arbiter.v`** — e.g. an
  actual state encoding/label used in the `case` statement and an actual
  condition on `req`, `gnt`, or `busy` as written in the RTL. Generic or
  placeholder descriptions (e.g. "some unknown state", "a random request
  pattern") will not be considered a grounded finding.
- **`overall_assessment`** must explicitly answer whether the arbiter can
  reach a state from which it never asserts any `gnt` bit again for any
  subsequent `req` value (short of a full asynchronous reset), and justify
  the answer.
- **`recommended_fix`** should describe, in plain engineering terms, what
  RTL change(s) would eliminate any such condition you found (or state
  that none is needed, if that is your conclusion).

## Constraints

- Do not modify `inputs/bus_arbiter.v` or `inputs/design_brief.md`.
- Submit only `submission/trojan_report.json`.
- Your report should be self-contained: someone with only
  `inputs/bus_arbiter.v` and your report should be able to check your
  claims (e.g. by simulating the exact `req` sequence and reset sequence
  you describe with `iverilog`/`vvp`).
- Confidence scores must be numeric values in `[0.0, 1.0]`.

## Starting Point

A placeholder `submission/trojan_report.json` is included in this
repository so you can see the expected file layout and JSON shape. It is
**not** a valid analysis — it reflects a cursory review that found nothing
noteworthy. You are expected to replace its contents entirely with your
own findings after actually tracing the FSM's state encoding and
transition logic in `inputs/bus_arbiter.v`.

## Tooling

The following tools are available in the environment if you want to build
your own simulation harness to sanity-check a hypothesis:

- `iverilog` — compile Verilog sources (`-g2012` for SystemVerilog-2012
  constructs, if needed).
- `vvp` — run the compiled simulation and observe `gnt`/`busy`/state
  behavior over time via `$display`/VCD dump.
- `yosys` — inspect synthesized structure, generate state-transition
  reports, or dump the FSM if you prefer a structural approach.

Good luck — read the state-transition logic carefully rather than trusting
the design brief's summary alone.