# Fault Model: Transient Register Perturbation

## Context

Embedded digital designs that operate in harsh environments (elevated temperature, radiation exposure such as cosmic-ray-induced neutron flux at altitude, or supply-voltage noise) are susceptible to transient upsets in sequential storage elements. These effects are well documented in the reliability engineering literature under names such as "single-event upset" (SEU) or "soft error," and they are a standard consideration during design review of any pipeline that stores intermediate values in flip-flops before those values are consumed by downstream logic.

This document describes, in general terms, the class of perturbation that a design reviewer should consider when assessing the robustness of an internal pipeline register — without specifying which particular register in a given design is affected. Identifying which register(s), if any, are exposed to this class of fault without adequate downstream verification is the subject of the review exercise itself.

## Perturbation Model

The fault model considered here has the following characteristics:

- **Single storage element.** Exactly one internal register in the datapath is affected during a given execution. All other registers, combinational logic, and control-path elements continue to operate correctly.
- **Transient duration.** The perturbation affects the register's stored value for one clock cycle (or, equivalently, corrupts the value latched into the register on one particular clock edge). The register's storage cell itself is not permanently damaged; on the next write, it can again hold a correct value. This distinguishes the fault from a "stuck-at" hardware defect, though the observable symptom for the affected cycle is similar: the register briefly holds an incorrect value in place of the correct one.
- **Arbitrary corrupted value.** The perturbation may flip one bit, several bits, or otherwise replace the register's correct content with an different, incorrect value within its bit-width. The reviewer should not assume the corruption is limited to a single bit position; any incorrect value the register could physically hold is in scope.
- **No control-path disruption.** The state machine, counters, and handshake signals (e.g. a "start" or "done" pulse) governing the pipeline's sequencing are assumed to continue operating exactly as designed. Only the data value held in the affected register is wrong for that cycle; the pipeline does not stall, does not re-enter an earlier phase, and does not otherwise indicate anything unusual happened.
- **Timing window.** The perturbation is assumed to occur after the affected register has been loaded with its (intended) computed value, but before that value is consumed by whatever downstream combinational or sequential logic uses it. In other words, the register briefly holds the wrong value at exactly the point where later stages read from it.

## Why This Matters for Datapath Review

A pipeline stage that stores an intermediate result in a register and later consumes that register's value to produce a final output is only as trustworthy as the confidence that (a) the register was loaded correctly and (b) its value did not change unexpectedly between being loaded and being consumed. Absent any additional check, a datapath has no way to distinguish "the register holds the value I computed" from "the register holds some other value that happened to be present at read time." If the downstream logic naively trusts whatever value is currently sitting in the register — and the surrounding control logic (counters, done/valid signaling) is otherwise unaffected — then a transient perturbation of exactly the kind described above can propagate silently into the final output with no accompanying indication that anything went wrong.

A design that is robust to this class of fault would, at minimum, provide some means of catching the case where a stored intermediate value does not match what an independent recomputation would have produced, before that value is allowed to influence a final, externally-visible output.

## Simulating This Fault Model

For the purposes of a design review, this perturbation can be reproduced in RTL simulation without any special tooling:

1. Take a copy of the module under review and identify the specific internal register believed to hold an intermediate value that later feeds the final output.
2. Instrument the simulation (e.g. via a testbench force statement, an `assign`/`deassign` pair, or a small procedural block gated on a chosen clock cycle count) to override that register's value for exactly one clock cycle, immediately after the cycle on which it would normally have been loaded with its correct, computed value.
3. Allow the simulation to proceed normally from that point onward, with no other modification to the design or its control signals.
4. Compare the resulting final output and completion signaling against a known-good reference computation (e.g. a reference module implementing the same function through an independent computational path) run on the same input, without any forced perturbation.
5. Observe whether the completion signaling still indicates a valid result, and whether the final output value differs from the reference despite that indication.

This procedure is a standard technique for assessing whether a given register's value is adequately safeguarded before it contributes to a module's externally visible result, and is a useful exercise to perform against the artifacts provided for this review.