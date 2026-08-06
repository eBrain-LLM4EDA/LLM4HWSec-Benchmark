# Evaluation Harness: MUX-based ALU Datapath Recovery

## What This Grades

This harness behaviorally evaluates your submission at:

```
submission/recovered_rtl.v
```

It does **not** grade prose, comments, or coding style. The only thing
that matters is what your `recovered_datapath` module *does* when
simulated across a broad, deterministic sweep of `(a, b, sel)`
combinations.

## How It Works

1. **Existence check.** `evaluate.py` first confirms
   `submission/recovered_rtl.v` exists. If it does not, every requirement
   fails with a `SETUP` reason and the run exits non-zero.

2. **Static scan (fail-on-presence only).** The submission source is
   scanned for constructs that are *incompatible* with the pinned public
   constraint that the design must be purely combinational:
   - clocked `always @(posedge ...)` / `always @(negedge ...)` blocks,
   - `if` statements inside an `always` block with no matching `else`
     (a classic latch-inference pattern).

   These checks only ever cause a **FAIL** when the pattern is present;
   they never cause a pass by themselves. A correct combinational
   submission (e.g. built from `assign` statements or a fully-specified
   combinational `always @(*)` block with complete `if/else` coverage on
   every branch) will simply not trip either pattern.

3. **Compile + simulate.** `evaluate.py` compiles:
   - `submission/recovered_rtl.v` (your answer),
   - `evaluation/tb_compare.v` (the comparison testbench),

   together with `iverilog -g2012`, then runs the result with `vvp`. Your
   module is connected in the testbench via **explicit named ports**
   (`.a`, `.b`, `.sel`, `.y`) matching the pinned interface exactly:

   ```verilog
   module recovered_datapath(
       input  [7:0] a,
       input  [7:0] b,
       input  [1:0] sel,
       output [7:0] y
   );
   ```

   Any mismatch in module name, port names, port widths, or port
   directions will cause an elaboration error here, which is treated as
   a compile failure and fails **every** requirement (FR1–FR4, SR1–SR2)
   with a `compile failed: <first error line>` reason. This is by
   design: if we cannot simulate your module at all, no requirement can
   be judged as satisfied.

   Note that this harness computes the expected reference value directly
   inside `evaluation/tb_compare.v` using ordinary behavioral Verilog
   arithmetic (`a + b`, `a - b`, `a & b`, `a | b` on 8-bit operands,
   which naturally truncate to give modulo-256 wraparound) — it does
   **not** simulate `inputs/gate_netlist.v` as a side-by-side oracle for
   scoring. The expected values are simply the literal, word-level
   definitions given in the public functional requirements (FR2–FR4)
   below, applied per the pinned `sel` encoding (`00`=add, `01`=sub,
   `10`=and, `11`=or). This keeps grading entirely behavioral and
   independent of any particular gate-level styling.

4. **Vector sweep.** `evaluation/tb_compare.v` drives a fully
   deterministic stimulus set (no `$random`, no wall-clock dependence) —
   a fixed table of directed `(a, b)` pairs covering zero, all-ones,
   overflow/underflow boundaries, and non-commutative operand pairs,
   plus a fixed-seed pseudo-random sweep — applied identically at all
   four `sel` values (`00`, `01`, `10`, `11`). This produces well over
   200 total `(a, b, sel)` combinations, satisfying the task's sweep
   size requirement. For every vector, the testbench prints one line:

   ```
   VEC sel=<sel> a=<a> b=<b> rec=<rec_y> exp=<expected_y> match=<0 or 1>
   ```

   where `expected_y` is the behaviorally-computed reference value and
   `rec_y` is your module's output for the same inputs. `evaluate.py`
   parses these lines and derives every requirement verdict purely from
   this observed simulation output — there is no static "your code looks
   like an adder" heuristic anywhere in the scoring path.

## Requirement Mapping

- **FR1** — Compile/elaborate cleanly against the pinned interface, and
  contain no clocked or latch-inferring constructs (purely
  combinational, per the public constraints).
- **FR2** — For every vector with `sel=00`, your output must exactly
  match the reference (word-level: 8-bit `a+b` with wraparound).
- **FR3** — For every vector with `sel=01`, your output must exactly
  match the reference (word-level: 8-bit `a-b`, two's-complement
  wraparound).
- **FR4** — For every vector with `sel=10` (bitwise AND) and `sel=11`
  (bitwise OR), your output must exactly match the reference.

## Security Requirements

SR1 and SR2 are **directed spot-checks** drawn from the same simulated
output used for FR2/FR3. They exist to make specific classes of subtle
reverse-engineering mistakes fail loudly and unambiguously, even in the
unlikely case an aggregate FR check were satisfied by coincidence:

- **SR1** — checks non-commutative operand pairs (e.g. swapping `a` and
  `b`) at `sel=00` and `sel=01` against an independently Python-computed
  expected value, guarding against add/sub opcode confusion or reversed
  operand order (`b-a` instead of `a-b`).
- **SR2** — checks boundary overflow (`a=255,b=1` add) and underflow
  (`a=0,b=1` subtract) cases against Python-computed modulo-256 expected
  values, guarding against incorrect width recovery or a leaked/extra
  carry-out bit.

If your recovered module is genuinely functionally equivalent to the
literal FR2–FR4 definitions for all four operations across the full
sweep, SR1 and SR2 will pass automatically — they are not independent
hurdles beyond correct word-level recovery, just additional visibility
into *why* a submission failed when it does.

## Running Locally

```
python3 evaluation/evaluate.py
```

Requires `iverilog` and `vvp` on `PATH`. All checks print one line each
in the form:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <reason>
```

The process exits `0` only if every requirement passes.