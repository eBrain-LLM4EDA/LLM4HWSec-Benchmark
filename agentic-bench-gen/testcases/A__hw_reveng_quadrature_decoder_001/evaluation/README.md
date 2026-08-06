# Quadrature Decoder Recovery — Evaluation

## What is graded

`evaluate.py` grades the file at `submission/recovered_rtl.v`. It does **not**
edit or grade anything under `inputs/`; those files (`quadrature_netlist.v`,
`quadrature_wrapper.v`, `design_brief.md`) are reference-only inputs describing
the flattened gate-level implementation you were asked to reverse-engineer.

Your submission must contain exactly one module named `quad_decoder` with the
pinned port list:

```verilog
module quad_decoder (
    input  wire        clk,
    input  wire        rst,
    input  wire        a,
    input  wire         b,
    output reg  signed [7:0] pos,
    output reg          dir,
    output reg          invalid
);
```

(Port order/types must match the pinned interface in the task specification
exactly — bit widths, `signed`, and direction all matter.)

## How grading works

1. **Setup checks.** The evaluator first confirms all three `inputs/` files
   exist (informational — they are not modified or re-graded) and that
   `submission/recovered_rtl.v` exists. Either missing file is a `SETUP`
   failure.

2. **Static scan (SR3).** Before simulating, `submission/recovered_rtl.v` is
   scanned for forbidden constructs that would let a submission trivially
   force a pass regardless of stimulus: `$stop`, `$finish`, `force`,
   `deposit`, and `` `ifdef TESTBENCH ``. Presence of any of these is an
   immediate FAIL for SR3, independent of simulated behavior.

3. **Compilation.** The submission is compiled together with
   `evaluation/tb_quad_decoder.v` using `iverilog`. If compilation fails, every
   behaviorally-graded requirement (FR1–FR4, SR1–SR2) is reported as FAILing
   with a summary of the compiler error; SR3's static result is unaffected.

4. **Simulation.** The resulting design is run under `vvp` with a timeout. The
   testbench drives `clk`/`rst`, then applies a fixed sequence of `{a,b}`
   stimulus patterns covering:
   - a forward Gray-code run (`00,01,11,10,00`, repeated),
   - a reverse Gray-code run (`00,10,11,01,00`, repeated),
   - a stationary/bounce segment (same pattern held across multiple cycles),
   - illegal diagonal jumps (`00<->11`, `01<->10`) embedded mid-sequence,
     followed by legal and non-illegal cycles.

   The testbench prints one `PROBE:<label>:<cycle>:<pos>:<dir>:<invalid>` line
   per cycle after reset release, plus a terminating `PROBE:DONE` marker.

5. **Comparison against an independent reference model.** `evaluate.py`
   contains a small pure-Python model of the intended Gray-code decoder
   behavior, computed directly from the pinned interface semantics (Moore
   outputs, one cycle of latency, synchronous active-high reset, Gray-code
   forward/reverse adjacency, single-cycle `invalid` pulse). This model is run
   over the *same* stimulus sequence embedded in the testbench and its
   per-cycle expected values are compared against the parsed `PROBE` lines.
   Each functional and security requirement is judged from this comparison —
   never from how the submitted source is written.

## Requirements checked

- **FR1** — forward Gray-code run: `pos` increments by 1 per legal step,
  `dir` reads 1, `invalid` reads 0 throughout.
- **FR2** — reverse Gray-code run: `pos` decrements by 1 per legal step,
  `dir` reads 0, `invalid` reads 0 throughout.
- **FR3** — stationary/bounce segment: `pos` and `dir` hold, `invalid` stays 0.
- **FR4** — diagonal jump: `invalid` pulses high for exactly one cycle and
  `pos`/`dir` are unaffected by the illegal transition.
- **SR1** — `pos` and `dir` are bitwise identical to their pre-transition
  values on the illegal edge and the cycle immediately after.
- **SR2** — `invalid` is asserted for exactly one cycle per illegal
  transition and stays low for at least 3 subsequent cycles absent a new
  illegal transition (no sticky/re-asserting fault flag).
- **SR3** — static scan of the submitted RTL for forbidden
  pass-forcing/non-synthesizable constructs.

## Pass/fail semantics

- Every requirement above emits exactly one line:
  `[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>`.
- The process exits `0` only if every requirement line is `PASS`.
- Any compile failure, simulation timeout/crash, or mismatch against the
  reference model counts as a genuine FAIL for the affected requirement(s) —
  it is never reported as `SETUP` unless the missing artifact is one of the
  fixed input/harness files.

## Notes for implementers

- Only standard synthesizable Verilog-2001 constructs, synchronous
  `posedge clk` logic, and the pinned port list are permitted. No additional
  clocks, latches, or asynchronous resets.
- Do not modify any file under `inputs/`; they are read-only reference
  material for your analysis and are not themselves graded.
- The reference model used for comparison is written independently from the
  pinned interface text — matching a particular internal netlist style or
  variable naming is irrelevant; only cycle-accurate output behavior at the
  `quad_decoder` boundary is judged.