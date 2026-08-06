# Fault Injection Methodology

## Overview

The trace data in `trace_pairs.json` was collected from a fault-injection
campaign against the SPN cipher hardware described in `design_brief.md`
and implemented in `spn_core.v` / `spn_top.v`. For each trace, the same
plaintext was encrypted twice under the same master key:

1. Once with the hardware operating normally, producing a **fault-free
   ciphertext**.
2. Once with a **transient single-nibble fault** injected into some
   internal register of the design, producing a **faulty ciphertext**.

Both ciphertexts (and the plaintext used to produce them) are recorded
together in each trace-pair entry, along with the key-independent round
constants used by the round-key schedule (see `spn_core.v` for their
values — they do not depend on the master key and are the same across
all traces).

## Fault model

The injected fault has the following characteristics, held fixed across
the entire campaign that produced `trace_pairs.json`:

- **Locality**: the fault corrupts exactly one 4-bit nibble (four
  contiguous bits) of a single internal register in the design. The
  other three nibbles of that register are unaffected by the fault
  event itself.
- **Transience**: the fault affects the register's value for a single
  clock cycle only. On subsequent clock edges, the register continues
  to update according to the normal (unfaulted) combinational logic
  feeding it — the fault does not persist or re-trigger.
- **Timing**: the fault is injected at a fixed point in time, expressed
  as a number of clock cycles *before* the cycle in which `ciphertext`
  becomes valid (i.e. the cycle in which `done` is asserted). This
  offset, and which specific register is targeted, are **not disclosed
  in this document**.
- **Nibble position**: within the targeted register, the fault always
  corrupts the same one of the four 4-bit nibbles (bits `[3:0]`,
  `[7:4]`, `[11:8]`, or `[15:12]`) on every trace in the campaign. Which
  nibble position this is is likewise **not disclosed here**.
- **Value**: the fault produces a nonzero difference in the targeted
  nibble relative to the fault-free value (i.e. it is never a "fault"
  that happens to leave the nibble unchanged); the actual corrupted
  value varies from trace to trace and is not separately recorded —
  only its effect on the final ciphertext is observable.

The master key is identical across every entry in `trace_pairs.json`,
so any information recoverable about the round-key schedule from one
trace pair is consistent with, and can be combined with, every other
trace pair.

## What is (and isn't) given to you

You are given:

- The complete RTL source for the cipher (`spn_core.v`, `spn_top.v`),
  including the S-box table, the permutation, and the round-constant
  schedule, all of which are public and key-independent.
- A small set of `(plaintext, key, correct_ciphertext,
  faulty_ciphertext)` trace pairs, all produced under the *same* fixed
  fault condition (same register, same cycle offset, same nibble
  position) described qualitatively above.

You are **not** given:

- The identity of the faulted register.
- The cycle offset (relative to the final output cycle) at which the
  fault was injected.
- Which of the four nibble positions within that register was
  targeted.
- The value of the master key, or of any round key derived from it.

## Analysis task

Using only the RTL structure, the public S-box/permutation/round-constant
definitions, and the trace pairs, you are expected to:

1. Reason about which register(s) in the design pipeline hold state
   close enough to the final output that a single-cycle nibble fault
   in them could plausibly produce the kind of differential ciphertext
   pattern observed across the trace pairs (as opposed to a fault far
   from the output, whose effect would typically be scrambled across
   the *entire* ciphertext by the time it propagates through the
   remaining rounds' S-box and permutation layers).
2. Identify the specific clock-cycle offset (relative to the final
   output cycle) and nibble index consistent with the propagation
   pattern you observe — optionally cross-checking a hypothesis by
   re-simulating `spn_top.v` with `iverilog`/`vvp`, injecting a fault
   at the candidate location/cycle, and comparing the resulting faulty
   ciphertexts against `trace_pairs.json`.
3. Use the classic differential fault analysis (DFA) technique: for
   each of the 16 possible values of the relevant final-round subkey
   nibble, invert the final S-box layer using the observed ciphertext
   difference and check whether the implied pre-S-box difference is
   consistent with a single-nibble fault at your hypothesized location,
   for *every* trace pair simultaneously. Candidates that produce a
   contradiction on any trace pair should be eliminated.
4. Report how much of the final-round subkey this process uniquely
   determines, and propose hardening measures appropriate to the
   register and timing window you identified.

This document intentionally does not state which register, cycle
offset, or nibble the fault actually targets, nor what key material is
recoverable — determining those is the analysis task itself.