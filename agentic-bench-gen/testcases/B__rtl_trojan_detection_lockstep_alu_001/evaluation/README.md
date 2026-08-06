# RTL Trojan Detection — Evaluation Harness

## Task

Analyze `inputs/lockstep_alu.v` (a dual-channel lockstep ALU) and submit a
structured Trojan-finding report at:

```
submission/trojan_report.json
```

`evaluate.py` grades the **content of that submission file** against a
hidden ground truth describing a compensating Trojan embedded in the RTL
(a rare-condition trigger that both corrupts the architectural result and
forges the mismatch/integrity signal that would otherwise catch it).

## Running the harness

From the repository root:

```
python3 evaluation/evaluate.py
```

The script:

1. Loads `submission/trojan_report.json`. If the file is missing, it emits
   `[TEST] FAIL: SETUP: submission/trojan_report.json not found` and exits
   non-zero immediately. If the file **exists but is structurally
   malformed** (invalid JSON syntax, or the top-level JSON value is not an
   object), this is **not** treated as a SETUP failure: the script parses
   defensively, records the parse problem, and reports it as an `FR1`
   requirement failure (`[TEST] FAIL: FR1: invalid JSON: ...` or
   `[TEST] FAIL: FR1: top-level JSON value is not an object (got ...)`),
   then continues running every other check against an empty fallback
   report so all requirements still emit a deterministic verdict.
2. Checks structural/functional requirements `FR1`–`FR4` against the report
   (required top-level fields, well-formed candidate objects, presence of a
   candidate that pins down the exact rare trigger condition, and coverage
   of both the result-corruption and mismatch-masking findings).
3. Checks substantive security requirements `SR1`–`SR5` against the report's
   content: correct identification of the trigger condition, of the bit-3
   result corruption, of the mismatch-masking behavior, correct ranking of
   the true findings among the highest-confidence candidates, and that a
   naive/empty submission is correctly rejected.
4. Computes and prints an informational `[METRICS]` JSON line summarizing
   `detection_rate`, `false_positive_rate`, `trigger_payload_localization`,
   and `confidence_calibration` (see below). This line is diagnostic only
   and never affects any `[TEST]` verdict or the exit code.
5. Optionally attempts to compile and simulate `inputs/lockstep_alu.v` with
   `evaluation/tb_trigger_check.v` via `iverilog`/`vvp`, printing the
   observed `architectural_result`/`mismatch` values for benign and
   trigger vectors as `[INFO]` lines. **This simulation is purely
   informational corroboration that the ground-truth trigger genuinely
   exists in the shipped RTL.** It never affects any `[TEST]` verdict —
   this domain grades the submitted answer file, not the RTL itself, and
   the simulation step is skipped gracefully (with an `[INFO]` message,
   not a failure) if `iverilog`/`vvp` are unavailable or the compile fails.

## Marker format

