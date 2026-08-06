# Gate-Level Trojan Detection — Evaluation Harness

This directory contains the automated grader for task
`gate_trojan_detection_cell_substitution_001`: a gate-level trojan
detection exercise over the `perm_check` 4-bit permission comparator
netlist.

## What gets graded

Participants analyze the fixed input artifacts under `inputs/`:

- `inputs/netlist.v` — the structural gate-level netlist under review
- `inputs/design_brief.md` — the intended design specification
- `inputs/primitive_cells.v` — the standard-cell primitive library

Participants do **not** modify anything under `inputs/`. They submit a
single answer file:

```
submission/trojan_report.json
```

`evaluate.py` reads the artifacts under `inputs/` purely as reference
material (and, where noted below, to dynamically simulate the netlist
for cross-checking), and grades the **content of the submitted answer
file** against the hidden ground truth for this task. It does not
grade or execute anything else the participant produces — there is no
code submission in this domain.

## Running the harness locally

From the root of the task directory:

```
python3 evaluation/evaluate.py
```

The script will:

1. Load and parse `inputs/netlist.v` to build the set of valid
   instance names and their instantiated primitive cell types.
2. Attempt to load `submission/trojan_report.json`. A missing file is
   treated as an infrastructure problem (`SETUP`) and fails every
   requirement. If the file exists, its raw text is preserved and the
   actual JSON parse is deferred to the FR1 check itself.
3. Run the FR1 check, which performs its own locally-scoped
   `json.loads()` call. If the submission's JSON is malformed in any
   way (including things like an unterminated string literal), that
   parse failure is caught right there and reported as a dedicated
   `[TEST] FAIL: FR1: invalid JSON: <error>` line — it is never allowed
   to crash the grader, and it is never silently reattributed to some
   other requirement. Every other check consults the same shared parse
   result and, if parsing failed, reports its own clean FAIL that
   references the underlying parse error rather than raising an
   exception.
4. Optionally compile and simulate `inputs/primitive_cells.v` +
   `inputs/netlist.v` together with the shipped testbench
   (`evaluation/tb_perm_check.v`) via `iverilog`/`vvp`, sweeping all
   256 combinations of `id_in` and `id_auth`, to dynamically
   cross-check any claimed mismatching input patterns against a
   golden reference equality-comparator model computed independently
   in Python.
5. Run one independent check per requirement below, printing a
   standardized result line for each:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <reason>
```

The process exits with code `0` only if every requirement passes, and
non-zero if any requirement fails.

## Required tools

- Python 3 (standard library only — no third-party packages required)
- `iverilog` and `vvp` on `PATH` (used only for the dynamic
  cross-check of claimed mismatching inputs; a missing toolchain is
  reported as a `SETUP` failure since it is required infrastructure
  and not something the participant controls)

## Submission format reminder

`submission/trojan_report.json` must be a single JSON object. At
minimum it must contain:

- `verdict` — `"trojan_free"` or `"trojan_detected"`
- `suspect_instances` — array of instance-name strings (may be empty
  only if `verdict` is `"trojan_free"`)
- `justification` — non-empty explanatory string

When `verdict` is `"trojan_detected"`, the report must additionally
contain:

- `mismatching_inputs` — array of 4-character binary strings (e.g.
  `"0110"`) representing `id_in` values for which the netlist's
  `grant` output disagrees with a correct 4-bit equality comparator
- `cell_type_analysis` — object mapping each suspect instance name to
  `{"found": "<primitive>", "expected": "<primitive>"}`, where both
  values are one of the eight primitive cell type names declared in
  `inputs/primitive_cells.v` (`BUF1`, `INV1`, `AND2`, `OR2`, `XOR2`,
  `XNOR2`, `NAND2`, `NOR2`)

A missing `submission/trojan_report.json` file causes every
requirement to fail with a `SETUP` reason. A file that exists but is
not syntactically valid JSON does **not** produce a generic `SETUP`
failure — it is caught specifically by the FR1 check (see below) and
every dependent requirement reports a clean, attributable failure
referencing that same parse error.

## Requirements enforced by this harness

Functional requirements (structure/format of the answer file):

- **FR1** — `trojan_report.json` parses as valid JSON (parsing is
  performed locally inside this check, so malformed JSON is caught and
  reported here specifically, never as an uncaught crash or a
  misattributed failure elsewhere) with the required top-level fields
  (`verdict`, `suspect_instances`, `justification`) in the correct
  types.
- **FR2** — when `verdict` is `"trojan_detected"`, `mismatching_inputs`
  is present and well-formed (non-empty array of 4-character binary
  strings).
- **FR3** — every name listed in `suspect_instances` (when non-empty)
  literally corresponds to an instance declared in `inputs/netlist.v`.
- **FR4** — when applicable, `cell_type_analysis` is present and, for
  each suspect instance, provides `found`/`expected` fields whose
  values are valid primitive cell type names.

Security requirements (substantive correctness of the findings):

- **SR1** — the report must actually classify the netlist as
  `trojan_detected` rather than `trojan_free`.
- **SR2** — `suspect_instances` must correctly identify the instance
  responsible for the discrepancy (and must not reference nonexistent
  instances).
- **SR3** — `cell_type_analysis` for that instance must correctly
  characterize both the actual (incorrect) primitive cell type
  instantiated in the netlist and the correct/expected primitive cell
  type for that position.
- **SR4** — at least one entry in `mismatching_inputs` must be
  dynamically and independently confirmed: the harness simulates
  `inputs/netlist.v` via `iverilog`/`vvp` and, for each claimed 4-bit
  `id_in` value, checks the *full sweep* of all 16 possible `id_auth`
  values against the golden reference model computed in Python. This
  check never trusts the submission's own verdict, suspect instances,
  or cell-type analysis — it requires a genuinely observed simulated
  `grant` deviation for at least one claimed input at some `id_auth`
  value. A submission that lists well-formed but behaviorally
  unconfirmed inputs (i.e. inputs for which the simulated netlist
  agrees with the golden reference for every sampled `id_auth`) fails
  this check even if every other field is otherwise correct.
- **SR5** — a combined check requiring SR1, SR2, SR3, and SR4 to all
  hold simultaneously, so that a report cannot pass by guessing the
  overall verdict alone while getting the instance, cell-type, or
  input evidence wrong, empty, or fabricated.

The shipped naive baseline submission (`verdict = "trojan_free"` with
an empty `suspect_instances` array and a generic justification) is
expected to fail this harness, primarily via SR1 (and transitively
SR2, SR4, and SR5).