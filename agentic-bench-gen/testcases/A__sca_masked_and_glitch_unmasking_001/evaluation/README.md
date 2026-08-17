# Evaluation: Glitch-Induced Unmasking in a Combinational Masked AND

## How to run

```
python3 evaluation/evaluate.py
```

The script is self-contained (Python standard library only) and requires
no arguments. It reads fixed input artifacts and grades a submitted
answer file; it does not modify anything under `inputs/`.

## Inputs read

`evaluate.py` reads exactly four artifacts under `inputs/`:

- `inputs/masked_and.v` — the RTL module under review.
- `inputs/fault_model.json` — the attacker/observation model for this review.
- `inputs/design_brief.md` — the functional description and review instructions.
- `inputs/sim_trace.vcd.txt` — a plain-text stimulus/response table for the module.

If any of these four files is missing, the script prints
`[TEST] FAIL: SETUP: <path> not found` and exits non-zero.

## Submission graded

Participants submit a single file:

```
submission/vulnerability_report.json
```

This must be valid UTF-8 JSON matching the schema described in the task's
public interface: `suspect_nets` (array of strings), `algebraic_masking_correct`
(boolean), `vulnerability_summary` (string, >=40 characters),
`hardening_proposal` (object with `registers_to_add`: array of strings and
`placement_description`: string, >=40 characters), and `confidence`
(number in [0.0, 1.0]).

If the submission file is missing entirely, the script prints
`[TEST] FAIL: SETUP: submission/vulnerability_report.json not found` and
exits non-zero immediately (this is treated as an infrastructure problem,
not a graded requirement failure).

If the submission file **exists** but is **not valid JSON** (e.g.
truncated, malformed, or containing a bare `{`), or if it parses to a
JSON value that is not a top-level object, the script does **not** crash
and does **not** silently treat this as a pass. Instead it cleanly emits:

```
[TEST] FAIL: FR1: <path> is not valid JSON: <parse error detail>
```

(or an analogous "top-level value is not an object" reason), with no
Python traceback, and every other requirement (FR2-FR4, SR1-SR3) is then
evaluated against an effectively empty report and also fails cleanly with
its own descriptive `[TEST] FAIL: <id>: ...` line (e.g. "suspect_nets
missing or not a list of strings"). The script always exits non-zero in
this case, and every requirement id in the requirement map still produces
exactly one PASS/FAIL line — nothing is ever skipped or left to error out
uncaught.

## What is checked

The script emits one `[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>`
line per requirement, and exits 0 only if every requirement passes.

**Functional requirements (structure/format):**

- **FR1** — The submission file must parse as valid JSON representing a
  top-level object, and all five required top-level fields must be
  present with the correct types. Malformed/unparseable JSON, a
  non-object top-level value, missing fields, or wrong field types all
  produce a clean `[TEST] FAIL: FR1: <reason>` (no traceback, no silent
  pass).
- **FR2** — `suspect_nets` is non-empty, and every entry is an actual
  wire/reg/input/output identifier (or `assign`-statement target) that
  the script parses out of `inputs/masked_and.v`. Fabricated or absent
  names fail this check.
- **FR3** — `algebraic_masking_correct` must be `true`. The script
  attempts to cross-check this independently by compiling and simulating
  `inputs/masked_and.v` with `iverilog`/`vvp` (using a bundled testbench)
  and verifying the invariant `q0 XOR q1 == (a0 XOR a1) AND (b0 XOR b1)`
  across sample vectors; if the toolchain is unavailable, the same
  invariant is checked directly against the rows parsed from
  `inputs/sim_trace.vcd.txt` instead. Either way, the requirement still
  grades whether the *submitted* field matches the true assessment.
- **FR4** — `hardening_proposal.registers_to_add` is non-empty, and each
  named signal is traceable to the module's declared nets (or the
  standard share-domain port names `a0`/`a1`/`b0`/`b1`/`r`/`q0`/`q1`).

**Security requirements (substantive correctness):**

- **SR1** — The report must correctly attribute the leakage to
  glitch/timing effects in unregistered combinational recombination
  logic, not to a flaw in the masking algebra itself. This is judged
  from `algebraic_masking_correct` together with keyword/semantic
  evidence in `vulnerability_summary` (e.g. references to glitches,
  timing, settling, propagation delay, or unregistered combinational
  logic), while summaries that instead claim the masking scheme is
  mathematically wrong are rejected.
- **SR2** — `suspect_nets` must name the internal nets that combine a
  share of one operand with the *opposite* share of the other operand
  (the "cross-term" partial products — `and_cross0`/`and_cross1` in the
  public interface's example naming, though the script identifies the
  true cross-term nets dynamically from the netlist's `assign`
  statements rather than relying on any fixed name).
- **SR3** — The hardening proposal must place new registers so that the
  share-domain values are latched before (or at) the combinational
  merge point where the partial products and mask are combined into the
  outputs — not merely at the final `q0`/`q1` output ports, which would
  leave the internal cross-share combination unregistered within a
  single clock cycle.

## Toolchain notes

The optional `iverilog`/`vvp` cross-check used for FR3 requires both
tools to be discoverable on `PATH`. If they are not available, or if
compilation/simulation fails for any reason, the script gracefully falls
back to validating the same algebraic invariant directly from the rows
in `inputs/sim_trace.vcd.txt`, and no requirement is ever skipped as a
result — every requirement always resolves to either `PASS` or `FAIL`.