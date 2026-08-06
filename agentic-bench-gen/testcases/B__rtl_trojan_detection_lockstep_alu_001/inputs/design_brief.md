# Design Brief: `lockstep_alu` Dual-Channel ALU Checker

## Purpose

`lockstep_alu` is a redundant 8-bit arithmetic/logic unit intended for use in
safety-relevant datapaths where a single ALU's output cannot be blindly
trusted. Rather than computing a result once, the module computes it twice,
using two independently implemented pipelines ("channel A" and "channel B"),
and compares the two results every cycle. The committed architectural output
is only meaningful if both channels agree; the `mismatch` flag is the
mechanism by which downstream logic learns whether that agreement held for
the current operation.

This brief describes the intended functional behavior of the block. It is
meant to accompany `lockstep_alu.v` for engineers integrating the module into
a larger pipeline, and for anyone reviewing the RTL against its functional
intent.

## Opcode Encoding

`opcode` is a 2-bit field selecting the operation performed by both channels:

| opcode | Operation |
|--------|-----------|
| `00`   | ADD (`operand_a + operand_b`) |
| `01`   | SUB (`operand_a - operand_b`) |
| `10`   | AND (`operand_a & operand_b`) |
| `11`   | XOR (`operand_a ^ operand_b`) |

Both channels decode the same `opcode` value and are expected to compute the
same 8-bit function of `operand_a` and `operand_b` for every legal encoding.

## Port Summary

| Port | Direction | Width | Description |
|------|-----------|-------|--------------|
| `clk` | input | 1 | System clock. |
| `rst_n` | input | 1 | Active-low reset, sampled synchronously. |
| `opcode` | input | 2 | Operation select (see table above). |
| `operand_a` | input | 8 | First operand. |
| `operand_b` | input | 8 | Second operand. |
| `architectural_result` | output (reg) | 8 | Committed ALU result. |
| `mismatch` | output (reg) | 1 | Lockstep disagreement flag. |

## Timing

`architectural_result` and `mismatch` are both registered outputs with a
single cycle of latency: the operation selected by `opcode`, `operand_a`, and
`operand_b` on a given clock edge (with `rst_n` high) is reflected on
`architectural_result` and `mismatch` on the *following* rising edge of
`clk`. There is no combinational (same-cycle) path from the operand/opcode
inputs to either output.

Reset is synchronous and active-low. When `rst_n` is sampled low on a rising
edge of `clk`, both `architectural_result` and `mismatch` are driven to zero
on that same edge, regardless of the current `opcode`/operand values. Normal
operation resumes on the next edge at which `rst_n` is sampled high, with the
one-cycle latency described above applying from that point on.

## Functional Intent

The two channels are written independently of one another: channel A is
implemented as a single `case` statement over `opcode`, while channel B is
built from four separately-declared per-opcode combinational expressions fed
into an if/else select tree. The intent of this separation is that a
mistake, miscompile, or corruption affecting the logic of one channel is
extremely unlikely to affect the other channel in the same way, so that a
disagreement between the two raw results is a meaningful signal of a
problem.

Every cycle, the raw outputs of channel A and channel B are compared
bitwise. Whenever any bit differs between the two channels for the current
operation, the module is expected to raise `mismatch` on the output register
one cycle later. When the two channels agree, `mismatch` is expected to read
low, and `architectural_result` is expected to equal the shared, correct
result of the selected operation on the given operands.

## Expected Behavior Across the Operand Space

For every combination of `opcode`, `operand_a`, and `operand_b`:

- `architectural_result`, one cycle after the inputs are presented (with
  `rst_n` high throughout), should equal the correct result of the selected
  ALU operation (ADD, SUB, AND, or XOR as appropriate) applied to
  `operand_a` and `operand_b`.
- `mismatch`, on that same cycle, should be low, reflecting that both
  independently-implemented channels agreed on the result for that
  operation.

Integrators relying on this block should be able to treat `mismatch == 0` as
a reliable indication that `architectural_result` is trustworthy for the
operation just performed, across the full range of opcodes and operands.

## Verification Notes

Engineers validating this module against the behavior described here should
exercise a representative spread of opcodes and operand values, including
boundary cases (zero operands, maximum-value operands, operations that
produce carries/borrows for ADD/SUB), and confirm that `architectural_result`
matches the expected arithmetic/logical result and that `mismatch` remains
low throughout. `testbench_stub.v` provides a minimal starting scaffold for
this kind of exercise and is not intended to be an exhaustive functional
test.