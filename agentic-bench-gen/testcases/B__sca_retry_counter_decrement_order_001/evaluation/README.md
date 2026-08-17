# Evaluation: PIN-Check Retry Counter Fault Analysis

## What you are submitting

This task does **not** ask you to modify or resubmit any RTL. Your
deliverable is a single JSON answer file:

```
submission/vulnerability_report.json
```

No other file is graded. `evaluate.py` reads the reference artifacts under
`inputs/` (the RTL under test, its fault model, the reference testbench, and
the design brief) purely for context and optional corroboration — the
PASS/FAIL verdict is computed entirely from the content of your submitted
JSON report.

## Required fields

Your `vulnerability_report.json` must be a single JSON object with the
following top-level fields:

| Field | Type | Description |
|---|---|---|
| `vulnerable_transition` | string | The FSM state transition (naming a `source_state->dest_state` pair, spelled exactly as the `localparam` identifiers in `inputs/pin_check_fsm.v`) that is exploitable under the fault model in `inputs/fault_model.md`. |
| `glitch_window` | string | A description of the cycle(s), relative to the `pin_valid` strobe, during which the fault must land to succeed. |
| `remediation` | string | A concrete RTL-level change that closes the identified window. |
| `affected_signals` | array of strings | At least the retry-counter signal and the `auth_ok`/`locked_out` signals affected by the flaw. |
| `fault_free_behavior_preserved` | boolean | Whether your proposed remediation preserves the documented fault-free 3-attempt lockout sequence. |
| `fault_free_justification` | string | A short explanation of why the remediation does (or does not) preserve that sequence. |
| `state_names_referenced` | array of strings | State names you referenced in your analysis. Every entry must literally appear as a `localparam`/`parameter` identifier in `inputs/pin_check_fsm.v`. |
| `confidence` | number (0–1) | Your confidence in the finding. |
| `method` | string | One of `static_analysis`, `simulation`, or `both` — how you derived the finding. |

Refer to `public_spec.response_format` in the task specification for the
authoritative field list; the table above summarizes it.

## What `evaluate.py` checks

`evaluate.py` performs two categories of checks, one entry per requirement
ID, each emitting a single `[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>`
line:

### Schema/structure checks (FR1–FR4)

These verify that the required fields are present and well-typed:

- **FR1** — `vulnerable_transition`, `glitch_window`, and `remediation` are
  non-empty strings; `affected_signals` is an array of strings that names a
  retry-counter-like signal (e.g. something containing `attempt`, `retry`,
  or `counter`) and an `auth_ok`/`locked_out`-like signal.
- **FR2** — `fault_free_behavior_preserved` is present and boolean;
  `fault_free_justification` is present and a substantive (non-trivial)
  string.
- **FR3** — `state_names_referenced` is a non-empty array of strings, and
  every entry literally matches a state name declared as a `localparam` in
  `inputs/pin_check_fsm.v` (checked by parsing the RTL text directly, so
  this is grounded in the actual shipped design, not a fixed name list).
- **FR4** — `confidence` is a number in `[0, 1]`; `method` is one of
  `static_analysis`, `simulation`, `both`.

### Substantive correctness checks (SR1–SR4)

These grade the content of your findings against the hidden ground truth
described in the task's threat model and fault model. In line with the
public specification:

- **SR1** — `vulnerable_transition` must correctly identify the transition
  implicated by the fault model, naming the correct pair of states in the
  correct direction (not some unrelated transition, and not the reverse
  direction without qualifying language).
- **SR2** — `glitch_window` must correctly and specifically characterize the
  timing window in which the fault must land — tied to the relevant
  state-to-state edge with timing language connecting it to the
  comparison/decrement ordering, not a vague or overly broad claim (e.g.
  "any time"), and not pointing at an unrelated state as the landing point.
