# Fault Model: Single-Step Instruction Skip

## Overview

This document describes a generic transient-fault mechanism applicable to
synchronous FSM-based control sequencers such as `mode_sequencer.v`. The
mechanism is commonly associated with physical fault-injection techniques
(supply-voltage glitching, clock glitching, electromagnetic pulse injection,
or laser fault injection), but the model here is expressed purely in terms
of its logical effect on the circuit, independent of the specific injection
technique used.

## Mechanism

A synchronous FSM typically performs two kinds of work on each active clock
edge while in a given state:

1. **State-sequencing logic** — computation of the next state value, which
   is latched into the state register.
2. **State-defined write actions** — any additional register writes that the
   current state is defined to perform (for example, incrementing a
   counter, latching a status flag, or updating a data register).

The **single-step instruction-skip fault** models a transient disturbance
that is precisely timed to a single target clock cycle and that suppresses
only the state-defined write action described in (2), while leaving the
state-sequencing logic in (1) completely unaffected. In other words:

- The FSM's state register still updates to the correct next state on the
  affected cycle, exactly as it would in the fault-free case.
- Any register write that the *current* state would otherwise have
  performed on that cycle does not take effect; the target register instead
  retains whatever value it already held (as if a `default: reg <= reg;`
  branch had been taken instead of the state's intended write branch).
- On all other cycles (before and after the fault cycle), the circuit
  behaves exactly as specified, with no persistent change to the
  sequencing logic itself.

This is a *single-step* fault: it affects exactly one clock cycle, and by
extension the write action of exactly one state occurrence in one pass
through a transition sequence. It does not repeat on subsequent passes
through the same state unless re-injected.

This fault can, in principle, be targeted at **any** state in an FSM that
performs a write action, not just a specific one. Whether skipping a given
state's write action has any observable effect on the final outcome of a
transition sequence depends entirely on that state's role: if a state does
not perform any register write (i.e. it exists purely for sequencing or
timing purposes), skipping its "write" trivially has no effect, since there
was nothing to skip. If a state is the state responsible for updating a
register to a new value, skipping it means that register retains its
prior value instead of taking on the new one.

## Generic Illustration (Unrelated Example)

Consider an unrelated toy sequencer that walks through states `START`,
`LOAD`, `INC`, `HOLD`, `STOP` to increment an 8-bit counter register `cnt`
by one:

- `START`: sequencing only, no write to `cnt`.
- `LOAD`: sequencing only, no write to `cnt`.
- `INC`: performs `cnt <= cnt + 1`.
- `HOLD`: sequencing only, no write to `cnt`.
- `STOP`: sequencing only, no write to `cnt`.

Under fault-free operation, `cnt` increases by exactly one over the full
`START -> LOAD -> INC -> HOLD -> STOP` sequence.

If a single-step instruction-skip fault is injected during `START`, `LOAD`,
`HOLD`, or `STOP`, the FSM advances to the next state on schedule, and
`cnt` still ends up incremented by one, because none of those states had a
write action to suppress in the first place.

If the same fault is instead injected during `INC`, the FSM still advances
to `HOLD` on schedule, but the `cnt <= cnt + 1` write does not occur on
that cycle; `cnt` retains its pre-`INC` value for the remainder of the
sequence, and the final value of `cnt` differs from the fault-free case by
exactly the skipped increment.

This illustrates the general principle: the observable effect of a
single-step instruction-skip fault depends entirely on whether the
targeted state performs a write action that other states in the sequence
do not redundantly perform or correct.

## Forcing an Instruction-Skip Fault in Simulation

To study the effect of this fault model on a given design in simulation, a
tester can construct a testbench harness around the design under test that:

1. Drives the design through a normal (fault-free) run of the transition
   sequence of interest, recording the resulting register values as a
   baseline.
2. Selects a target state to fault, and a target occurrence of that state
   (typically the first/only occurrence within a single pass through the
   sequence).
3. Re-runs the sequence, but on the clock cycle where the FSM is in the
   targeted state, forces any write-enable condition associated with that
   state's write action to be suppressed for that one cycle only — for
   example, by temporarily forcing the relevant `case` branch to fall
   through to a "no write" / "hold current value" behavior, or by gating
   the write-enable signal feeding the register with an injected control
   signal that is asserted for exactly one clock cycle.
4. Allows the FSM's state-sequencing logic to proceed completely
   unmodified, so that `next_state` computation and the state register
   update happen exactly as in the fault-free run.
5. Compares the final register values at the end of the sequence (e.g. once
   `done` is asserted) against the fault-free baseline to determine whether
   the skip at that particular state had any observable effect.

Repeating this procedure once per state in a transition sequence — skipping
each state's write action in turn while leaving sequencing logic untouched
— produces a complete per-state characterization of which single-step
instruction-skip faults are observable at the sequence's completion and
which are not.