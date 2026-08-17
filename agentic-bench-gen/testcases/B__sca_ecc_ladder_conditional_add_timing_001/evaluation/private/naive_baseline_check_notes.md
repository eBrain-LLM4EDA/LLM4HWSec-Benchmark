# Internal Notes — Naive Baseline Submission Behavior

**Status: internal maintainer documentation only. Not read by evaluate.py.**

This note records the expected grading outcome for the naive/empty baseline
`submission/vulnerability_report.json` (all string fields empty, no
`cycle_counts_by_scalar` entries, `preserves_correct_output: false`), for
future maintainers verifying that `evaluate.py` continues to reject it
correctly after any changes — including the JSON-extraction robustness fix
(strict parse -> fenced-block extraction -> brace-matching scan) and the
golden-fixture cycle-count regeneration performed in this round (which only
touches the private golden report used for differential validation, not
`evaluate.py` itself or this baseline).

## Note on the JSON-extraction fix

The baseline submission file is expected to already be a well-formed bare
JSON object (just with empty/placeholder field values), so the strict
`json.loads()` path in `extract_json_object()` should succeed on it
directly, without needing to fall back to fenced-block or brace-matching
extraction. The extraction fix changes *how* a JSON object is located in
the file content; it does not change *what* is checked once the object is
parsed. Therefore all of the failure reasons below are unaffected by the
fix — the baseline must still fail every one of these checks for the same
substantive reasons as before.

## Note on the golden-fixture cycle-count regeneration

This round's repair only regenerates the *private golden* submission's
`cycle_counts_by_scalar` values (and derived `cycle_count_range`) by
actually running `iverilog`/`vvp` against `inputs/scalar_mult_ctrl.v` and
`inputs/field_datapath.v` via `evaluation/tb_cycle_count.v`, rather than
deriving them analytically. `evaluate.py`'s cross-check logic (FR2/SR2)
was already correct and is unchanged. This baseline fixture is untouched
and its expected failures below are unaffected: it reports zero scalars,
so there is nothing for the simulation cross-check to compare against in
the first place.

## Expected failures

- **FR1** — FAILS. The required string fields
  (`vulnerable_signal`, `vulnerable_states`, `timing_dependency_description`,
  `remediation_description`) are empty strings, which fails the
  non-empty-string check. `cycle_counts_by_scalar` is an empty list, which
  fails the "missing, empty, or not a list" check. Since FR1 already fails
  on the empty required fields, the empty array only reinforces the same
  verdict.

- **FR2** — FAILS. With `cycle_counts_by_scalar` empty, there are zero
  distinct scalars reported, which is fewer than the required 4. There is
  also no scalar with Hamming weight ≤2, none with ≥14, and no intermediate
  entries, so all three coverage checks fail independently of the count
  check. Additionally, with no submitted scalars there is no overlap with
  the fixed reference scalar set, so the simulation cross-check also cannot
  be performed and is treated as a failure.

- **FR3** — FAILS. `preserves_correct_output` is `false` (a boolean, so the
  type check itself would pass), but `remediation_rtl_sketch` is an empty
  string, which fails both the minimum-length check and the RTL-keyword
  substantiveness check.

- **FR4** — FAILS. `cycle_count_range` is absent or, if present as an empty
  placeholder, contains no valid integer `min`/`max` matching the (nonexistent)
  entries in `cycle_counts_by_scalar`; with zero parsed entries there is
  nothing to compare against, so the check cannot succeed.

- **SR1** — FAILS. `vulnerable_signal`, `vulnerable_states`, and
  `timing_dependency_description` are all empty strings, so none of the
  ADD-state / `scalar_bit` conditional regex patterns match anywhere in the
  combined text. The "mentions_add_concept" check is false, so SR1 fails
  regardless of the generic-only fallback branch.

- **SR2** — FAILS. There are fewer than 4 `cycle_counts_by_scalar` entries
  (in fact zero), so the correlation computation cannot be performed and is
  treated as an automatic failure before even considering the independent
  reference-simulation cross-check.

- **SR3** — FAILS. `remediation_description` and `remediation_rtl_sketch`
  are both empty, so neither the "always execute ADD" patterns nor the
  "mux/select" patterns are found in the combined remediation text.

- **SR4** — FAILS. `preserves_correct_output` is `false` (not `true`), which
  alone fails this requirement; additionally, the empty remediation text
  contains none of the commit/select-mechanism explanation patterns.

## Summary

The naive baseline is expected to fail **all eight** requirement checks
(FR1–FR4, SR1–SR4), not merely the minimum subset (FR1/FR2/SR1/SR2) called
out in the hidden acceptance criteria. This is consistent with the
acceptance criterion "must fail at least FR1/FR2/SR1/SR2" — the baseline
fails strictly more than the minimum required set, which is expected and
acceptable. `evaluate.py` must exit non-zero on this submission.

If a future change to `evaluate.py` causes any of the above eight checks to
unexpectedly PASS on this baseline, that is a regression and must be
investigated before merging.

## Regression check after the JSON-extraction fix

When re-validating after the extraction-robustness change, confirm:

1. The baseline's raw file content still parses successfully via the
   strict `json.loads()` branch of `extract_json_object()` (i.e. `report`
   is not `None` and `parse_error` is not set), so FR1's failure reason is
   the *field-level* reason above ("field '...' missing/empty/non-string";
   "'cycle_counts_by_scalar' missing, empty, or not a list") — **not** a
   parse-error reason like "could not parse vulnerability_report.json as a
   JSON object". If the baseline ever produces a parse-error-based FR1
   failure instead of a field-level one, that indicates the baseline file
   itself has become malformed (unexpected) rather than confirming the
   extraction logic; investigate the baseline fixture in that case.
2. All eight checks still emit `[TEST] FAIL` with the same substantive
   reasons enumerated above, and `evaluate.py` still exits non-zero overall.

## Regression check after the golden-fixture cycle-count regeneration

This baseline is independent of the private golden fixture: it does not
share any `cycle_counts_by_scalar` values with the golden report, and
`evaluate.py`'s FR2/SR2 cross-check logic (tolerance-based comparison
against a live `iverilog`/`vvp` simulation of `inputs/scalar_mult_ctrl.v` +
`inputs/field_datapath.v`) is unchanged this round. Confirm that:

1. The independent reference simulation itself still runs successfully
   against the (unchanged) `inputs/` RTL and produces non-constant
   `CYCLE_RESULT` values across the scalars in
   `evaluation/private/scalar_input.txt` (this is a precondition for SR2's
   "reference simulation shows real variation" check to even be
   evaluable, independent of whatever the baseline or golden report
   claims).
2. The baseline's FR2/SR2 failures above are driven purely by having zero
   submitted `cycle_counts_by_scalar` entries, not by any mismatch against
   specific reference numbers — so these failure reasons are unaffected by
   whatever numeric values the golden fixture now reports.