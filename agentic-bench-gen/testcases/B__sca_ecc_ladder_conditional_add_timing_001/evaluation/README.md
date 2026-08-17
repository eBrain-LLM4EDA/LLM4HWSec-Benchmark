# Evaluation — Conditional Point-Addition Timing Leak

## What is graded

This task is graded in **report_grading** mode. Participants do **not**
modify anything under `inputs/`. The only artifact that is graded is:

```
submission/vulnerability_report.json
```

`evaluate.py` reads the reference RTL under `inputs/` (`scalar_mult_ctrl.v`,
`field_datapath.v`, `fault_model.md`, `design_brief.md`) purely to
cross-check claims made in the submitted report. It does **not** grade the
RTL itself, and it does not accept code changes to `inputs/`.

## How the report file is read

`submission/vulnerability_report.json` is expected to contain a JSON
object, but the grader is tolerant of minor packaging differences: it
first attempts a strict `json.loads()` on the whole file, and if that
fails it will look for a fenced code block (` ```json ... ``` ` or
` ``` ... ``` `) or scan the raw text for the first well-formed top-level
`{ ... }` object and parse that. Only if none of these strategies produce
a valid JSON object does the report fail to parse. This means a report
consisting of pure JSON, or JSON preceded/followed by explanatory prose,
or JSON inside a markdown fence, are all accepted equally — what matters
is the *content* of the object, not its surrounding formatting.

## How grading works

1. **Setup checks.** All four `inputs/` files and
   `submission/vulnerability_report.json` must exist. Missing files produce
   `[TEST] FAIL: SETUP: <path> not found` and an immediate non-zero exit.

2. **Independent simulation cross-check.** `evaluate.py` compiles
   `evaluation/tb_cycle_count.v` together with `inputs/scalar_mult_ctrl.v`
   and `inputs/field_datapath.v` using `iverilog`, then runs the result with
   `vvp`. The testbench drives a fixed, deterministic list of 16-bit
   scalars (from `evaluation/private/scalar_input.txt`, spanning low, mid,
   and high Hamming weight) through the controller's `start`/`done`
   handshake and prints one `CYCLE_RESULT <scalar> <cycle_count>` line and
   one `RESULT_XY <scalar> <x_hex> <y_hex>` line per scalar. This produces
   an independent reference table of `(scalar, cycle_count)` pairs that is
   used to validate the submission's own reported numbers — it is not
   itself graded, and its presence is completely independent of how the
   submitted report is worded or structured.

3. **Functional Requirements (FR1–FR4)** — structural/format checks against
   the parsed content of `vulnerability_report.json`:
   - **FR1**: required string fields present and non-empty; `cycle_counts_by_scalar`
     is an array of `{scalar:int, cycle_count:int}` objects. This check also
     fails (with a parse-error reason) if the file cannot be resolved to a
     JSON object at all by any of the extraction strategies above.
   - **FR2**: at least 4 distinct scalars are reported, spanning low
     (≤2 set bits), high (≥14 set bits), and ≥2 intermediate Hamming
     weights; any submitted scalar that also appears in the fixed
     reference scalar set must have a `cycle_count` within a small
     tolerance of the independently simulated value.
   - **FR3**: `preserves_correct_output` is boolean; `remediation_rtl_sketch`
     is a substantive (non-placeholder) description of an RTL-level fix.
   - **FR4**: `cycle_count_range.min`/`max` match the actual min/max of the
     submitted `cycle_counts_by_scalar` values.

4. **Security Requirements (SR1–SR4)** — substantive correctness checks:
   - **SR1**: the report must identify the ADD state / `scalar_bit == 1`
     conditional path as the leak source, not merely the DOUBLE state or a
     generic FSM reference.
   - **SR2**: Hamming weight of each submitted scalar must correlate
     (Pearson ≥ 0.9) with the submitted `cycle_count`, and the independent
     simulation must itself show real cycle-count variation across
     Hamming weights (a submission — or the reference sim — showing
     constant cycle counts fails this check).
   - **SR3**: the remediation must describe always executing ADD every bit
     (writing to a dummy/discarded result when the bit is 0) with a final
     mux/select, not merely random delay/jitter/noise/blinding.
   - **SR4**: `preserves_correct_output` must be `true`, and the
     remediation text must explain the mux/select mechanism that commits
     the real vs. dummy ADD result based on the scalar bit.

All checks are **behavioral or substantive**, never based on incidental
prose style, file packaging, field ordering, or naming conventions beyond
what the public interface pins. A correct report that uses entirely
different wording, field ordering (within the fixed JSON schema), or
explanation style — or that wraps its JSON in narrative text or a markdown
fence — than any reference example will still pass, provided it
substantively satisfies each requirement above.

## Pass/Fail semantics

- Each requirement id (`FR1`–`FR4`, `SR1`–`SR4`) emits exactly one line:
  `[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>`.
- `evaluate.py` exits `0` only if **every** requirement passes.
- The shipped naive baseline (`vulnerable_signal`/`vulnerable_states`
  empty, `cycle_counts_by_scalar` empty, `preserves_correct_output: false`)
  is expected to **fail** at minimum FR1, FR2, SR1, and SR2, and therefore
  exits non-zero.
- A correct, substantively accurate report — regardless of exact wording or
  file packaging — is expected to pass all requirements and exit `0`.

## Determinism

- The scalar list used for simulation cross-checks is fixed in
  `evaluation/private/scalar_input.txt` and is identical across runs.
- All subprocess invocations (`iverilog`, `vvp`) use explicit timeouts and
  write build artifacts to a temporary directory, never into `inputs/`.
- No wall-clock-dependent or random behavior is used in grading.
- All reported `cycle_count` figures in a correct submission must be
  values actually observed by running the provided RTL through simulation
  (e.g. with `iverilog`/`vvp`) for the corresponding scalar, not values
  derived analytically from a mental model of the state machine — small
  discrepancies between an assumed cycle-accounting formula and the
  actual synthesized/simulated behavior of `scalar_mult_ctrl.v` combined
  with `field_datapath.v` are exactly what the independent simulation
  cross-check in FR2 is designed to catch.