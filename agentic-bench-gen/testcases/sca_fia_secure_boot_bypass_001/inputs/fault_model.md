# Fault Model: Single-Bit Transient Fault Injection

## Attacker Capability

The attacker is assumed to have physical proximity to the device during
its boot sequence, using techniques such as electromagnetic (EM) fault
injection, clock glitching, voltage glitching, or laser fault injection.
These techniques are modeled abstractly here as the ability to force a
single flip-flop's stored value for a short, bounded window of time.

The attacker cannot:

- Read or write combinational signals directly.
- Modify more than one flip-flop in a given run.
- Sustain a fault across multiple clock cycles.
- Alter the RTL, the expected signature value, or the input signature
  bytes supplied to the module.

The attacker can:

- Select any single flip-flop instance in the design as the fault
  target for a given experiment.
- Force that flip-flop to a chosen value (0 or 1, or bit-flip of its
  current value) for exactly one clock edge.
- Choose *when* during the boot sequence (i.e., at which clock cycle)
  the fault is applied, including choosing to fault the register while
  the design is in any reachable state.
- Repeat the experiment with a different single flip-flop and/or a
  different timing choice.

## Fault Model Parameters

- **Fault type:** transient bit-set / bit-clear / bit-flip on a single
  storage element (flip-flop bit).
- **Fault width:** exactly one flip-flop (if the flip-flop is
  multi-bit, exactly one bit of it) is disturbed per experiment.
- **Fault duration:** the disturbed value is only forced for a single
  clock cycle. On the next clock edge, the flip-flop resumes normal
  operation driven by its regular next-state logic (unless that logic
  itself now computes a different value as a consequence of the fault).
- **Fault timing:** the fault may be injected at any single clock cycle
  chosen by the attacker, including cycles where the module is idle,
  loading, comparing, or has already completed a sequence.
- **Repeatability:** each simulated run injects a fault into exactly one
  flip-flop. Different flip-flops require separate runs to evaluate.

## Analysis Goal

Given this fault capability, the analysis task is to determine which
flip-flop(s) in the design, if disturbed according to the model above,
can change the module's ultimate authentication outcome — that is,
cause the module to reach a state in which it reports a successful
verification without the input signature having genuinely matched the
expected value through the normal comparison path.

Flip-flops whose disturbance has no effect on the authentication
outcome (e.g., because normal next-state logic immediately overwrites
the disturbed value before it can influence any output, or because the
disturbed value only affects timing/bookkeeping rather than the
pass/fail decision) are considered lower priority for hardening than
flip-flops whose disturbance directly or indirectly determines whether
authentication is reported successful.

Analysts should consider both:

1. Flip-flops that are read *directly* by the logic driving the
   module's success/failure output.
2. Flip-flops whose value determines *which state* the control logic
   is in, since state values can determine whether success-indicating
   outputs are asserted regardless of any comparison result.

The output of this analysis should identify the specific flip-flop(s)
most critical to the security guarantee of the module and propose
hardening techniques appropriate to a single-bit transient fault model.