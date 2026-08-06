# Hamming(7,4) SEC Decoder — Evaluation Harness

## What this evaluates

This harness grades `submission/recovered_rtl.v`, a candidate reverse-engineered
implementation of the combinational decoder module `recovered_decoder`, against
the reference behavior found in `inputs/flattened_netlist.v`. The reference
netlist is treated as a black box: we never inspect its internal structure at
grading time, we only compare externally observable behavior.

Grading is purely behavioral (simulation-based), per the task's evaluation
contract. No requirement passes because of how the submitted source is
written — only because its simulated outputs match the reference's simulated
outputs.

## How grading works

1. **Presence checks.** `evaluate.py` first verifies that
   `inputs/flattened_netlist.v`, `inputs/design_brief.md`, and
   `submission/recovered_rtl.v` all exist. Any missing file is a `SETUP`
   failure and grading stops early.

2. **Static banned-construct scan (fail-on-presence only).** The submission
   source is scanned for `always @(posedge ...)` / `always @(negedge ...)`
   blocks. The module under test is required to be purely combinational (no
   clock, no internal state), so presence of a clocked always-block is a
   disqualifying construct. This scan can only ever produce a FAIL — it never
   causes a PASS by itself. A submission with no such construct simply does
   not trip this check, regardless of naming, formatting, or internal
   structure.

3. **Compilation.** `evaluate.py` invokes `iverilog` to compile, together:
   - `inputs/flattened_netlist.v` (the reference module, `flattened_netlist`),
   - `submission/recovered_rtl.v` (the candidate module, `recovered_decoder`),
   - `evaluation/tb_top.v` (the generated testbench).

   If compilation fails for any reason (syntax error, missing module,
   port-list mismatch, etc.), every requirement is reported as FAILing with a
   compile-error summary, and the process exits non-zero.

4. **Simulation.** The compiled design is run under `vvp`. The testbench
   (`evaluation/tb_top.v`) instantiates both the reference module and the
   submitted module side by side, sharing the same driven `codeword` input.
   It exhaustively sweeps all 128 values of `codeword` (`7'b0000000` through
   `7'b1111111`), applying each value, waiting a fixed `#5` settling delay
   (no clock involved, matching the pinned interface's purely-combinational,
   zero-latency timing discipline), and then sampling `data`,
   `corrected_codeword`, and `error_detected` from both instances. For each of
   the 128 codewords the testbench prints exactly one fixed-format,
   machine-parseable line reporting the codeword value and both instances'
   sampled outputs.

5. **Parsing and requirement derivation.** `evaluate.py` parses all 128
   printed lines with a fixed regex. If fewer than 128 lines are recovered
   (e.g. the simulation crashed, timed out, or `$finish` was never reached),
   every requirement is treated as failing due to a run crash/timeout, not as
   a SETUP issue. Otherwise, each functional and security requirement below
   is derived purely from comparing the parsed reference values against the
   parsed submission values across the appropriate subset of the 128 rows.

## Requirement-to-check mapping

- **FR1 (full exhaustive equivalence):** all three outputs (`data`,
  `corrected_codeword`, `error_detected`) must match the reference on all 128
  codewords. Any mismatch anywhere fails this requirement.

- **FR2 (error-free codewords pass through unchanged):** restricted to the
  subset of the 128 rows where the *reference* reports `error_detected == 0`
  (the valid, error-free codewords). On these rows the submission must also
  report `error_detected == 0` and `corrected_codeword == codeword`
  (unchanged).

- **FR3 (single-bit errors are corrected):** restricted to the subset of rows
  where the *reference* reports `error_detected == 1` (codewords containing
  exactly one flipped bit relative to some valid codeword). On these rows the
  submission must report `error_detected == 1` and its
  `corrected_codeword` must match the reference's corrected codeword
  bit-for-bit.

- **FR4 (interface and combinational-only structure):** the submission must
  define a module compiling cleanly under `iverilog` with the pinned port
  list (elaboration against the testbench's instantiation enforces this), and
  must not contain a clocked `always` block (static fail-on-presence scan).

- **SR1 (no parity/data-bit confusion):** restricted to the error-free
  (reference `error_detected == 0`) subset, the submission's `data[3:0]`
  must exactly match the reference's `data[3:0]` on every such row. Because
  a swapped parity/data mapping can coincidentally look correct on clean
  inputs alone, this check is deliberately paired with SR2 below — together
  they only pass if the *same* extraction convention holds both before and
  after correction is exercised by injected single-bit errors.

- **SR2 (correct syndrome-to-bit-position mapping):** restricted to the
  single-bit-error (reference `error_detected == 1`) subset, the
  submission's `corrected_codeword` must exactly match the reference's
  `corrected_codeword` on every such row. A reversed or permuted
  syndrome-bit ordering will flip the wrong bit for a detectable portion of
  these rows and is caught here.

## Determinism

The testbench exhaustively and deterministically sweeps all 128 possible
7-bit codewords in a fixed order with a fixed settling delay; there is no
randomness, no wall-clock dependence, and no reliance on tool-specific
scheduling behavior beyond standard blocking-assignment delta-cycle settling
within `iverilog`/`vvp`.