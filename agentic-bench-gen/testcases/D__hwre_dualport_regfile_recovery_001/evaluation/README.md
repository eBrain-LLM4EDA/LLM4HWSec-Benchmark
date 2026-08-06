# Evaluation Harness: Dual-Read Register File Recovery

This directory contains the automated grader for
`hwre_dualport_regfile_recovery_001`.

## What gets graded

The participant submits a single file:

```
submission/recovered_rtl.v
```

containing exactly one module named `reg_file_recovered` with the pinned
port list from `public_spec.interface`. `evaluate.py` is the sole entry
point and is the only thing invoked by the pipeline.

The reference artifacts under `inputs/`:

- `inputs/design_brief.md`
- `inputs/gate_netlist.v`
- `inputs/obfuscated_wrapper.v`

are **read-only reference material for the human/Expert** describing the
ground-truth timing contract. `evaluate.py` verifies these three files
exist (failing with a `SETUP` marker if any is missing), but it never
compiles them against the submission and never opens them as Verilog
sources for any toolchain invocation. They are not used to decide
PASS/FAIL. Grading is entirely behavioral, driven by a generated
testbench instantiating the submission directly, plus two narrowly-scoped
fail-on-presence static scans described below.

## How grading works

1. **Setup check.** Confirm `inputs/gate_netlist.v`,
   `inputs/obfuscated_wrapper.v`, `inputs/design_brief.md`,
   `submission/recovered_rtl.v`, and `evaluation/tb_regfile.v` all exist.
   Any missing file emits `[TEST] FAIL: SETUP: <path> not found` and the
   process exits 1 immediately.

2. **Static fail-on-presence scans (SR1/SR2 helper checks only).**
   `evaluate.py` reads the submission source text (after stripping
   comments) and searches for two banned constructs:
   - An extra clocked register stage driving `rdata0`/`rdata1` directly
     (e.g. `always @(posedge clk) ... rdata0 <= ...`), which would add a
     cycle of read latency forbidden by SR1.
   - A combinational bypass multiplexer that compares `raddr0`/`raddr1`
     against `waddr` together with `we` and selects `wdata` directly
     (e.g. `assign rdata0 = (raddr0==waddr && we) ? wdata : mem[raddr0];`),
     which is the racy collision-forwarding anti-pattern forbidden by SR2.

   These are pure fail-on-presence checks: they can only ever cause a
   `FAIL`, never cause a `PASS`. A submission that does not contain either
   pattern is unaffected by this step, regardless of how it is otherwise
   structured or named.

3. **Deterministic stimulus generation.** A single Python function
   (`build_stimulus`) generates a fixed 600-cycle sequence of
   `rst/we/waddr/wdata/raddr0/raddr1` values using a seeded linear
   congruential generator (seed = 42), plus a few explicitly scripted
   opening cycles (writes of `0x00,0xFF,0xA5,0x3C` to addresses `0..3`,
   a reset pulse, and a post-reset read-only cycle). Periodic forced
   collisions (`raddr0==waddr` every 10 cycles, `raddr1==waddr` every 13
   cycles) and forced independent-read cycles (every 7 cycles) ensure
   FR3/FR4/SR2-relevant scenarios are always exercised, including at
   cycle 0. This same stimulus is written to a plain-text file and
   consumed identically by both the Python reference model and the
   Verilog testbench, so there is never a chance of the two diverging
   due to two independent random number generators.

4. **Python reference model.** A pure-Python behavioral model of the
   4x8 register file (synchronous active-high reset with priority over
   writes, single synchronous write port, two combinational read ports
   with natural write-forwarding) computes the expected `(rdata0,
   rdata1)` pair after every simulated clock edge, plus the exact
   pre-edge memory snapshot needed to validate zero-latency mid-cycle
   address changes.

