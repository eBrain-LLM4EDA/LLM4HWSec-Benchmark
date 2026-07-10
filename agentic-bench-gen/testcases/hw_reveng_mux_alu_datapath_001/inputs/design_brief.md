# Design Brief: Flattened ALU-Style Datapath

## Origin

The netlist under `inputs/gate_netlist.v` was produced by an automated
synthesis/bit-blasting flow that takes a small word-level combinational
datapath and expands every word-level operator into primitive logic gates
(`and`, `or`, `xor`, `not`, `buf`, etc.). The result is functionally
identical to the original design, but the word-level intent — which
operation is being performed, and how the select bits choose between
operations — is no longer visible in the source text. This is a common
situation when working with netlists recovered from synthesis output,
gate-level exports, or IP where only the flattened structure is available.

## What the Design Does, at a High Level

The datapath has two 8-bit data operands (`a`, `b`), a 2-bit operation
select (`sel`), and produces a single 8-bit result (`y`). It implements
**four ALU-style operations** commonly found in small processor datapaths
and arithmetic/logic units: a mix of **arithmetic** operations and
**bitwise logical** operations over the two operands. Which specific four
operations, and which 2-bit `sel` encoding activates each one, is exactly
what you are being asked to determine — this brief will not tell you.

## Structural Hints

A few observations about how bit-blasting tools typically expand
word-level operators may help you navigate the netlist faster:

- **Bitwise operations** (AND, OR, XOR, etc.) expand into independent
  per-bit gate clusters. Each output bit depends *only* on the
  corresponding input bits at the same bit position — there is no
  signal flow between bit slices.

- **Arithmetic operations** (addition, subtraction, increment/decrement,
  comparisons, etc.) generally cannot be computed independently per bit.
  They require a **carry (or borrow) chain** that propagates information
  from the least-significant bit slice toward the most-significant one.
  If you see a wire threading from bit slice `i` into bit slice `i+1`
  that is *not* simply one of the raw operand bits, that is a strong
  signal you are looking at carry logic, not a purely bitwise operation.

- Subtraction is frequently implemented in gate-level hardware as
  addition with one operand conditionally inverted, plus an injected
  carry-in — a classic two's-complement trick. If you find a small
  cluster of XOR gates conditioned on part of `sel` sitting *just before*
  a carry chain, consider what value carry-in must take for the chain to
  compute a subtraction versus a plain addition.

- Bit-blasting flows frequently interleave the control/select logic with
  the arithmetic carry logic when they lower a multiplexer over multiple
  results down to gates. Don't expect the "adder" and the "mux" to appear
  as clean, separated blocks in the source — trace signal names and
  fan-in/fan-out relationships rather than relying on file layout or
  comments.

## Recommended Approach

1. Simulate first, read structure second. Use
   `inputs/testbench_template.v` (or a testbench of your own) to exercise
   `gate_netlist` with `iverilog`/`vvp` for a range of hand-chosen
   `(a, b, sel)` values before committing to any hypothesis about what a
   particular gate cluster computes.

2. Vary one input at a time. Hold `a` and `sel` fixed and sweep `b` (and
   vice versa) to see whether `y` behaves like an independent per-bit
   function of `a` and `b`, or whether it shows carry/borrow-like
   propagation (e.g. changing a low bit of `b` flips several bits of `y`,
   not just the corresponding bit).

3. Sweep `sel` across all four of its possible values for a few fixed
   `(a, b)` pairs and observe how `y` changes. Do not assume any
   particular binary encoding for `sel` corresponds to any particular
   operation — infer the mapping empirically from simulated behavior.

4. Pay close attention to non-commutative cases: choose `a` and `b` such
   that swapping them changes the arithmetic result (e.g. `a` clearly
   larger than `b`, and vice versa) to make sure you recover not just
   *which* arithmetic operation is present but the *correct operand
   order*.

5. Once you have a working hypothesis for all four operations and their
   `sel` encodings, write it up as clean, word-level Verilog and verify it
   against the reference netlist yourself — across a wide range of
   operand values, including small values, large values, and values near
   the top and bottom of the 8-bit range — before submitting.

Good luck, and trace carefully.