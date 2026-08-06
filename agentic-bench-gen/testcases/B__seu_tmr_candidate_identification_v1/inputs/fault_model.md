# Single-Event Upset (SEU) Fault Model — Background Reference

## Purpose

This document describes the generic fault assumptions used when reasoning about hardening decisions for sequential (flip-flop) storage in a digital design. It is intended as background reading only. It does not evaluate or reference any specific design; you must apply the general concepts described here to the RTL you are analyzing.

## Fault Assumption: Single-Event Upset (SEU)

A single-event upset models the effect of ionizing radiation (or an analogous transient disturbance) striking a storage node and flipping its stored value. For the purposes of this analysis, the following simplified assumptions apply:

1. **One bit-flip per fault window.** Within any given fault window (e.g., one clock period, or the interval between two hardening decision points), at most a single flip-flop anywhere in the design may have its stored bit inverted. Combinational logic is assumed fault-free; only sequential storage elements (registers) are subject to upset.

2. **Persistence until next write.** Once a bit is flipped, the corrupted value remains in place until that storage element is next written by its normal clocked update (its own `always @(posedge clk ...)` process). There is no automatic self-healing of a flipped bit before the next legitimate write.

3. **Uniform likelihood.** No register is assumed to be inherently more or less likely to be struck than any other; likelihood of upset is treated as uniform across all flip-flops in the design. This model does not incorporate any information about physical layout, process node, or particle flux variation.

4. **No timing or power side-channel considerations.** This fault model is limited to logical/functional corruption of stored state. It does not model or require analysis of switching time, current draw, electromagnetic emission, or any other physical side channel. Those concerns are out of scope for this analysis.

5. **Fault observability is not assumed.** The model does not assume that a corrupted register will necessarily produce an externally visible error indication (such as a flag, exception, or checksum mismatch). Whether a given upset is eventually observable, silently absorbed, or silently propagated depends entirely on how the corrupted value is subsequently used by the surrounding logic — which is part of what an analyst must determine by examining the design itself.

## Hardening Technique: Triple Modular Redundancy (TMR)

Triple Modular Redundancy is a standard hardening technique for protecting a storage element (or a small cluster of related storage elements) against single-bit upsets:

- The protected register is instantiated three times, with identical update logic driving each of the three copies in parallel.
- A majority-voting circuit compares the three copies on every read and outputs the value held by at least two of the three.
- If exactly one of the three copies is corrupted by an SEU (consistent with the "at most one bit-flip per fault window" assumption above), the majority vote continues to produce the correct value, and the corrupted copy is naturally overwritten on the next clocked update, restoring consistency.

TMR is effective against the single-fault assumption in this model, but it is not free:

- **Area cost.** Each protected register requires roughly three times the flip-flop area, plus additional area for the majority-voting logic on every output path.
- **Power cost.** Triplicated storage and voting logic increase both dynamic switching power and static leakage power roughly in proportion to the number of bits protected.
- **Timing cost.** Voting logic adds a small amount of additional combinational delay on the read path of any protected register, which can affect timing closure in tight designs.

## Hardening Under a Fixed Budget

In practice, a design's area and power budget will not permit applying TMR to every flip-flop unconditionally. A hardening plan must therefore prioritize: some subset of registers should receive TMR protection, and the remainder should be left unprotected, accepting the residual risk of an uncorrected upset in that subset.

Making this prioritization decision requires understanding, for each register (or logically related group of registers) in a specific design:

- What role that storage element plays in the overall behavior of the circuit.
- How its value is produced (which logic writes it, and under what conditions).
- How its value is subsequently consumed by the rest of the design.
- What the practical consequence of a single unexpected bit-flip in that storage element would be, given the surrounding logic, under the assumptions above.

This document intentionally does not enumerate which registers in any particular design warrant TMR — that determination depends on the specific structure and behavior of the design being analyzed, and is the responsibility of the analyst performing the review.