5. **Compile and simulate.** `evaluate.py` invokes:

   ```
   iverilog -g2012 -o <tmp>/sim.vvp submission/recovered_rtl.v evaluation/tb_regfile.v
   vvp <tmp>/sim.vvp +STIMFILE=<tmp>/stimulus.txt
   ```

   with explicit timeouts. The testbench (`tb_regfile.v`) instantiates
   `reg_file_recovered` by the exact pinned port list, and does all of its
   work inside a **single `initial` block** sequenced purely with
   blocking statements: it first reads the `+STIMFILE=<path>` plusarg,
   opens the file, `$fscanf`s `num_cycles` and every stimulus row into
   the `stim_*` arrays, closes the file, and only THEN — in the very same
   initial block, continuing in program order — initializes the drive
   signals from `stim[0]` and begins the drive/wait/probe loop for cycle
   0 onward.

   **Why this matters (the race fix).** A previous version of this
   harness loaded the stimulus file in one `initial` block and drove the
   DUT from a *second, separate* `initial` block, with the two
   synchronized only by a bare `#1` delay inserted before the drive block
   began stepping cycles. Because both `initial` blocks start executing
   at simulation time 0, this created a genuine race condition: the
   drive/probe block could reach and execute its cycle-0 drive step and
   its first `posedge clk` wait before the loading block's `$fscanf` loop
   had finished populating the `stim_rst/we/waddr/wdata/raddr0/raddr1`
   arrays, depending on statement-scheduling order inside the same time
   step. The most visible symptom was a `PROBE` line for cycle 0 (and,
   by the same mechanism, the very first collision cycle at cycle 0)
   simply never being emitted — not because the DUT behaved incorrectly,
   but because the testbench's own internal race dropped or corrupted
   the stimulus values it was supposed to drive at that cycle. This
   caused a fully spec-compliant, behaviorally correct golden submission
   to be rejected with `missing PROBE for cycle 0` / `missing PROBE for
   collision cycle 0` errors that had nothing to do with the submission's
   actual read/write/reset/collision timing.

   The fix merges both phases into **one** `initial` block with purely
   sequential blocking statements: load stimulus first (open file,
   `$fscanf` every row, close file), then — still inside that same
   process, still at the same point in program order, with zero
   intervening `#` delays or `@` waits between the last stimulus load
   statement and the first drive statement — initialize cycle-0's drive
   signals and enter the drive/wait-for-posedge/settle/probe loop. There
   is no second `initial` or `always` block anywhere in `tb_regfile.v`
   that touches `rst`, `we`, `waddr`, `wdata`, `raddr0`, or `raddr1`
   (only the clock generator, which drives `clk` alone, runs
   concurrently). Because the entire load-then-drive sequence executes
   as one uninterrupted program-order sequence within a single process,
   there is no simulation-time window in which the drive loop can run
   before the stimulus arrays are fully populated — the race is
   eliminated structurally, not merely delayed, so a correct submission
   always receives a `PROBE` (and, where applicable, a `PROBE_MID`) for
   cycle 0 and for every collision/independent-read cycle including
   cycle 0.

   For every cycle `i` the testbench prints:

   ```
   PROBE <cycle> <rdata0_hex> <rdata1_hex>
   ```

   immediately after the rising edge settles, and then — without waiting
   for another clock edge — toggles `raddr0`/`raddr1` to the *next*
   cycle's addresses and prints:

   ```
   PROBE_MID <cycle> <rdata0_hex> <rdata1_hex>
   ```

   to directly probe zero-latency combinational read behavior (SR1). The
   run ends with a `DONE` marker.

6. **Compile/run failure handling.** If `iverilog` fails to compile the
   submission, or `vvp` crashes or times out, or the `DONE` marker is
   never observed, every behaviorally-graded requirement
   (`FR1, FR2, FR3, FR4, SR1, SR3`) is failed with a reason string
   including a concise summary of the compiler/runtime error — never a
   `SETUP` marker, since the input files and harness files are present;
   this is a defect in the submission itself. `SR2` is still evaluated
   independently since it is purely static.

