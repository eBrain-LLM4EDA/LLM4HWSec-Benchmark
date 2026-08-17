# Evaluation: Bellcore-style Fault in CRT Recombination

## What is graded

This is an **analysis-report** task. Participants do **not** modify anything
under `inputs/`. They submit a single answer file:

```
submission/vulnerability_report.json
```

`evaluate.py` reads the reference RTL/testbench artifacts under `inputs/`
(`crt_recombine.v`, `crt_reference.v`, `tb_crt_recombine.v`, `fault_model.md`,
`design_brief.md`) purely for cross-checking purposes, and grades the
**content** of the submitted JSON report against the hidden ground truth. No
credit is given for restating or copying phrases from the input artifacts —
the report must demonstrate that the participant actually diagnosed the
vulnerability.

The submission schema (`response_format` in the task spec) requires exactly
five non-empty string fields:

- `vulnerable_register`
- `fault_model`
- `trigger_scenario`
- `missing_verification_step`
- `recommended_fix`

## How each requirement is checked

### Functional requirements (schema / presence / basic shape)

- **FR1** — `submission/vulnerability_report.json` must exist, parse as
  valid JSON, and contain all five required fields as non-empty strings.
  A missing file is a `SETUP` failure; malformed JSON or missing/empty
  fields are ordinary `FR1` failures.
- **FR2** — `trigger_scenario` must describe a concrete, reproducible
  fault: a specific `msg_in` value in the valid range (0-142) and a named
  fault register (`sig_p_reg` or `sig_q_reg`). This is checked by
  extracting the value/register from the text and then **actually running
  a simulation** (see below) that forces that register to a wrong value at
  the recombination point and confirms `result_out` diverges from the
  golden `crt_reference.v` output while `done` asserts in both.
- **FR3** — `vulnerable_register` must designate a single **primary**
  branch register from `inputs/crt_recombine.v` (`sig_p_reg` or
  `sig_q_reg`) as the unverified register whose fault propagates to
  `result_out` without detection. See "Primary-register determination"
  below for exactly how this is decided — a report is not penalized merely
  for mentioning both register names somewhere in the field.
- **FR4** — `recommended_fix` must describe a concrete RTL-level
  countermeasure, i.e. a recompute/redundant-computation/cross-check
  mechanism, not merely a generic or unrelated mitigation (e.g. parity on
  `msg_in`, a checksum unrelated to the branch arithmetic, a watchdog
  timer).

### Security requirements (substantive correctness)

- **SR1** — The **primary** register determined from `vulnerable_register`
  (see below) must also be the register referenced (as the primary/sole
  fault target) in `trigger_scenario`. Reports that are genuinely
  inconsistent — naming one register as the primary answer in one field and
  a *different* register as the primary answer in the other — fail this
  check. Reports that name a single primary register in
  `vulnerable_register` and additionally, in a clearly secondary or
  contrastive remark, mention the other register (e.g. to note it is
  symmetrically exposed in principle) are **not** penalized, as long as
  that same primary register is the one used in `trigger_scenario`.
- **SR2** — `fault_model` must describe a **single, transient,
  register-level** corruption (bit-flip, stuck value, forced value,
  single-event upset, glitch) consistent with the classic Bellcore/BDL
  differential fault model — not a requirement for simultaneous faults in
  both branches, nor a purely algorithmic/software-level fault claim.
- **SR3** — `missing_verification_step` and `recommended_fix`, taken
  together, must express **recompute-and-compare** semantics: an
  independent recomputation of (at least) one branch result, or an
  equivalent cross-check between the two branches, performed before
  `result_out`/`done` are committed. Proposals that are only generic error
  detection unrelated to the actual modular arithmetic (parity, CRC,
  timeout/watchdog) do not satisfy this, even if such text happens to be
  present alongside irrelevant claims — the check looks for genuine
  recompute/cross-check language, not just its absence of other words.
