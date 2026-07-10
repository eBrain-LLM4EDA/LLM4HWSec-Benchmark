# RTL Hardware Trojan Detection — AES-like Core

## Task

You are given a compact, synthesizable Verilog module implementing an
AES-like round-function core, along with a design brief describing its
intended behavior:

- `inputs/aes_core.v` — the RTL implementation under review.
- `inputs/design_brief.md` — a plain-English description of the module's
  documented ports, datapath, and control behavior.

Your job is to analyze the RTL against the design brief and determine
whether the implementation faithfully realizes **only** the documented
functionality, or whether it contains additional internal logic whose
behavior deviates from the specification under some internal condition.

Produce a report identifying:

- any suspicious internal signal(s) that are not accounted for by the
  design brief,
- the condition(s) under which each suspicious signal becomes active,
- which output port(s) are affected when that condition fires,
- your confidence in each finding,
- an overall assessment and a final verdict on whether the design
  contains injected/undocumented behavior.

You are encouraged to read the RTL carefully, cross-reference every
identifier against the design brief, and reason about which registers
and comparators have no legitimate role in the documented round
computation. The toolchain (`iverilog`, `vvp`, `yosys`) is available
in the environment if you want to elaborate or simulate the design to
confirm a hypothesis, but using it is optional — your submission is
graded purely on the content of your report.

## Submission Contract

You do **not** modify any files under `inputs/`. Your entire submission
is a single file:

```
submission/trojan_report.json
```

A starter template is already present at that path. It is a naive,
placeholder answer that you are expected to replace with your own
analysis — do not submit it unchanged.

No other files are graded. Do not add extra files to `submission/`;
only `trojan_report.json` will be read.

## Required Schema

`submission/trojan_report.json` must be valid JSON with exactly this
shape:

```json
{
  "findings": [
    {
      "signal_name": "string",
      "activation_condition": "string",
      "affected_outputs": ["string"],
      "confidence": 0.0
    }
  ],
  "overall_assessment": "string",
  "is_trojan_present": false
}
```

Field semantics:

- `findings` — an array of candidate suspicious-signal findings. May be
  empty.
- `signal_name` — the name of the suspicious wire/reg/net, as a string.
- `activation_condition` — a plain-English or Verilog-expression
  description of the internal state or condition under which the
  signal's anomalous behavior occurs.
- `affected_outputs` — an array of output port names that are altered
  when the condition fires.
- `confidence` — a number between `0.0` and `1.0` inclusive, indicating
  how confident you are in this specific finding.
- `overall_assessment` — a free-text summary of your conclusion (e.g.
  `"suspicious rare-trigger logic found"` or `"no anomalies found"`).
- `is_trojan_present` — boolean, your final verdict on whether the
  design contains undocumented/injected logic.

## Functional Requirements

1. **FR1 — Valid schema.** `trojan_report.json` must be valid JSON and
   match the schema above exactly: top-level keys `findings` (array),
   `overall_assessment` (string), `is_trojan_present` (boolean); each
   entry in `findings` must include `signal_name` (string),
   `activation_condition` (string), `affected_outputs` (array of
   strings), and `confidence` (number in `[0.0, 1.0]`).

2. **FR2 — Consistency between verdict and findings.** If
   `is_trojan_present` is `true`, `findings` must contain at least one
   entry. If `is_trojan_present` is `false`, `findings` may be empty.

3. **FR3 — Real signal names only.** Every `signal_name` you report
   must correspond to an identifier (wire, reg, or port) that appears
   verbatim in `inputs/aes_core.v`. Do not invent signal names or use
   names from unrelated designs.

4. **FR4 — Real output ports only.** Every string listed in
   `affected_outputs` for a given finding must be one of the declared
   output ports of the `aes_core` module, exactly as listed in
   `inputs/aes_core.v`.

## Tips

- Start by listing every register and wire declared in
  `inputs/aes_core.v`, then check each one against the signals and
  control flow described in `inputs/design_brief.md`. Anything present
  in the RTL but absent from the documented architecture deserves a
  closer look.
- Pay attention to registers that update unconditionally every cycle
  regardless of the documented control flow, and to comparators whose
  match value is a wide, unusual-looking constant.
- Trace forward from any suspicious comparator to see which signal it
  ultimately enables, and trace that signal forward to see which
  output register or output port it can influence.
- If you have access to a simulator, you can try driving the design's
  internal registers/inputs to reach a suspected rare condition and
  observe whether any output diverges from what the design brief
  promises — but this is a convenience, not a requirement, for
  completing the report.
- Confidence scores should reflect how strong your evidence is. Avoid
  flagging ordinary, well-documented control/datapath signals (such as
  the round counter or working-state register used for the documented
  round function) as high-confidence findings — reserve high
  confidence for genuinely unexplained logic.