# Evaluation: Precharged Bus Hamming-Weight Leakage

## What is graded

This task uses the **report_grading** evaluation mode. The participant does
**not** modify any file under `inputs/`. The only artifact that is graded is:

```
submission/vulnerability_report.json
```

`evaluate.py` reads the reference RTL and documentation under `inputs/`
(`precharge_bus_wrapper.v`, `fault_model.json`, `design_brief.md`,
`activity_trace_template.txt`) purely as ground-truth context for grading —
it does not grade those files, and it does not execute or modify them except
for an **optional, non-authoritative** simulation cross-check described
below.

## What the report must show

`precharge_bus_wrapper` transports an 8-bit secret data word (`data_in`)
across a shared bus (`dbus[7:0]`) using a two-phase precharge/evaluate
protocol. Because every transfer's precharge phase drives `dbus` to a fixed,
data-independent baseline, the number of bus lines that transition when the
evaluate phase subsequently drives `dbus` to the data word is exactly the
Hamming weight of that data word. This is a classic bus power/EM
side-channel: an attacker who watches per-cycle switching activity on
`dbus` (no logical access required) obtains a low-noise, per-transfer
Hamming-weight leak of the secret operand.

A correct vulnerability report must:

- Identify the leaking phase as `evaluate` (the precharge→evaluate
  transition), not `precharge` alone.
- Identify the full `dbus[7:0]` bus (all 8 bit lines) as the affected nets,
  not a partial subset.
- Describe a Hamming-weight/transition-count-based leakage metric.
- Propose a mitigation that achieves **constant per-transfer transition
  count** (e.g. transmitting the bitwise complement of the data word as a
  companion word, dual-rail/differential encoding, or another
  constant-Hamming-weight encoding), while explicitly affirming that
  correct data transport (`dbus` still conveys `data_in`, `valid` still
  pulses correctly) is preserved.
- Report `transfer_timing` offsets consistent with the module's documented
  two-cycle transfer latency: precharge at `load_cycle + 1`, evaluate at
  `load_cycle + 2`.

## Requirements checked

### Functional requirements (schema / structural)

- **FR1** — `vulnerability_report.json` is valid JSON containing all
  required top-level keys with the correct types: `leaking_phase` (string),
  `affected_nets` (array of strings), `leakage_metric` (string),
  `mitigation` (string), `functional_equivalence_claim` (bool or string),
  `transfer_timing` (object).
- **FR2** — Every entry in `affected_nets` textually corresponds to the
  `dbus` port or its constituent bit indices as actually declared in
  `inputs/precharge_bus_wrapper.v` (not an invented net name).
- **FR3** — `mitigation` names a concrete, bus-activity-relevant
  countermeasure technique (e.g. dual-rail, complementary/complement
  encoding, constant-weight/constant-Hamming encoding, random masking),
  rather than a generic or unrelated security statement.
- **FR4** — `transfer_timing` is an object with integer
  `precharge_cycle_offset` and `evaluate_cycle_offset` fields.

### Security requirements (substantive correctness)

- **SR1** — `leaking_phase` is exactly `"evaluate"` (case-insensitive,
  trimmed).
- **SR2** — `affected_nets` covers the full `dbus[7:0]` bus (a whole-bus
  token, or all 8 individual bit entries), not a partial subset.
- **SR3** — `leakage_metric` semantically describes a
  Hamming-weight/transition-count/switching-activity metric, not an
  unrelated metric such as pure timing delay or fault count.
- **SR4** — `mitigation` specifically achieves constant per-transfer
  transition count (complementary-bit companion word, dual-rail, or
  constant-Hamming-weight encoding — plain random masking alone is
  insufficient because it does not guarantee constant weight), **and**
  `functional_equivalence_claim` is affirmative.
- **SR5** — `transfer_timing.precharge_cycle_offset == 1` and
  `transfer_timing.evaluate_cycle_offset == 2`, matching the two-cycle
  transfer latency documented in `inputs/design_brief.md`
  (precharge at `load+1`, evaluate at `load+2`). If `iverilog`/`vvp` are
  available on the toolchain, `evaluation/tb_check.v` is optionally
  compiled against `inputs/precharge_bus_wrapper.v` to empirically
  cross-check these offsets against the reference RTL's actual behavior;
  this simulation is a supplementary sanity check only — the PASS/FAIL
  verdict for SR5 is always decided from the documented ground-truth
  offsets, so a missing or unavailable toolchain never blocks grading.

## Pass/fail semantics

- Each of the 9 requirements (`FR1`–`FR4`, `SR1`–`SR5`) emits exactly one
  line: `[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>`.
- `evaluate.py` exits `0` only if all 9 checks pass, and non-zero otherwise.
- If `submission/vulnerability_report.json` is missing, `evaluate.py` emits
  `[TEST] FAIL: SETUP: submission/vulnerability_report.json not found` and
  exits `1` immediately.
- The shipped **baseline** submission (an empty/placeholder report, or one
  reporting `leaking_phase="none"`, a single affected bit, and an unrelated
  mitigation) is expected to **fail** multiple checks (at minimum SR1, SR2,
  SR3, SR4, and possibly FR1/FR3 depending on which placeholder fields are
  present).
- A submission that correctly reports the evaluate-phase Hamming-weight
  leak across the full bus, with a constant-weight-balancing mitigation
  that preserves functional correctness and the correct transfer timing
  offsets, is expected to **pass** all 9 checks — regardless of wording,
  field ordering, or JSON formatting style, as long as the required
  substantive content is present.