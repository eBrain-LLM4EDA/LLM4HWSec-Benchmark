# Design Brief: `top` Controller/Datapath Module

## 1. Overview

The `top` module implements a small controller/datapath unit intended for
use as a subblock in a larger system-on-chip design. It accepts a data
input and a control input, maintains a small amount of internal state
across a set of control and datapath registers, and produces a single
combinational/registered data output. The module is designed to be
synthesizable to standard cell libraries and is intended to be fully
resettable to a known-good state on demand.

## 2. Ports

| Port   | Direction | Width | Description |
|--------|-----------|-------|-------------|
| `CLK`  | input     | 1     | System clock. All sequential state in the module is updated on the rising edge of `CLK`. |
| `RSTN` | input     | 1     | Synchronous, active-low reset. When `RSTN` is deasserted (logic 0), all state-holding registers in the module are synchronously cleared to their defined reset value on the next rising edge of `CLK`. |
| `DIN`  | input     | N     | Primary data input to the datapath logic. |
| `CTRL` | input     | M     | Control input used to sequence internal control registers and to select datapath operations. |
| `DOUT` | output    | N     | Primary data output, derived from the current datapath and control state. |

## 3. Functional Description

### 3.1 Control Path

The control path consists of a small bank of control registers that track
the current operating mode and sequencing state of the module. These
registers advance based on the value of `CTRL` sampled on each rising edge
of `CLK`, and they gate which datapath operation is active at any given
time. The control registers include the module's privilege/lock-state
tracking, which determines whether certain datapath operations are
permitted in the current mode.

### 3.2 Datapath

The datapath consists of a small bank of pipeline/storage registers that
capture and forward values derived from `DIN` under the direction of the
current control state. The datapath combines `DIN` with the current
control settings to produce `DOUT`.

### 3.3 Reset Behavior

The module uses a single, global, synchronous, active-low reset signal,
`RSTN`, distributed to every state-holding register in the design
(control registers, privilege/lock-state registers, and datapath
registers alike).

The intended reset behavior is as follows:

- While `RSTN` is held at logic 1, the module operates normally: control
  and datapath registers update each clock edge according to `CTRL` and
  `DIN` as described above.
- When `RSTN` is driven to logic 0, then on the next rising edge of `CLK`
  every state-holding register in the module — every control register,
  every privilege/lock-state register, and every datapath register —
  must synchronously clear to its defined reset value (logic 0 for all
  registers in this design). This must occur uniformly and simultaneously
  across all registers; no register is expected to retain its
  pre-reset value once a reset pulse has been applied.
- Once `RSTN` returns to logic 1, normal operation resumes from the
  cleared (all-zero) state.

This uniform reset behavior is a basic system-level assumption: any
downstream logic or software that relies on this module assumes that
asserting `RSTN` returns the entire module, including its
privilege/lock-state registers, to a fully known, all-zero state with no
exceptions.

### 3.4 Normal-Operation Output Behavior

Under normal (non-reset) operation, `DOUT` is a function of `DIN` and the
current control/datapath register state only. Reset wiring has no bearing
on functional behavior outside of a reset event; the datapath computation
itself is unaffected by how any individual register's reset input happens
to be connected internally, since that connection only matters while a
reset is being applied.

## 4. Internal State Elements

The module is expected to be implemented with the following
state-holding flip-flops (exact instance names may vary by
implementation, but each of the following roles is represented by one
flip-flop instance):

- Four control-path registers, tracking mode/sequencing state
  (e.g. `u_ctrl_ff0`, `u_ctrl_ff1`, `u_ctrl_ff2`, `u_ctrl_ff3`).
- Two datapath registers, tracking captured/forwarded data values
  (e.g. `u_dp_ff4`, `u_dp_ff5`).
- Two privilege/lock-state registers, tracking the current
  privilege/lock mode of the module (e.g. `u_priv_ff1`, `u_priv_ff2`).

All eight of these registers are state-holding elements of the module and,
per Section 3.3, are all expected to be wired to the same global
synchronous active-low reset signal, `RSTN`, and to clear to logic 0 on
reset.

## 5. Summary

`top` is a straightforward synchronous control/datapath module with a
single global synchronous active-low reset. All internal registers,
including the privilege/lock-state registers, are expected to reset
uniformly whenever `RSTN` is asserted, ensuring the module always returns
to a fully known, well-defined state after a reset event.