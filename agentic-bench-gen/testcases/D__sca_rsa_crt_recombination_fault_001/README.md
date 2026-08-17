# Side-Channel & Fault Analysis: CRT Recombination Datapath Review

## Background

A design team has implemented a small embedded modular-arithmetic datapath, `crt_recombine`, that computes a result using a two-path ("Chinese-Remainder-style") decomposition: an input message is reduced along two separate small-modulus branches, and the two partial results are then recombined into a final output. A companion module, `crt_reference`, computes the same mathematical function through a single, direct modular-reduction path and is provided purely as a golden reference for cross-checking behavior.

You have been asked to perform a design review of the recombination stage. Your job is to examine the provided RTL and testbench artifacts, understand the internal register structure of `crt_recombine`, and determine:

1. Which internal register in the recombination datapath is used to build the final output *without* being independently re-verified first.
2. Under what kind of register-level perturbation (fault) that register's value could diverge from correct operation while the module still reports successful completion.
3. A concrete input/fault scenario that would demonstrate this divergence.
4. What verification step is missing from the RTL that should have caught such a divergence before the output was committed.
5. A concrete RTL-level fix that would add that missing verification.

This is a pure analysis task. You will not modify or resubmit any RTL — your deliverable is a structured JSON report.

## Provided Input Artifacts (`inputs/`)

- `design_brief.md` — plain-language description of the datapath's purpose, ports, and timing behavior.
- `fault_model.md` — a plain-engineering description of the class of register-level perturbation relevant to this review (framed as a general reliability/robustness concern for embedded pipeline registers).
- `crt_recombine.v` — the RTL module under review. Ports: `clk`, `rst_n` (active-low, synchronous), `start` (pulse), `msg_in[7:0]`, `result_out[7:0]` (reg, valid the cycle `done` is high), `done` (reg, pulses for one cycle). Internal branch registers `sig_p_reg` and `sig_q_reg` are named directly in the RTL comments and signal declarations.
- `crt_reference.v` — a reference/oracle module with an identical port list and matching cycle-for-cycle `done`/`result_out` timing semantics, computing the same function via a single direct modular-reduction path (no branch split). Useful for cross-checking specific input vectors.
- `tb_crt_recombine.v` — a testbench that runs both modules on a few nominal input vectors and confirms they agree in the absence of any fault, establishing that the design is functionally correct under normal conditions.

**Do not modify any files under `inputs/`.** They are provided as read-only reference material for your analysis.

You are free to use `iverilog`, `vvp`, and `yosys` locally to experiment with the provided RTL — for example, to simulate the testbench, to try instrumenting a copy of `crt_recombine.v` to force one of its internal registers to an incorrect value at a chosen point in the cycle sequence, and to compare the resulting `result_out` against `crt_reference.v`'s output for the same input. This is optional but may help you validate your findings before writing them up.

## Your Deliverable

Submit your analysis as a single JSON file at:

```
submission/vulnerability_report.json
```

The file must be valid JSON with **exactly** the following five top-level string fields, all non-empty, and no other top-level fields:

```json
{
  "vulnerable_register": "string",
  "fault_model": "string",
  "trigger_scenario": "string",
  "missing_verification_step": "string",
  "recommended_fix": "string"
}
```

### Field guidance

- **`vulnerable_register`** — Name the specific internal register in `crt_recombine.v` (one of `sig_p_reg` or `sig_q_reg`) whose value is consumed by the recombination logic to build `result_out` without being independently re-checked first.
- **`fault_model`** — Describe the class of register-level perturbation you are assuming (e.g. a transient bit-level corruption of a single internal register for one cycle), and why it is plausible for this kind of pipeline register.
- **`trigger_scenario`** — Give a concrete, reproducible scenario: a specific `msg_in` value, and a description of forcing the named register to an incorrect value at a specific point in the cycle sequence, such that simulating `crt_recombine.v` under this condition produces a `result_out` that differs from `crt_reference.v`'s output for the same `msg_in`, on the cycle `done` is asserted in both.
- **`missing_verification_step`** — State precisely what check is absent from the RTL that would have caught this divergence before `result_out`/`done` were committed.
- **`recommended_fix`** — Describe a concrete RTL-level change (e.g. adding a redundant recomputation and comparison step, or an equivalent independent cross-check) that would cause the module to withhold or flag its output instead of asserting `done` on a divergent value.

## Evaluation

Your submission is graded on:

1. **Schema compliance** — the JSON must parse and contain all five required fields as non-empty strings, with no extra top-level fields.
2. **Content accuracy** — whether you correctly identify the vulnerable register and a fault model consistent with a single transient register-level corruption, whether your `trigger_scenario` is internally consistent and (where checked) reproducible in simulation against the reference module, and whether your proposed fix and missing-verification-step describe a specific, actionable redundant-verification countermeasure rather than a vague or unrelated mitigation.

A report that only vaguely gestures at "a register might be wrong" without naming the specific register, or that proposes an unrelated fix (e.g. adding parity to the input message), will not score well. Be specific and concrete.

A placeholder submission is provided at `submission/vulnerability_report.json` — you must replace its contents with your own analysis before submitting.