- **SR3** — `remediation` must describe a fix that actually closes the
  identified window, and it must do so **completely**. Concretely, the text
  must affirmatively describe **both** of the following, not just one of
  them:
  1. An early/speculative counter-update mechanism that can no longer be
     bypassed by skipping the post-comparison bookkeeping state (e.g.
     decrementing the retry counter as soon as a comparison attempt begins,
     or an equivalent atomic decrement-and-compare fix); **and**
  2. An explicit restoration/increment-back mechanism that fires
     specifically on a *successful* match outcome, so that a legitimate
     correct PIN does not permanently consume an attempt.

  A remediation that describes only the first part — moving the decrement
  earlier — without describing how a successful match's counter effect is
  reversed or offset, is **incomplete** and will be rejected, even if the
  early-decrement language itself is well-formed. Likewise, text that
  explicitly states or implies that no restoration/cancellation occurs
  (e.g. "the counter is not restored on a match", "without restoring the
  counter") will be rejected regardless of how the rest of the remediation
  reads. A single atomic merge of the comparison and the decrement into one
  state/cycle (such that there is inherently only one net counter update
  per outcome) is also acceptable, since it does not require separate
  restore language to guarantee correctness. Vague proposals ("add a
  watchdog", "add redundant logic") that do not address the underlying
  ordering are rejected outright.

- **SR4** — If you claim `fault_free_behavior_preserved: true`, this claim
  is checked for consistency **against the arithmetic and semantics implied
  by your own remediation description and justification**, not merely
  against superficial keyword presence. Specifically:

  - **Restoration must be tied to success, not failure.** A remediation or
    justification that describes restoring, cancelling, or incrementing the
    retry counter on a *failed* or *mismatched* comparison — rather than on
    a *successful* match — is rejected, **even if it uses the word
    "restore"**. Phrasing such as "restore the counter on a failed match",
    "restore on mismatch", or "increment on failure" describes an inverted
    scheme relative to the documented policy: if the counter is restored
    whenever a comparison *fails*, the net effect on a failed attempt is
    zero decrements (the early decrement is immediately cancelled), so the
    device would never actually consume a retry on a genuine wrong guess
    and the 3-consecutive-failure lockout could never trigger under
    fault-free operation. This check inspects the described *condition*
    under which restoration happens (success vs. failure/mismatch), not
    just whether the word "restore" appears somewhere in the text.

  - **The claimed attempt count must be exactly 3, not merely "not 2 or
    4".** Your `fault_free_justification` must be consistent with the
    documented exactly-3-consecutive-failures lockout. Any digit or number
    word other than `3`/`three` appearing in attempt/lockout context (e.g.
    "locks out after 2 attempts", "four failed tries", "five consecutive
    failures", "after 6 attempts") is treated as an inconsistency and
    rejected, regardless of how many other passages correctly say "3
    attempts" elsewhere in the text. This is a broadened check: it is not
    limited to catching only off-by-one values of 2 or 4 — any non-3
    attempt count mentioned in lockout context will fail this check.

  - **Net decrement arithmetic.** In addition to the above, the counting
    scheme your `remediation` field itself describes must be
    arithmetically consistent with **exactly one net counter decrement per
    failed attempt**. For example, a remediation that describes
    decrementing the counter once on entry to the comparison state *and*
    decrementing it again separately upon a failed outcome (with no
    compensating restore for that path) implies two net decrements per
    failed attempt, which would exhaust the retry budget in fewer than 3
    fault-free failed attempts. Describing a single early decrement with a
    restore that only fires on success (which does not affect the
    failed-attempt path at all), or a single atomic decrement-and-compare
    mechanism, both correctly yield one net decrement per failed attempt
    and are accepted.

  All three sub-checks above must pass for SR4 to pass; failing any one of
  them (an inverted restore-on-failure condition, a non-3 attempt count in
  lockout context, or an inconsistent net-decrement-per-failure scheme)
  causes SR4 to fail even if `fault_free_behavior_preserved` is asserted
  `true` and the text otherwise contains reassuring-sounding keywords like
  "restore" or "3 attempts".

Each SR check performs keyword/phrase and structural matching against your
submitted text; there is no single "magic phrase" required, but your answer
should be specific and unambiguous about the transition, timing window, and
remediation mechanism involved (including precisely which outcome —
success or failure — triggers restoration, and how many net decrements
occur per failed attempt), using the actual state names from the RTL.

## Role of the Verilog toolchain

`evaluate.py` may additionally attempt to compile and run
`evaluation/tb_stateskip.v` against `inputs/pin_check_fsm.v` using
`iverilog`/`vvp`. This is **purely corroborative and informational** — it
does not gate any PASS/FAIL verdict. All grading decisions are made by
inspecting the fields of your submitted `vulnerability_report.json` as
described above. If the optional simulation cannot be compiled or run for
any reason, grading proceeds unaffected based solely on your report's
content.

## Common reasons for failure

- Submitting no file, or a file that is not valid JSON.
- Omitting any of the required fields, or using the wrong type (e.g. a
  number for `confidence` outside `[0, 1]`, or a non-array for
  `affected_signals`).
- Referencing state names that do not appear verbatim in
  `inputs/pin_check_fsm.v`.
- Identifying the wrong transition, an overly vague timing window, or a
  remediation that does not actually address the ordering of the counter
  update relative to the comparison.
- Describing an early/speculative decrement without also describing how
  the counter is restored on a successful match (an incomplete fix that
  permanently penalizes legitimate successful authentications).
- Describing a remediation that restores or increments the counter on a
  *failed* or *mismatched* comparison instead of on a *successful* match —
  this inverts the intended semantics and is rejected even though the word
  "restore" appears in the text.
- Describing a remediation whose own counting scheme implies more than one
  net decrement per failed attempt (e.g. decrementing at two separate
  points on a failure with no offsetting restore), while still claiming
  the fault-free 3-attempt lockout sequence is preserved.
- Claiming fault-free behavior is preserved while the justification implies
  any attempt count other than exactly 3 before lockout (not just 2 or 4 —
  any other number in attempt/lockout context is rejected).