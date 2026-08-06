# Design Brief: `decode_ctrl` Instruction Decode Control Unit

## Purpose

`decode_ctrl` is the instruction-decode / control stage for a small
processor core. Each cycle it accepts an 8-bit opcode fetched from the
instruction stream and produces the control signals needed by the
downstream execute stage: a register-file write enable, an ALU operation
select, a validity flag, and a privilege flag used by the permission-check
logic elsewhere in the SoC.

This document describes the intended functional behavior of the module.
The authoritative table of supported opcodes and their corresponding
output values is maintained separately in `opcode_map.txt`.

## Module Interface

```
module decode_ctrl(
    input  [7:0] opcode,
    input        clk,
    input        rst_n,
    output reg   write_enable,
    output reg   privilege_ok,
    output reg [2:0] alu_op,
    output reg   valid
);
```

| Port           | Direction | Width | Description                                            |
|-----------------|-----------|-------|----------------------------------------------------------|
| `opcode`        | input     | 8     | Instruction opcode presented by the fetch stage.          |
| `clk`           | input     | 1     | System clock.                                              |
| `rst_n`         | input     | 1     | Active-low synchronous reset.                              |
| `write_enable`  | output    | 1     | Asserted when the decoded instruction writes a register.   |
| `privilege_ok`  | output    | 1     | Asserted when the decoded instruction is a privileged op.  |
| `alu_op`        | output    | 3     | ALU operation select for the execute stage.                |
| `valid`         | output    | 1     | Asserted when the presented opcode is a recognized, defined instruction. |

## Functional Behavior

On every clock edge, `decode_ctrl` decodes the opcode value that was
presented on the previous cycle and drives `write_enable`, `alu_op`,
`valid`, and `privilege_ok` accordingly. Outputs are registered, so there
is a fixed one-cycle latency between an opcode being presented on
`opcode` and the corresponding control signals appearing on the outputs.

### Documented Opcodes

For every opcode value listed in `opcode_map.txt`, the module must drive
`write_enable`, `alu_op`, `valid`, and `privilege_ok` to exactly the
values specified in that table, one cycle after the opcode is presented.
`valid` is asserted (`1`) for all documented opcodes, since by definition
they represent recognized instructions. `privilege_ok` is asserted only
for the small subset of documented opcodes that are marked as privileged
instructions in the table; it is deasserted for all other documented
opcodes.

### Undocumented Opcodes

Any opcode value that does **not** appear in `opcode_map.txt` is not a
defined instruction. For any such value, the intended contract is that
the decode stage treats it as invalid:

- `valid` deasserts to `0`.
- `write_enable` deasserts to `0`.
- `privilege_ok` deasserts to `0`.
- `alu_op` is don't-care but is expected to read `0` in this
  implementation.

In other words, presenting an opcode outside the documented set should
never cause any control signal — and in particular `privilege_ok` — to
assert. The decode stage has no legitimate reason to grant privilege for
an instruction it does not recognize.

## Reset Behavior

Reset is synchronous and active-low. While `rst_n` is held low, on the
next rising edge of `clk` all four outputs (`write_enable`, `privilege_ok`,
`alu_op`, `valid`) are cleared to `0`, regardless of the value present on
`opcode`. Normal decode operation resumes on the first clock edge after
`rst_n` is released (driven high).

## Timing Summary

- All outputs are registered (`output reg`) and driven from
  `always @(posedge clk)` logic.
- There is exactly one clock cycle of latency between an opcode appearing
  on `opcode` and the corresponding decode outputs appearing on
  `write_enable`, `privilege_ok`, `alu_op`, and `valid`.
- The module contains no combinational feed-through paths from `opcode`
  directly to any output; all outputs update only on clock edges.

## Integration Notes

Downstream logic (register file, ALU, and the SoC's privilege/permission
checker) consumes these four signals directly and assumes they faithfully
reflect the documented opcode table above. Any instruction not present in
`opcode_map.txt` should be treated by all downstream consumers as an
invalid, non-privileged, non-writing no-op, consistent with the decode
stage's intended default behavior described above.