# Evaluation Harness: PWM Dead-Time Generator Recovery

## Purpose

This harness grades `submission/recovered_rtl.v`, a reverse-engineered
Verilog implementation of a complementary PWM dead-time generator, by
**behavioral simulation** against an independently authored reference
design. It does not perform any static/textual analysis of the
submission's source — every requirement is judged solely from observed
simulation waveforms.

## Pinned interface (must match exactly)

```
module pwm_deadtime_gen (
    input  wire       clk,
    input  wire       rst,
    input  wire       en,
    input  wire [3:0] duty,
    output reg        pwm_hi,
    output reg        pwm_lo
);
```

- `clk`   — rising-edge system clock
- `rst`   — synchronous, active-high reset
- `en`    — active-high enable, sampled synchronously
- `duty`  — 4-bit programmable duty value (0–15)
- `pwm_hi`, `pwm_lo` — registered (Moore) outputs, high-side / low-side drive

The module name and every port name/width above must match exactly for
the submission to elaborate against `evaluation/tb_top.v`.

## How it works

1. `evaluate.py` verifies the three expected input artifacts exist under
   `inputs/` (`gate_netlist.v`, `obfuscated_rtl.v`, `design_brief.md`).
   These are read only for context; they are never used to grade the
   submission — grading is 100% behavioral.
2. `evaluate.py` verifies `submission/recovered_rtl.v` exists.
3. It compiles the submission together with the independently authored
   golden reference (`evaluation/reference_pwm.v`, module
   `reference_pwm_deadtime_gen`) and the shared testbench
   (`evaluation/tb_top.v`) using:

   ```
   iverilog -g2012 -o <tmp>/sim.vvp submission/recovered_rtl.v \
       evaluation/reference_pwm.v evaluation/tb_top.v
   ```

4. It runs the compiled simulation with `vvp <tmp>/sim.vvp`.
5. The testbench drives both the submission's `pwm_deadtime_gen`
   instance and the reference's `reference_pwm_deadtime_gen` instance
   from the same `clk`/`rst`/`en`/`duty` stimulus, and on every relevant
   clock edge prints one machine-parseable probe line of the form:

   ```
   PROBE <requirement_id> <PASS|FAIL> <detail>
   ```

6. `evaluate.py` parses all `PROBE` lines from stdout and aggregates
   them per requirement id. A requirement id is reported as
   `[TEST] PASS: <id>` only if **every** probe line emitted for that id
   was `PASS`; otherwise it is reported as
   `[TEST] FAIL: <id>: <reason>`. If no probe lines are found at all for
   a given id (e.g. the simulation crashed or timed out before
   completing that scenario), it is also treated as a `FAIL` (not
   `SETUP`, since the harness files themselves are present).

## Requirements checked

| ID  | Type       | What it checks |
|-----|------------|-----------------|
| FR1 | functional | duty=8, en=1 held, one-cycle reset then release: pwm_hi high for cnt=2..7, pwm_lo high for cnt=10..15, matched cycle-for-cycle against the reference over 4+ periods. |
| FR2 | functional | For every duty=0..15 with en=1 (and additional fixed alternating-en and LFSR-en patterns), pwm_hi and pwm_lo never overlap and match the reference over 2+ periods per duty. |
| FR3 | functional | duty=15: pwm_lo never asserts, pwm_hi asserts for cnt=2..14. duty=0,1,2: pwm_hi never asserts. Matched against reference. |
| FR4 | functional | With en=0 held for 8+ consecutive cycles starting at several distinct phase offsets after reset, the counter freezes and pwm_hi/pwm_lo settle to (and hold at) the values implied by the held cnt/duty, matching the reference throughout the hold and for several cycles after resuming. |
| SR1 | security   | Across duty=0..15 combined with both deterministic fixed en patterns (held-high, alternating) and pseudo-random (fixed-seed) `en` toggling over 3+ periods per duty, `pwm_hi & pwm_lo` is never simultaneously high on the submission, for any cycle. Any overlap is an immediate fail regardless of other results. |
| SR2 | security   | For duty=3..13, the dead-time gap is measured at both the period-start boundary (before pwm_hi may assert) and the duty-transition boundary (before pwm_lo may assert), and must be exactly 2 cycles wide at each boundary, independently asserted and cross-checked against the reference's captured waveform. |

Every requirement above is judged purely by comparing simulated
`pwm_hi`/`pwm_lo` waveforms of the submission against the reference
(and, for SR1, an absolute overlap invariant) — never by inspecting the
submission's source text.

## Exit code semantics

- Exit code **0**: every requirement (`FR1`–`FR4`, `SR1`–`SR2`) printed
  `[TEST] PASS: <id>`.
- Exit code **1**: at least one requirement printed
  `[TEST] FAIL: <id>: <reason>` — this includes missing input/submission
  files (`SETUP` failures), compilation failures, simulation
  crashes/timeouts, or any observed behavioral mismatch/overlap.

## Running manually

```
cd <repo-root>
python3 evaluation/evaluate.py
```

Ensure `iverilog` and `vvp` are on `PATH`. All simulation artifacts are
written to a temporary directory and never into `inputs/` or
`submission/`.