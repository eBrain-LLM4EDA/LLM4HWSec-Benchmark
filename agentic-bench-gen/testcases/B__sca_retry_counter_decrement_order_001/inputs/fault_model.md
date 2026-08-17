# Fault Model: Single-Event-Transient State Skip

## Overview

This document describes the fault-injection threat model that the
controller under analysis must be evaluated against. It applies to any
synchronous finite-state machine implemented with a state register and
combinational next-state logic, and is not specific to any one design.

## Fault mechanism

A single-event transient (SET) — for example a brief voltage-rail dip,
an injected clock glitch, or a localized electromagnetic pulse timed
against the clock edge — can corrupt the value that gets latched into
a state register on one particular clock edge.

For the purposes of this analysis, the fault is modeled as follows:

- **Scope of corruption.** The fault affects only the state register's
  next-state value on a single targeted clock edge. It does not
  corrupt any other register in the design: data registers, latched
  comparison or computation results, and all other stored values are
  assumed to update normally and correctly on that same edge and on
  every other edge.

- **Effect on the state register.** Instead of advancing to the state
  that the correct next-state logic would have produced, the state
  register advances one step further than intended: it lands directly
  in the state that would normally be reached only after *two*
  sequential correct transitions from the pre-fault state. In other
  words, the fault causes the FSM to skip over exactly one intended
  intermediate state for that single clock edge, as if that
  intermediate state had never been visited.

- **Transience.** The fault is a single event. It affects one clock
  edge only. On every subsequent clock edge, the state register and
  all next-state logic resume normal, unfaulted operation from
  wherever the skip left the FSM. The fault does not repeat, persist,
  or recur later in the same session unless a new fault is
  independently injected.

- **Frequency.** At most one such fault occurs per attempt/session
  under analysis (e.g., per activation of the controller's input
  protocol). This models a realistic, opportunistic physical attacker
  who can time a single glitch per power-up or per protocol run, not
  an attacker with unlimited simultaneous fault injection.

## Illustrative examples (generic, unrelated to the controller under test)

- In a generic traffic-light controller with states `RED -> RED_AMBER
  -> GREEN -> AMBER -> RED`, a state-skip fault landing on the edge
  leaving `RED` could cause the FSM to jump directly to `GREEN`,
  skipping the `RED_AMBER` transition state entirely for that one
  cycle, while the lamp-driver registers themselves still update
  according to whatever state the FSM lands in.

- In a generic UART receiver FSM with states `IDLE -> START_BIT ->
  DATA_BITS -> STOP_BIT -> IDLE`, a fault landing on the edge leaving
  `START_BIT` could cause the FSM to land directly in `STOP_BIT`,
  skipping `DATA_BITS` for that cycle, without corrupting the shift
  register's contents on that same edge.

These examples are provided only to illustrate the general shape of
the fault (a one-state skip on a single clock edge, with all other
registers unaffected) and do not describe the specific FSM under
analysis in this task. Determining which transition(s) in the
controller under test are meaningfully affected by this fault model,
and under what timing conditions, is part of the analysis to be
performed.