Each checked requirement emits exactly one line:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <brief reason>
```

Requirement IDs correspond to the task's functional requirements
(`FR1`–`FR4`) and hidden security requirements (`SR1`–`SR5`).

## Exit code

- Exit code `0`: every checked requirement emitted `[TEST] PASS`.
- Exit code `1`: at least one requirement emitted `[TEST] FAIL` (or a
  `SETUP` failure occurred because the submission file was missing).

## Requirement semantics (notable details)

- **FR1** requires `candidates` to be an array, `overall_confidence` to be
  a number in `[0,1]`, and `summary` to be a non-empty string. A submission
  file that fails to parse as JSON, or whose top-level value is not a JSON
  object, fails FR1 with a specific reason rather than crashing the
  harness or being misclassified as a SETUP problem.
- **FR4** requires two *distinct roles* to be covered by the candidates,
  each with **specific, mechanism-naming language**:
  - a result-corruption role: some candidate must name a concrete
    construct or mechanism (e.g. `architectural_result`, a bit index such
    as `[3]`/`bit 3`, a mux, or explicit flip/xor/toggle/invert language
    tied to the result) — a vague "suspicious module" or "may produce an
    incorrect result" statement that names no concrete mechanism does
    **not** satisfy this role even if some other candidate is well
    specified;
  - a mismatch-masking role: some candidate must name masking/forcing/
    suppression language tied to the `mismatch` signal or the integrity
    checker itself.
- **SR3** requires a candidate with `confidence >= 0.5` whose rationale
  **affirmatively asserts** that the `mismatch` signal is being forced,
  masked, suppressed, hidden, or gated (verbs like "forced", "masked",
  "suppressed", "hidden from", "gated off despite disagreement"). Merely
  mentioning the word "mismatch" near unrelated or weakly related text is
  not sufficient. Rationale that reads as **exculpatory or neutral** —
  e.g. describing the comparator as "legitimate", stating it "behaves as
  expected", or explicitly stating "no evidence of forcing/masking/
  suppression/hiding" — does **not** satisfy SR3, even if the word
  "mismatch" and some masking-adjacent vocabulary both appear in the same
  rationale.
- **SR4** is a **ranking/confidence-calibration** check evaluated over a
  *set* of top candidates, not a single candidate's text. Concretely:
  1. Sort all well-formed candidates by `confidence` descending.
  2. Let `N = max(2, number of candidates with confidence >= 0.6)`, capped
     at `3` and at the total number of candidates. Take the top-`N`
     candidates by confidence as the window under consideration.
  3. Within that window, restrict attention to candidates whose own
     `confidence >= 0.6` ("qualifying" candidates).
  4. SR4 **passes** if, among the qualifying candidates in the window,
     **at least one** satisfies the exact-trigger criterion (the SR1
     pattern: opcode reference co-occurring with both operand values) **and**
     **at least one** (which may be the *same* candidate or a *different*
     one) satisfies the bit-3-corruption criterion (SR2 pattern) **or** the
     mismatch-masking criterion (SR3 pattern).
  5. SR4 **fails** if no qualifying candidate in the top-`N` window
     satisfies the trigger criterion, or none satisfies the corruption/
     masking criterion — i.e. if the correct finding(s) only appear at
     confidence below 0.6, or are ranked outside the computed top-`N`
     window, they are considered "buried" and SR4 fails.

  **Splitting the trigger, the result-corruption payload, and the
  mismatch-masking payload into separate, individually high-confidence
  candidates is an acceptable and expected way to satisfy SR4.** A report
  is not required to cram the trigger condition, the bit-3 flip, and the
  mismatch-masking behavior into a single candidate's rationale text —
  reporting them as three distinct top-ranked candidates (e.g. one for the
  trigger comparator, one for the result mux, one for the mismatch mask),
  each with its own high confidence and rationale, satisfies SR4 exactly as
  well as a single combined candidate would.

- **SR5** independently inspects the parsed submission JSON for the
  hallmark shape of the shipped naive/empty baseline: an empty `candidates`
  array **and** `overall_confidence == 0`. This check is fully decoupled
  from the pass/fail outcome of FR2, FR3, FR4, or SR1–SR4 — it cannot pass
  "by construction" via those other checks. If the hallmark shape is
  present, SR5 fails unconditionally; otherwise it passes.

## Metrics output

In addition to the per-requirement `[TEST]` lines, `evaluate.py` prints a
single informational line of the form:

```
[METRICS] {"detection_rate": <float>, "false_positive_rate": <float>, "trigger_payload_localization": <float>, "confidence_calibration": <float>}
```

computed as follows:

- **`detection_rate`**: fraction of `SR1`–`SR4` that passed (count of
  passing checks divided by 4).
- **`false_positive_rate`**: among candidates with `confidence >= 0.6`,
  the fraction whose combined text matches none of the trigger-condition,
  bit-3-corruption, mismatch-masking, or FR4 result/mask role patterns
  (i.e. high-confidence findings unrelated to any real ground-truth
  element). If there are no candidates with `confidence >= 0.6`, this is
  reported as `0.0`.
- **`trigger_payload_localization`**: a coarse score based on how many of
  `SR1`, `SR2`, `SR3` passed — `1.0` if all three passed, `0.66` if
  exactly two passed, `0.33` if exactly one passed, `0.0` if none passed.
- **`confidence_calibration`**: `1.0` if `SR4` passed, else `0.0`.

**This `[METRICS]` line is purely informational/diagnostic.** It does not
gate, override, or otherwise influence any `[TEST] PASS`/`[TEST] FAIL`
verdict or the process exit code, which are determined solely by the
FR1–FR4 and SR1–SR5 checks described above.

## What is graded vs. what is reference-only

- **Graded (drives PASS/FAIL):** the contents of
  `submission/trojan_report.json` — its top-level fields, each candidate's
  fields, and the substantive correctness/ranking of its findings.
- **Reference-only (never gates PASS/FAIL):** `inputs/lockstep_alu.v`,
  `inputs/design_brief.md`, and `inputs/testbench_stub.v` are read/simulated
  only to corroborate that the hidden ground truth is genuinely present in
  the shipped artifact. Participants do not edit these files, and no check
  in this harness inspects their contents to decide a verdict.