7. **Requirement grading.** The parsed `PROBE`/`PROBE_MID` lines are
   compared cycle-by-cycle against the Python reference model:
   - **FR1** — the four scripted opening write-then-read cycles
     (addresses 0..3, data `0x00/0xFF/0xA5/0x3C`) must match exactly.
   - **FR2** — the cycle immediately following the reset pulse must read
     back `0x00` on both ports at the swept addresses, matching the
     reference.
   - **FR3** — every cycle in the stimulus where a write commits and
     `raddr0` or `raddr1` equals `waddr` on that same edge must show the
     *new* `wdata` value on the affected port(s), matching the reference
     exactly (old-value or otherwise-wrong observations fail this check).
   - **FR4** — every cycle where `raddr0 != raddr1` must show each port
     independently matching the reference's value for its own address.
   - **SR1** — combines the static scan result (no extra registered
     read stage present) with the behavioral `PROBE_MID` comparison
     (mid-cycle address changes must reflect the new address immediately,
     with zero additional clock edges, matching the reconstructed
     pre-edge/post-edge memory snapshot for the *next* cycle's addresses
     applied to the *current* cycle's committed state).
   - **SR2** — purely the static bypass-mux scan result described above.
   - **SR3** — the reset-pulse cycle itself, and the immediately following
     read-only cycle, must show all-zero reads on both ports with no
     stale data, matching the reference exactly.

## Numeric METRICS line

Immediately before the final `[TEST]` verdict lines are guaranteed to have
all been printed, `evaluate.py` prints one additional line of the form:

```
METRICS: {"cycle_accurate_match_rate": <float>, "functional_equivalence": <float>, "structural_match_accuracy": <float>, "word_recovery_rate": <float>}
```

These four fields correspond directly to the task specification's
`evaluation.metrics` and are computed as follows:

- **cycle_accurate_match_rate** — fraction of all 600 simulated cycles
  whose `PROBE` line exactly matches the Python reference model's
  `(rdata0, rdata1)` for that cycle.
- **word_recovery_rate** — fraction (0/4 .. 4/4) of the four scripted
  single-address write-then-read opening cycles (addresses 0..3) whose
  `PROBE` exactly matches the reference.
- **structural_match_accuracy** — `1.0` if neither static fail-on-presence
  scan (SR1's extra-register check, SR2's bypass-mux check) found its
  banned construct, else `0.0`. This mirrors the specification's framing
  of this metric as a fail-on-presence-only structural check.
- **functional_equivalence** — fraction (0/4 .. 4/4) of `FR1`–`FR4` that
  individually resolved to PASS.

**These METRICS values are informational only.** They are printed for
visibility/analytics and are never consulted to decide PASS/FAIL for any
requirement. The sole authority for PASS/FAIL is the per-requirement
`[TEST] PASS`/`[TEST] FAIL` marker described below; a submission with a
high `cycle_accurate_match_rate` but one failing requirement still fails
overall.

## Marker format

Every requirement in the requirement map emits exactly one line of the
form:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <brief reason>
```

Requirement IDs are: `FR1, FR2, FR3, FR4, SR1, SR2, SR3`. No requirement
is ever skipped; each one always resolves to PASS or FAIL, even when a
compile/run failure forces cascading failures across the behaviorally
graded set.

## Exit codes

- **Exit 0**: every requirement above printed `[TEST] PASS`.
- **Exit 1**: at least one requirement printed `[TEST] FAIL`, including
  the case where `submission/recovered_rtl.v` (or any required input
  file) is missing, in which case a single `[TEST] FAIL: SETUP: ...`
  line is printed and the process exits 1 immediately without attempting
  compilation.

## Notes for maintainers

- The stimulus generator and the Python reference model live entirely
  inside `evaluate.py`; there is no external "expected values" table to
  keep in sync — everything is computed algorithmically from the shared
  seeded LCG stream, so regenerating or extending the stimulus does not
  require hand-maintained golden vectors.
- The two static scans exist solely to catch banned constructs that are
  difficult or impossible to prove absent purely by behavioral
  simulation over a finite vector set (e.g. a submission could pass all
  600 randomized cycles by accident while still containing a latent
  racy bypass mux that only misbehaves under simulation delta-ordering
  the testbench doesn't happen to trigger). They are intentionally
  narrow (anchored to the literal banned construct shapes) so that they
  never reject a correct, differently-styled submission.
- `evaluation/tb_regfile.v` must not be edited by participants; it is
  shipped as part of the evaluation harness and instantiates the
  submission purely through the pinned public port list. Its stimulus
  loading and DUT driving logic live in a **single** `initial` block
  sequenced entirely with blocking statements (load-then-drive, in that
  order, in one process) specifically so that no simulation-time race
  between file loading and DUT driving can ever cause a probe (including
  the cycle-0 probe, and the cycle-0 collision probe) to go missing for
  a correct submission. Any future modification to this testbench must
  preserve the single-initial-block sequencing invariant, or the
  cycle-0/collision-cycle-0 probe-loss bug described above can silently
  reappear.
- `inputs/gate_netlist.v`, `inputs/obfuscated_wrapper.v`, and
  `inputs/design_brief.md` are read only for the setup existence check;
  they are never passed to `iverilog`, never instantiated, and never
  otherwise involved in compiling or simulating the submission.