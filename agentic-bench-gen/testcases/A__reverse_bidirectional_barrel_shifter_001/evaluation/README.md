# Reverse-Engineered Barrel Shifter — Evaluation

## What this evaluates

`evaluate.py` grades `submission/recovered_rtl.v`, which must define a
combinational module `barrel_shifter_top` matching the pinned interface
(`data_in[7:0]`, `amount[2:0]`, `direction`, `mode[1:0]`, `data_out[7:0]`).

Grading is purely **behavioral (simulation-based)**. The submission is
never inspected for coding style, module structure, or the presence of
`case`/`generate`/mux-tree constructs — any synthesizable RTL that
produces the correct `data_out` for every input vector passes.

## How it works

1. `evaluate.py` confirms `inputs/net_shifter_flat.v`,
   `inputs/design_brief.md`, and `submission/recovered_rtl.v` all exist.
   A missing file emits `[TEST] FAIL: SETUP: <path> not found` and the
   run exits non-zero immediately.
2. It compiles, with `iverilog`:
   - `inputs/net_shifter_flat.v` (the flattened reference netlist,
     instantiated in the testbench as `u_ref`),
   - `submission/recovered_rtl.v` (the recovered RTL, instantiated as
     `u_dut`),
   - `evaluation/tb_top.v` (the testbench).
3. It runs the resulting `vvp` executable. The testbench
   (`evaluation/tb_top.v`) exhaustively drives **all 8192 combinations**
   of `data_in` (0–255) × `amount` (0–7) × `direction` (0–1) × `mode`
   (00/01/10/11), applying each vector with a `#1` settle delay and
   comparing `u_ref.data_out` against `u_dut.data_out` on every vector
   (purely combinational — no clock, zero cycles of extra latency).
4. The testbench prints three deterministic summary lines that
   `evaluate.py` parses:
   - `TOTAL_VECTORS=8192 MISMATCHES=<n> FIRST_MISMATCH=<...|NONE>` —
     global exhaustive result across the entire input space.
   - `MODE11_MISMATCHES=<n> MODE11_TOTAL=2048` — result restricted to
     the 2048 vectors where `mode=11`.
   - `SR2_MISMATCHES=<n> SR2_TOTAL=<n>` — result restricted to vectors
     where `mode=01`, `direction=0` (left), and `data_in[7]=1`, tallied
     by a **dedicated, independent counter pass** in the testbench that
     is computed entirely separately from — and is not derived from,
     gated by, or dependent on the outcome of — the global exhaustive
     tally or any other requirement's result. This line alone fully
     determines SR2's PASS/FAIL.

## Requirement mapping

| Requirement | What is checked |
|---|---|
| **FR1** (logical shift, mode=00) | Subsumed by the global exhaustive comparison: `MISMATCHES==0` implies every mode=00 vector across all `amount`/`direction`/`data_in` matches the reference netlist bit-for-bit. |
| **FR2** (arithmetic shift, mode=01) | Same global comparison; mode=01 right-shift sign-extension and left-shift zero-fill vectors are included in the full 8192-vector sweep. |
| **FR3** (rotate, mode=10) | Same global comparison; all rotate-left/rotate-right vectors for `amount` 0–7 are included. |
| **FR4** (bit-exact equivalence, all modes) | Directly the global exhaustive result: PASS only if `MISMATCHES==0` over the full 8192-vector space, with the testbench settling each vector combinationally (no additional propagation cycles). |
| **SR1** (mode=11 don't-care resolution) | PASS only if `MODE11_MISMATCHES==0` across all 2048 mode=11 vectors, i.e. the submission reproduces the reference netlist's actual resolved output for the "unused" encoding rather than leaving it as an unconstrained don't-care. A static scan additionally flags an explicit `x`-valued literal assigned under a `mode==2'b11` branch as a belt-and-suspenders fail-on-presence signal; this can only make a submission fail, never make an otherwise-mismatching submission pass. |
| **SR2** (no false sign-extension on left shift) | PASS only if `SR2_MISMATCHES==0`, read directly from the **dedicated, isolated** SR2 counter emitted by the testbench for the subset of vectors with `mode=01`, `direction=0`, `data_in[7]=1`. This counter is computed by its own standalone pass over that vector subset and is entirely independent of the global `MISMATCHES` tally and of FR1–FR4's outcome — a submission that reintroduces sign-extension only on this specific left-shift path (while leaving everything else correct, or vice versa) is detected purely by this isolated subset check, with no dependence on any other requirement failing first. |

All six requirement checks are behavioral, driven by simulated I/O
comparison against the reference netlist — none of them require any
particular internal RTL structure.

## Markers and exit codes

Each requirement emits exactly one line:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <reason>
```

for `requirement_id` in `{FR1, FR2, FR3, FR4, SR1, SR2}`.

- If compilation fails, every requirement id emits
  `[TEST] FAIL: <id>: compile failed: <stderr summary>`.
- If simulation times out or crashes, every requirement id emits
  `[TEST] FAIL: <id>: run crashed/timed out`.
- `evaluate.py` exits `0` only if all six checks print `PASS`;
  otherwise it exits `1`.