- **SR4** — The `trigger_scenario` must be **reproducible**: simulating
  `inputs/crt_recombine.v` with the named register forced to an incorrect
  value at the point described (after that branch is computed, before
  recombination) for the stated `msg_in` must yield a `result_out` that
  differs from `inputs/crt_reference.v`'s `result_out` for the same
  `msg_in`, while `done` is asserted by both modules. This uses the same
  underlying simulation as FR2 (they check overlapping but distinct
  aspects: FR2 is "is a concrete scenario stated", SR4 is "does that exact
  scenario reproduce").

## Primary-register determination (FR3 / SR1)

A correct report will frequently, and legitimately, discuss *both*
`sig_p_reg` and `sig_q_reg` in its `vulnerable_register` field — for
example to explain that the recombination stage is symmetric and that the
*other* branch register is, in principle, equally exposed, even though the
report is designating one specific register as *the* answer being
reported. Naively failing any field that contains both identifiers as
whole-word tokens would incorrectly reject such reports. FR3 and SR1
therefore use a **primary-register determination** instead of a flat
token-presence scan:

1. The field text is split into sentences.
2. The **first** sentence that makes an unqualified assertion naming one of
   `sig_p_reg` / `sig_q_reg` as *the* vulnerable/unverified branch register
   (e.g. "`sig_p_reg` is the unverified branch register...", "`sig_p_reg`
   ... is the vulnerable register", "the vulnerable register is
   `sig_p_reg`") establishes that register as the **primary** answer.
3. Any **later** mention of the *other* register name is treated as
   **non-disqualifying** if it is introduced by a contrastive or
   explanatory marker — words/phrases such as `note`, `also`, `similarly`,
   `symmetrically`, `in contrast`, `unlike`, `whereas`, `by contrast` — or
   otherwise appears in a clause that does not itself assert that other
   register as *the* answer with equal or unqualified certainty. Such
   mentions are read as explanatory color, not as a second candidate
   answer.
4. The field is only treated as genuinely **ambiguous** (and FR3/SR1
   fail) if the text asserts *both* registers as candidates with no
   primary distinguished — e.g. "either `sig_p_reg` or `sig_q_reg` could be
   the vulnerable register", "could be either... ", or a bare list of both
   names with no sentence designating one as the primary/asserted answer.
5. If neither register name is found in the field at all, FR3 fails for
   want of a named register.

SR1 then checks that this same primary register (from
`vulnerable_register`) is also the register named/forced in
`trigger_scenario` (using the same primary-register determination logic
applied to that field, falling back to whichever single register token is
present if only one appears there).

A regression fixture at `evaluation/private/golden_fixture.json` encodes a
representative golden-style `vulnerable_register` value — a primary
sentence naming `sig_p_reg` as *the* unverified register, followed by a
secondary sentence beginning "Note that `sig_q_reg` ... is also
symmetrically exposed ..." — and `evaluate.py` runs a small internal
self-check confirming `determine_primary_register` returns `sig_p_reg` for
that fixture. This guards against a regression of the false-rejection bug
this logic was introduced to fix (a golden-style report being rejected
merely for mentioning both register names anywhere in the field).

## Simulation cross-check mechanics

For FR2/SR4, `evaluate.py`:

1. Parses `trigger_scenario` for an integer `msg_in` in `[0, 142]` and for
   the primary register (via the same primary-register determination used
   for FR3, falling back to a single-token match if the field only
   mentions one register).
2. Instantiates a parameterized testbench
   (`evaluation/fault_sim_harness.v`) that drives both
   `inputs/crt_recombine.v` (as `dut`) and `inputs/crt_reference.v` (as
   `golden`) with identical `clk`/`rst_n`/`start`/`msg_in` stimulus.
3. At the cycle after the named register would normally hold its correct,
   computed branch value, the harness force-overrides `dut.<register>`
   to `original_value XOR 8'hFF` (guaranteed different from the correct
   value for any 8-bit quantity) and then releases the force, mirroring
   the single-transient-register perturbation described in
   `inputs/fault_model.md`.
4. Both modules are allowed to run to completion; the harness prints a
   single deterministic result line reporting both modules' `result_out`
   and `done`.
5. `evaluate.py` parses that line and checks: `dut_done == 1`,
   `ref_done == 1`, and `dut_result != ref_result`.

If no valid `(msg_in, register)` pair can be extracted from
`trigger_scenario`, a small set of deterministic fallback vectors is tried
before failing outright, so that reports which state the scenario in
slightly different but still parseable phrasing are not unfairly
penalized. Compilation failures, timeouts, or crashes of the simulation
are treated as ordinary check failures (not `SETUP`), since they indicate
the submitted RTL cross-check environment could not be exercised as
described — this only happens due to bad extraction from the submission,
since the shipped `inputs/*.v` files themselves are fixed and known-good.

## Baseline and mutants

- The shipped **naive baseline** ships `vulnerability_report.json` with
  empty or placeholder (`"unknown"`) string fields. It fails FR1
  immediately (empty fields), and therefore also fails every SR check
  which depends on those fields being substantively populated. It is
  expected to fail every requirement and exit non-zero.
- A **correct submission** may use entirely different wording, field
  ordering, or explanatory style than any example — all checks are
  content/behavior-based (JSON field checks, primary-register
  determination, keyword/semantic scans tied to concrete engineering
  meaning, and an actual RTL simulation), never dependent on matching the
  baseline's or any particular phrasing. A correct submission may also
  mention the non-primary register in a secondary/contrastive remark
  without being penalized, per the primary-register determination logic
  above.
- **Mutants** (e.g. a report that swaps in the wrong register, asserts
  both registers as equally-likely candidates with no primary
  distinguished, claims a multi-register fault is required, proposes only
  a watchdog timer, or gives a trigger scenario that does not actually
  reproduce under simulation) are expected to fail the corresponding
  SR/FR check(s).

## Output format

Every requirement in the requirement map emits exactly one line:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <brief reason>
```

`evaluate.py` exits `0` only if all FR1-FR4 and SR1-SR4 checks pass, and
exits non-zero otherwise. Infrastructure problems (missing input files or
missing harness files) are reported as
`[TEST] FAIL: SETUP: <path> not found` and are excluded from mutation
scoring; a missing/unparseable `submission/vulnerability_report.json` is
reported under `FR1` (or `SETUP` if the file itself is absent), not
silently skipped.