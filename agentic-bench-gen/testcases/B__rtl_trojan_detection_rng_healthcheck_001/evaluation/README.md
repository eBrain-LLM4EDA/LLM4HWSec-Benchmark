# RTL Trojan Detection Evaluation — `lfsr_rng` RNG + Health Monitor

## What is graded

This task is graded as an **analysis report**, not as code. You (the participant)
must **not** modify any files under `inputs/`. Your only deliverable is:

```
submission/trojan_report.json
```

`evaluation/evaluate.py` reads the reference RTL under `inputs/` (specifically
`inputs/lfsr_rng.v`, `inputs/design_brief.md`, `inputs/testbench_stub.v`) purely
as context, and independently simulates `inputs/lfsr_rng.v` with `iverilog`/`vvp`
to establish ground-truth facts (the true cycle period and whether
`health_error` ever asserts). The PASS/FAIL verdicts are computed **against your
submitted report**, cross-checked against that ground truth.

If `submission/trojan_report.json` is missing or not valid JSON, every
requirement fails with a `SETUP` reason and the run exits non-zero.

## Report format (functional requirements)

Your report must be a single JSON object:

```json
{
  "findings": [
    {
      "id": "F1",
      "location": "feedback_logic always block (state advance)",
      "description": "...",
      "confidence": 0.9
    }
  ],
  "summary": "...",
  "tool_version": "..."
}
```

- **FR1** — `findings` is an array; `summary` and `tool_version` are strings;
  every finding has `id`, `location`, `description`, and a numeric `confidence`
  in `[0,1]`.
- **FR2** — At least one finding's `location`/`description` refers to the
  feedback/next-state/tap logic of the LFSR (the block that computes the next
  state bit from the current state), using vocabulary tied to the real design
  (feedback, tap, next-state, state register).
- **FR3** — At least one finding refers to the health/repetition-monitor logic
  (health_error, repetition counter, alarm), using vocabulary tied to the real
  design.
- **FR4** — Somewhere in the findings or summary, you must state a numeric
  period (an integer count of cycles before `rand_out` repeats).

These are purely structural/format checks — any report that supplies the
required fields and vocabulary passes, regardless of writing style, finding
ordering, or naming of `id` values.

## Substantive requirements (security requirements)

These check that your report's *content* is actually correct about the design,
not merely well-formed:

- **SR1** — Your feedback-logic finding must correctly identify that the
  implemented polynomial **omits the x^6 tap** relative to the documented
  `x^8+x^6+x^5+x^4+1` (taps 8,6,5,4). Phrasing that names bit/tap 6, or that
  enumerates the implemented taps as missing 6 (e.g. as `{8,5,4}` 1-indexed or
  `{7,4,3}` 0-indexed), is accepted. A vague "feedback logic looks different"
  claim without naming the missing tap does **not** satisfy SR1.

- **SR2** — Your health-monitor finding must explain **why** `health_error`
  fails to catch the resulting short cycle: the repetition counter is reset/
  suppressed whenever `rand_out` is `0x00` (a zero-crossing), not a generic
  "the health check might have a bug" statement. This is cross-checked by an
  independent simulation (`evaluation/tb_period_health.v` driven through
  `iverilog`/`vvp`) confirming `health_error` never asserts over 300+ cycles
  despite the abnormally short period.

- **SR3** — Somewhere in your report you must state a numeric period estimate
  that falls in **[20, 40]** cycles (ground truth is 28, confirmed by
  simulation). Claiming the full 255-cycle maximal-length period, or omitting
  a period entirely, fails SR3.

- **SR4** — Your report must **not** claim that `health_error` is working
  correctly / correctly flags the bias, and must **not** conclude "no trojan
  found". At least one finding that ties together the feedback defect and the
  health-monitor defect (or, absent an explicit combined finding, the more
  relevant of the two individual findings) must carry `confidence >= 0.5`.

## Toolchain use

`evaluate.py` invokes `iverilog` and `vvp` on `inputs/lfsr_rng.v` together with
a bundled testbench (`evaluation/tb_period_health.v`) to independently derive:

- `PERIOD=<n>` — the true number of cycles before `rand_out` repeats a
  previously seen value, starting after `output_valid` first asserts.
- `HEALTH_ERROR_SEEN=<0|1>` — whether `health_error` ever asserted over the
  simulated run.

These simulated facts are used to corroborate/validate your SR2/SR3 claims;
they do not replace the requirement to state the finding in your report.

## Determinism

All checks are deterministic: fixed seed (`8'hA5` per the DUT's own reset
behavior), fixed stimulus, fixed cycle counts, and fixed timeouts on all
subprocess invocations. No wall-clock-dependent behavior is used for verdicts.

## Exit behavior

`evaluate.py` prints one line per requirement:

```
[TEST] PASS: <ID>
[TEST] FAIL: <ID>: <reason>
```

for `ID` in `FR1, FR2, FR3, FR4, SR1, SR2, SR3, SR4`. The process exits `0`
only if every requirement passes; otherwise it exits non-zero.