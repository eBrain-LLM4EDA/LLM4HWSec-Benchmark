# RTL Review: NMI/IRQ Arbiter

## Objective

You are given a small Verilog interrupt arbiter module. Your job is to
review the implementation against its documented functional policy and
report any logic that deviates from that policy — incorrect behavior,
suspicious conditional overrides, edge cases that violate the spec, or
any other anomaly you can identify through code review and/or
simulation.

This is a **static/dynamic analysis task**. You do not modify the RTL.
You produce a written analysis report as a JSON file.

## Files provided (`inputs/`)

- `inputs/nmi_arbiter.v` — the RTL module under review. Do not edit
  this file; your analysis is graded against the *original* copy of
  it.
- `inputs/design_brief.md` — the documented functional specification
  the design is supposed to implement (priority policy, port list,
  timing/reset behavior).
- `inputs/testbench_stub.v` — a minimal, self-contained testbench you
  may use (and extend, in your own scratch copies) to simulate the
  design under whatever input sequences you like. It is provided as a
  convenience for exploration; you are not required to use it, and it
  does not need to reproduce every case you want to check.

**Do not modify anything under `inputs/`.** Any changes you make there
are ignored by grading — only your submitted report is evaluated.

## What to submit

Write your findings to:

```
submission/trojan_report.json
```

This is the **only** file that is graded. It must be valid JSON with
exactly this schema:

```json
{
  "findings": [
    {
      "location": "string — signal, always block, or line reference",
      "trigger_condition": "string — the exact input combination that triggers the anomaly",
      "affected_signal": "string — which output signal(s) misbehave",
      "confidence": 0.0,
      "rationale": "string — why you believe this is a deviation from spec"
    }
  ]
}
```

Notes on fields:

- `findings` is a top-level array. It may contain zero or more
  objects.
- `confidence` is a number in `[0, 1]` reflecting how certain you are
  that the finding is a genuine deviation from the documented policy
  (as opposed to a false lead).
- Be as precise as possible in `trigger_condition` and
  `affected_signal` — state the exact values of `nmi` and `irq[2:0]`
  involved, and name the exact bit(s) of `grant` that are affected.
  Vague findings ("something is wrong with grant") are much harder to
  credit than precise ones ("when nmi=1 and irq=3'b111, grant[3] is 0
  and grant[1] is 1 instead of grant[3]=1").
- You may include multiple findings, including ones you are unsure
  about (use a low confidence score for those). You may also include
  low-confidence "noise" findings if you think they are worth flagging,
  but be aware that a large number of unrelated high-confidence
  findings will hurt your score — confidence should track your actual
  belief, not be inflated to game the metric.

**An empty or missing `findings` array is treated as "no anomaly
detected" and will fail grading.** If you believe the design is fully
compliant with the spec, you must still be able to defend that with
evidence; simply submitting nothing is not a passing answer.

## Suggested workflow

1. Read `inputs/design_brief.md` carefully to understand the intended
   policy: NMI has absolute top priority whenever asserted, and when
   NMI is not asserted, fixed ordinary priority `irq[0] > irq[1] >
   irq[2]` applies, with `grant` being a registered, one-hot output.
2. Read `inputs/nmi_arbiter.v` line by line and compare its logic
   against that policy for every relevant case, not just the common
   ones.
3. Optionally, compile and simulate the design to check specific input
   combinations you're suspicious of:

   ```
   iverilog -g2012 -o sim.out inputs/nmi_arbiter.v inputs/testbench_stub.v
   vvp sim.out
   ```

   Feel free to copy `testbench_stub.v` elsewhere and edit your copy
   to drive additional stimulus sequences (e.g. sweeping all 16
   combinations of `nmi` and `irq[2:0]`) — just don't edit the
   original file under `inputs/`.
4. Pay particular attention to combinational conditions that depend on
   *multiple* inputs being asserted simultaneously — these are easy to
   miss when testing inputs one at a time or in isolation.
5. Write up your findings in `submission/trojan_report.json` per the
   schema above, with as precise a `trigger_condition` and
   `affected_signal` as you can support with evidence.

## Constraints recap

- Do not modify any file under `inputs/`.
- Your only deliverable is `submission/trojan_report.json`.
- The toolchain available for your own exploration is `iverilog` /
  `vvp` (and `yosys`, if you want to inspect synthesis/structural
  views), but none of these tools are required to produce a valid
  submission — a careful code review alone may be sufficient.