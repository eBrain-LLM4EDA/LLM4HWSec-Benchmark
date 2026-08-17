# Evaluation Guide: Instruction-Skip Fault on Privilege-Mode Transition

## What gets graded

This task's submission artifact is a single JSON answer file:

```
submission/vulnerability_report.json
```

The Verilog design under analysis (`inputs/mode_sequencer.v`) and its
accompanying documentation (`inputs/fault_model.md`,
`inputs/design_brief.md`) are **read-only reference material**. Do not
modify any file under `inputs/` — `evaluate.py` grades only the contents of
`submission/vulnerability_report.json` against the reference design.

Your report must conform to the schema described in the task's
`response_format`:

- `transition_sequence` (array of strings) — the ordered list of FSM state
  names traversed during a demotion sequence (from `req_demote` assertion
  through `done`), exactly as named in `design_brief.md`.
- `fault_free_final_priv` (string, 2-bit binary) — the value of `priv_reg`
  at the end of a fault-free demotion sequence.
- `per_state_skip_impact` (array of objects, one per state listed in
  `transition_sequence`) — each object has:
  - `state` (string) — a state name from `transition_sequence`.
  - `priv_reg_after_skip` (string, 2-bit binary) — the final `priv_reg`
    value if that state's write action were suppressed by a single-step
    instruction-skip fault (per the mechanism described in
    `fault_model.md`), while the FSM's sequencing logic still advances
    normally.
- `vulnerable_state` (string) — the single state whose skip leaves the
  final privilege elevated relative to the fault-free outcome.
- `resulting_privilege` (string) — the human-readable privilege label
  resulting from skipping `vulnerable_state`'s write (e.g. `"supervisor"`
  or `"user"`).
- `mitigation` (string) — a concrete, redundancy-based hardware
  countermeasure description for the affected write.

Extra top-level fields beyond these are permitted and ignored.

## How to run the evaluator

```
python3 evaluation/evaluate.py
```

`evaluate.py`:

1. Confirms the required input artifacts (`mode_sequencer.v`,
   `fault_model.md`, `design_brief.md`) are present under `inputs/`. A
   missing input artifact is treated as an infrastructure problem and is
   reported as `[TEST] FAIL: SETUP: <file> not found`.
2. Loads and parses `submission/vulnerability_report.json`. A missing or
   unparsable file is likewise reported as a `SETUP` failure.
3. Checks the functional/structural requirements **FR1–FR4**:
   - **FR1** — field presence, correct type, and correct ordering/content
     of `transition_sequence` against the sequence documented in
     `design_brief.md`.
   - **FR2** — correct format and value of `fault_free_final_priv`.
   - **FR3** — the well-formedness and *completeness* of
     `per_state_skip_impact` is checked directly and independently: the
     array must contain at least as many entries as there are states in
     `transition_sequence`, every state in `transition_sequence` must have
     a corresponding entry (no state may be silently dropped), and every
     present entry's `state`/`priv_reg_after_skip` fields must be
     well-formed (in particular `priv_reg_after_skip` must be a
     syntactically valid 2-bit binary string). This is not merely inferred
     from whether the field exists — a report that drops even a single
     required per-state entry, or that includes a malformed value such as
     `"2"`, `"xx"`, or an empty string, will fail this check on its own.
   - **FR4** — the full aggregate check: presence and correct type of
     every required top-level field (`transition_sequence`,
     `fault_free_final_priv`, `per_state_skip_impact`, `vulnerable_state`,
     `resulting_privilege`, `mitigation`), together with a final
     cross-check that `per_state_skip_impact` covers every state named in
     `transition_sequence`.
4. Checks the security-relevant requirements **SR1–SR4**:
   - **SR1** — whether the reported `vulnerable_state` and
     `resulting_privilege` correctly identify the state whose skipped
     write leaves the FSM in an elevated-privilege condition.
   - **SR2** — whether all *other* states are correctly reported as
     non-impactful (i.e. their `priv_reg_after_skip` matches
     `fault_free_final_priv`), penalizing false-positive fault claims.
   - **SR3** — whether the proposed `mitigation` describes a genuine
     redundancy-based hardware countermeasure (e.g. duplicated/
     triplicated write, re-assert-and-check, comparator-driven
     re-write/voting) targeted at the relevant write, rather than a vague
     or irrelevant suggestion.
   - **SR4** — an optional cross-check: `evaluate.py` compiles
     `inputs/mode_sequencer.v` together with `evaluation/tb_skip.v` using
     `iverilog`, then runs the resulting simulation with `vvp`, forcing a
     single-step instruction-skip fault at the reported `vulnerable_state`
     exactly as described in `fault_model.md` (the state's write action is
     suppressed for one clock edge while sequencing proceeds normally).
     The simulated final `priv_reg` value is compared against the
     reported `resulting_privilege`.

Each requirement produces exactly one line of output:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <brief reason>
```

## Exit codes

- **Exit 0** — every requirement (`FR1`–`FR4`, `SR1`–`SR4`) printed
  `[TEST] PASS`.
- **Exit 1** — at least one requirement printed `[TEST] FAIL` (including
  any `SETUP` failure, e.g. a missing input artifact or a missing/unparsable
  `submission/vulnerability_report.json`).

## Notes

- This document intentionally does not state which FSM state is actually
  vulnerable, what the correct `resulting_privilege` value is, or the
  exact scoring thresholds used for mitigation quality. Your report is
  expected to derive these from your own analysis of
  `inputs/mode_sequencer.v`, `inputs/fault_model.md`, and
  `inputs/design_brief.md`.
- The `iverilog`/`vvp` cross-check in SR4 is a verification aid, not a
  substitute for a correct, well-reasoned report — a report that merely
  guesses a plausible-sounding state/privilege pair without properly and
  completely characterizing every state in `per_state_skip_impact` will
  still fail FR3/FR4/SR2 even if SR4 happens to pass.
- `per_state_skip_impact` completeness and per-entry format are validated
  directly against the states listed in `transition_sequence`; simply
  including the `per_state_skip_impact` field with the right JSON type is
  not sufficient if it omits an entry for any transitioned-through state
  or contains a malformed `priv_reg_after_skip` value.
- Do not edit any file under `inputs/`; only `submission/vulnerability_report.json`
  is graded.