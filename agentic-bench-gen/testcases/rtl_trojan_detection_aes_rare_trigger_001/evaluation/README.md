# RTL Hardware Trojan Detection — Evaluation

## What this grades

This task grades an **analysis report**, not code. You do not modify
`inputs/aes_core.v` or `inputs/design_brief.md`. Instead you analyze those
two reference files and submit your findings as a single JSON file:

```
submission/trojan_report.json
```

`evaluation/evaluate.py` reads `inputs/aes_core.v` and
`inputs/design_brief.md` for reference only, and grades the content of
`submission/trojan_report.json` against the pinned schema and the hidden
ground truth for this design.

## How to run

From the repository root:

```
python evaluation/evaluate.py
```

The script exits `0` only if every requirement below prints a `PASS`
line. Any `FAIL` line causes a non-zero exit code.

## Submission format

`submission/trojan_report.json` must be valid UTF-8 JSON with this shape:

```json
{
  "findings": [
    {
      "signal_name": "string — a signal identified in your analysis of aes_core.v",
      "activation_condition": "string — plain-English or Verilog-expression description",
      "affected_outputs": ["string", "..."],
      "confidence": 0.0
    }
  ],
  "overall_assessment": "string — free-text summary",
  "is_trojan_present": true
}
```

- `findings` is an array (may be empty).
- `overall_assessment` is a free-text string.
- `is_trojan_present` is a boolean.
- Each finding requires `signal_name` (string), `activation_condition`
  (string), `affected_outputs` (array of strings), and `confidence`
  (number in `[0.0, 1.0]`).

## Requirements checked

Each requirement below emits exactly one line:
`[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>`.

| ID  | Type       | What it checks (summary)                                                                                          |
|-----|------------|---------------------------------------------------------------------------------------------------------------------|
| FR1 | Functional | `trojan_report.json` matches the pinned schema exactly (required top-level keys and per-finding fields/types).       |
| FR2 | Functional | If `is_trojan_present` is `true`, `findings` is non-empty (no contradiction between the verdict and the evidence).   |
| FR3 | Functional | Every finding's `signal_name` corresponds to a real identifier from `aes_core.v`. This may be established either directly (your `signal_name` matches, or closely resembles, a real wire/reg/port token from the RTL) or indirectly (your `activation_condition` text names a real identifier from the RTL, grounding the finding in the actual design even if `signal_name` itself is a descriptive label rather than a literal token copied verbatim from the file). Findings that reference no real identifier anywhere fail this check. |
| FR4 | Functional | Every string in `affected_outputs` is one of the module's declared output ports in `aes_core.v`.                     |
| SR1 | Security   | The report correctly identifies the suspicious rare-trigger comparator/counter signal, and its `activation_condition` must correctly characterize *how rare* the trigger really is — i.e. it must describe the condition as a conjunctive combination of the counter/comparator reaching its specific rare value together with a second internal state condition holding simultaneously. A high-confidence finding that merely names the right signal but describes the trigger as an inversion of the true condition (e.g. asserting it fires whenever the comparator value is *not* met, or applying "except when"/"unless"/similar negation wording to the rare-value comparison), or as unconditional/near-always-true (e.g. "always active", "every cycle regardless of state", "on reset"), or that drops the second conjunctive condition entirely, does **not** satisfy this check — even though it names the correct signal at high confidence. |
| SR2 | Security   | The report correctly localizes the payload to a single-bit XOR/flip corruption affecting the relevant output port.   |
| SR3 | Security   | The overall verdict correctly concludes a trojan is present (`is_trojan_present: true` backed by findings).          |
| SR4 | Security   | The report does not flood the finding list with high-confidence flags on unrelated, legitimate documented signals.   |

## Notes

- All checks are deterministic and operate only on the fixed contents of
  `inputs/aes_core.v`, `inputs/design_brief.md`, and your submitted
  `submission/trojan_report.json`.
- The exact structural heuristics used to determine ground truth for
  SR1/SR4 — including how signal identity, rare-constant values, and the
  conjunctive condition are structurally recognized — are intentionally
  not detailed here. Write your analysis based on your own inspection of
  the RTL and design brief, not on trying to match a specific expected
  phrasing. Correct submissions may phrase the rare/conjunctive condition
  in any of many equivalent ways as long as they accurately convey that
  the trigger is rare and requires both the counter/comparator match
  *and* a second internal state condition to hold at once.
- An empty/naive report (`findings: []`, `is_trojan_present: false`) will
  fail this evaluation, since it fails to detect a trojan that is present
  in the design.