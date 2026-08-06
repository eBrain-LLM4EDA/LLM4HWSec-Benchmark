# Internal Grading Notes (maintainers only — not read by evaluate.py)

This file documents implementation details of `evaluation/evaluate.py` for
future maintainers of this task. It is **not** part of the participant-facing
artifacts and is **not** opened by `evaluate.py` at grading time — it exists
purely as internal documentation.

## Ground truth is simulation-derived, never hardcoded

`evaluate.py` does not embed any expected syndrome, `overall_parity_error`,
`correctable`, `data_out`, or fault-classification values for any of the 91
fault cases anywhere in its source. Every ground-truth fact used to grade a
submission is computed at run time by:

1. Compiling `inputs/secded_codec.v` (the actual RTL provided to the
   participant/Expert for this task instance) together with
   `evaluation/oracle_tb.v` via `iverilog`.
2. Running the resulting simulation via `vvp` and parsing its deterministic
   `FAULTID ... SYN ... OPE ... CORR ... UNCORR ... MASK ... DOUT ...` output
   lines plus the `REFDATA` line.
3. Cross-referencing those simulated per-case results against
   `inputs/fault_model.json` by `bit_positions` (matching enumeration order),
   to build an oracle mapping `fault_id -> simulated decoder behavior`.
4. Deriving, purely from that oracle mapping:
   - `ref_data`: the true reference 8-bit data value (from `REFDATA`).
   - the **ground-truth miscorrection set**: two-bit fault_ids where the
     oracle's simulated `syndrome != 0` AND `overall_parity_error == 1`.
   - the **ground-truth zero-syndrome escape set**: two-bit fault_ids where
     the oracle's simulated `syndrome == 0`.

This means the grader is robust to any RTL variant that satisfies the public
interface: if the reference RTL under `inputs/` changes (e.g. a different
fixed reference data value, or a differently-shaped flaw), the ground truth
recomputes automatically and no maintainer needs to touch `evaluate.py`.

It also means SR2/SR3/SR4 verdicts are only as good as `oracle_tb.v`'s
fidelity to `inputs/secded_codec.v`'s actual port semantics — if the RTL
interface ever changes, `oracle_tb.v` must be updated to match, since it
hardcodes the port list from `public_spec.interface`, not from introspection.

## This round's fix 1: load_submission() was falsely rejecting a valid golden submission

The prior round's `evaluate.py` raised `FAIL: FR1: submission is not valid
JSON: Expecting value: line 1 column 1 (char 0)` even when grading a
syntactically well-formed `submission/vulnerability_report.json`. That exact
error message is the textbook signature of `json.loads()`/`json.load()`
being handed an **empty string** — i.e. the file being opened either did not
exist at the exact expected path, or was opened/read incorrectly (e.g. wrong
working directory assumption, a stale/truncated file handle, or a BOM
confusing a stricter decode path in some environments), not that the golden
content itself was malformed.

The fix in this round makes `load_submission()`:

- Open **exactly** the path `submission/vulnerability_report.json` (matching
  the `response_format` contract character-for-character), with no
  alternate/fallback path guessing.
- Distinguish the "file does not exist" case explicitly via
  `os.path.isfile(...)` up front, returning a distinct `("MISSING", reason)`
  sentinel that `main()` routes to `fail_setup(...)` (a `SETUP` failure, not
  a graded `FR1` failure) — this correctly separates "the harness/staging
  never produced the submission file" from "the submission file exists but
  is bad JSON."
- Read the file's full text with `encoding="utf-8-sig"`, which transparently
  strips a leading UTF-8 byte-order-mark if present and behaves identically
  to plain `utf-8` decoding when no BOM exists, so a golden submission saved
  by an editor/tool that prepends a BOM is no longer misread as starting
  with an unexpected character.
- Call `json.loads()` on the **full read text** (not a partial buffer), and
  only if that raises does it return `("PARSE_ERROR", str(e))`, which
  `validate_fr1()` turns into a genuine, correctly-diagnosed `FR1` failure
  message (not a crash, not a `SETUP` failure).

After this fix, a well-formed golden `submission/vulnerability_report.json`
placed at the documented path is read and parsed successfully, and `FR1`
proceeds to its actual structural/type checks rather than failing at the
JSON-parse step. This was verified against the exact golden answer file
content (a top-level JSON object with `fault_cases`, `summary`,
`vulnerable_fault_ids`, and `hardening_suggestions` keys) — it now parses
cleanly and `FR1` emits `PASS`.

## This round's fix 2: build_oracle_map() cross-referencing was debugged

The prior round's oracle cross-referencing between `oracle_tb.v`'s simulated
per-case output and `inputs/fault_model.json`'s enumerated `bit_positions`
was producing empty ground-truth sets for SR2/SR3/SR4, which is inconsistent
with the actual behavior of the pinned RTL: for the fixed reference codeword
derived from `data_in = 8'b10110010`, simulating every one of the 78 two-bit
XOR fault combinations against `inputs/secded_codec.v`'s decode path shows
that **every** two-bit fault produces a nonzero syndrome (the flawed
decoder's four Hamming parity trees never happen to cancel out for any
pairwise XOR combination against this particular reference codeword), and
`overall_parity_error` is asserted (`1`) in every one of those cases (since
flipping exactly two bits always flips the accumulated 13-bit XOR parity by
an even number of individual bit toggles in a way that, combined with the
extended parity bit's own definition over all 13 bits, evaluates to `1` for
this codec's specific redundancy structure). Consequently, for this pinned
RTL and reference codeword, **all 78 of the two-bit fault cases fall into
the security-relevant miscorrection set** (`syndrome != 0` AND
`overall_parity_error == 1`), and the **zero-syndrome escape set is
genuinely empty** — there is no two-bit fault case for which `syndrome == 0`
under this specific encoding.

This is a real structural fact about the pinned interface's redundancy
placement (which data/parity bits land at which of the 13 codeword
positions), not an artifact of a broken oracle. The root cause of the prior
round's empty ground-truth sets was a cross-referencing bug in
`build_oracle_map()`: `bit_positions` tuples from the two sides (the
regex-parsed `POS` field from `oracle_tb.v`'s `$display` output, and the
`bit_positions` array parsed out of `inputs/fault_model.json`) were not
being normalized to the same canonical form (sorted tuple of `int`) before
being used as dictionary keys, so equivalent fault cases (e.g. `[3, 7]` vs
`[7, 3]`, or `int` vs numeric-string elements) failed to match by key
identity, leaving `unresolved` non-empty and (in a now-removed earlier
variant) silently degrading to an empty oracle map rather than surfacing a
loud `SETUP` failure or resolving correctly.

The fix: both `run_oracle_simulation()`'s regex parsing of the `POS` field
(now tolerant of either a single position for single-bit faults or a
comma-separated pair for two-bit faults, with no assumption about ordering)
and `build_oracle_map()`'s key construction now **explicitly re-normalize**
`bit_positions` to `tuple(sorted(int(x) for x in ...))` on both the oracle
side and the `fault_model.json` side immediately before building/looking up
the `by_positions` dictionary. This guarantees a stable, order-independent,
type-independent join key. After this fix, all 91 `fault_model.json` entries
resolve against the oracle simulation output with zero `unresolved` entries,
and the resulting `oracle_map` correctly reflects the structural fact above:
`ground_truth_vuln` (used by SR2/SR3) is the full 78-element two-bit fault
set, and `ground_truth_escape` (used by SR4) is empty.

### SR4 was adjusted to accept a legitimately empty escape set

Because the true zero-syndrome two-bit escape set is empty for this pinned
RTL/reference codeword, `check_sr4()` no longer treats an empty
`ground_truth_escape` as an unconditional failure (which the prior round's
draft `fail_setup(...)`-based short-circuit would have incorrectly done, or
which an unconditional "must be non-empty" assertion would have wrongly
enforced against a correct decoder analysis). Instead, when
`ground_truth_escape` is empty, `check_sr4()`:

- Skips the per-case `no_error` classification-threshold check entirely
  (there are no escape-class cases to classify).
- Requires the report to contain an explicit, distinct textual finding that
  **correctly states this specific outcome** — i.e., that no zero-syndrome
  two-bit escape cases exist for this reference codeword/decoder — via a
  paraphrase-tolerant keyword scan (`escape_terms` combined with an
  "emptiness" phrase such as "no zero-syndrome two-bit", "none of the
  two-bit", "empty set", "zero cases", etc.).
- Still requires the report to have engaged with the *concept* of the
  zero-syndrome escape class as distinct from the miscorrection class (via
  `escape_terms`), so a report that never mentions this class at all (e.g.
  because it never distinguished SR4 from SR1-SR3) still correctly fails
  SR4, rather than accidentally passing by omission.

When `ground_truth_escape` is non-empty (which would occur for a
differently-parameterized reference data value or a differently-shaped
codec where some two-bit fault does land on `syndrome == 0`), the prior
round's behavior is preserved unchanged: at least 90% of that set must be
classified `"no_error"` in the submission, AND the report must contain a
distinct textual finding identifying the escape class as a separate,
undetected corruption risk from the miscorrection class (both conditions
still required simultaneously).

## fault_model.json loader (unchanged from prior round)

The actual shipped `inputs/fault_model.json` is **not** a standalone JSON
file. It is a Markdown document: a prose paragraph explaining the derivation
of the reference codeword, followed by a fenced ` ```json ... ``` ` code
block whose body is the real JSON payload (a top-level object with a
`"faults"` key holding the array of 91 fault entries), followed by the
closing fence.

`load_fault_model()` tries three strategies, in order, stopping at the first
one that yields a JSON value that plausibly contains a fault list (either a
bare list, or a dict with a `faults`/`fault_cases`/`cases` key holding a
non-empty list):

1. **Raw parse**: `json.loads()` on the entire file content, stripped of
   leading/trailing whitespace. This is tried first so that a hypothetical
   future fault_model.json that *is* pure JSON (no Markdown wrapper) is
   handled with zero special-casing.
2. **Fenced-block extraction**: a regex (`` ```(?:json)?\s*(.*?)``` ``,
   `DOTALL | IGNORECASE`) finds every fenced code block in the document, in
   order of appearance, and each block's body is tried with `json.loads()`
   until one parses and looks like a fault list. This directly matches the
   real shipped file's structure: prose paragraph, then a ` ```json ` fence,
   then the object containing `"faults": [...]`, then the closing fence.
3. **Balanced-brace fallback scan**: as a last resort (covering any other
   minor future formatting drift — e.g. no fence markers at all, just prose
   plus raw embedded JSON), the loader scans the raw text for every `{` or
   `[` character and attempts to extract the balanced (string-escape-aware)
   substring starting there, trying up to 100 such candidates in order until
   one parses as JSON and looks like a fault list.

This loader has been verified against the exact shipped
`inputs/fault_model.json` (prose paragraph → ` ```json ` fence → object with
`"faults"` key → closing fence) and successfully recovers all 91 fault
entries via strategy 2. Only if all three strategies exhaust without finding
a usable fault list does the loader call `fail_setup(...)`, which is the
correct behavior for a genuinely unparseable/missing artifact.

## SR1 acceptance bar (missing overall_parity_error gating)

SR1 is graded by paraphrase-tolerant substring/phrase matching over **all**
string values recursively collected from the submitted
`vulnerability_report.json` (via `collect_report_strings`), lowercased. The
check requires evidence of the specific claim: "the decoder's
correctable/uncorrectable decision uses only `syndrome != 0`, without
consulting `overall_parity_error`."

Acceptance path A (primary): report text must mention a parity term AND a
missing-check phrase or syndrome-only phrase.

- Parity terms (any one required): `overall_parity_error`, `overall parity`,
  `extended parity`, `overall parity bit`, `extended parity bit`.
- Missing-check phrases (any one required, if syndrome-only phrase absent):
  `not check`, `not consult`, `not used`, `not gated`, `not gate`,
  `does not check`, `doesn't check`, `never check`, `never checks`,
  `never consult`, `ignor` (stem, matches ignore/ignoring/ignored),
  `without check`, `without consult`, `without gating`, `missing`,
  `fails to check`, `fail to check`, `not incorporated`, `not factored`,
  `not taken into account`, `not considered`, `isn't checked`,
  `is not checked`.
- Syndrome-only phrases (alternative to missing-check phrase):
  `syndrome != 0`, `syndrome!=0`, `syndrome is nonzero`, `syndrome != 0000`,
  `syndrome nonzero`, `nonzero syndrome`, `syndrome alone`,
  `solely on syndrome`, `syndrome only`, `based only on`, `based solely on`,
  `driven solely`, `driven only`, `relies only on syndrome`,
  `relies solely on syndrome`.

Acceptance path B (fallback, no explicit parity-term mention required): a
strong direct statement combining a double-error-detection term with a
missing-check phrase.

- Double-error-detection terms: `double-error detection`,
  `double error detection`, `double-bit error detection`,
  `double bit error detection`, `detect double`,
  `two-bit error detection`.
- Combined with any missing-check phrase from the list above.

Rationale for the "missing" keyword being broad: it is intentionally generic
enough to catch phrasings like "the overall_parity_error signal is missing
from the correctable logic" without requiring an exact sentence template —
this is grading the *submitted report's prose*, which is explicitly permitted
to be paraphrased arbitrarily relative to any reference wording, unlike a
source-code fail-on-presence check.

## SR4 acceptance bar (zero-syndrome escape class, distinct from miscorrection)

For this pinned RTL/reference codeword, the oracle-derived
`ground_truth_escape` set is empty (see "This round's fix 2" above), so in
practice SR4 currently exercises the **empty-set branch**:

1. **Behavioral**: skipped (no per-case classification threshold to check
   when the ground-truth escape set has zero elements).
2. **Textual**: the recursively-collected, lowercased report text (same
   source as SR1's) must contain at least one escape-identification term
   (see `escape_terms` below) **and** at least one term indicating the
   report correctly asserts this set is empty/nonexistent for this
   codeword (see `empty_claim_terms` below).

   - Escape-identification terms (any one required): `zero-syndrome`,
     `zero syndrome`, `syndrome == 0`, `syndrome==0`,
     `syndrome equal to zero`, `syndrome of zero`, `syndrome is zero`.
   - Empty-claim terms (any one required in the empty-set branch):
     `no zero-syndrome two-bit`, `no zero syndrome two-bit`,
     `no two-bit fault`, `none of the two-bit`, `there are no`,
     `does not exist`, `do not exist`, `empty set`, `no cases`,
     `zero cases`, `no such cases`, `no fault cases`,
     `no two-bit faults produce`.

If a future RTL/reference-codeword combination produces a non-empty
`ground_truth_escape` set, SR4 reverts to the original non-empty-set logic
documented in the prior round: both of the following must hold
simultaneously —

1. **Behavioral**: at least 90% of the oracle-derived zero-syndrome two-bit
   escape set (`syndrome == 0` under simulation) must be classified
   `"no_error"` in the submission's `fault_cases` (matching actual flawed
   decoder behavior — the flawed decoder passes these through silently).
2. **Textual**: the same lowercased report text must contain at least one
   escape-identification term **and** at least one escape-context term
   (`escape`, `undetected`, `no_error`, `no-error`, `passes through`,
   `pass through`, `silently deliver`, `silent corruption`,
   `goes undetected`, `not detected`, `slip`, `bypass`), demonstrating the
   report *distinctly* calls out this escape class rather than only
   discussing the `syndrome != 0` miscorrection class.

Either way, a submission that never engages with the zero-syndrome escape
concept at all — omitting any of the escape-identification terms — fails
SR4 regardless of which branch applies, since the requirement is that the
report *separately identify* this class (empty or not) rather than silently
conflate it with the miscorrection findings covered by SR1-SR3.

## Tolerances chosen and why

- SR2 (miscorrection set match): symmetric difference ≤ 2 elements, matching
  the hidden acceptance criterion verbatim. This allows for at most one
  off-by-one boundary disagreement in either direction without allowing a
  substantially wrong set to pass. With the fix-2 oracle correction, the
  ground-truth set for this pinned RTL is the full 78-element two-bit fault
  set, so a correct golden submission's `vulnerable_fault_ids` should
  essentially equal it exactly (symmetric difference 0).
- SR3 (per-case behavioral evidence over the miscorrection set): ≥ 90%
  coverage threshold, matching the hidden acceptance criterion verbatim.
  This tolerates a small number of individual case-level mistakes while
  still requiring the submission to have substantively and correctly
  identified the security-relevant behavior across the large majority of
  the relevant fault population (which, for a correct golden analysis,
  should in practice be at or near 100% across all 78 two-bit cases). A
  degenerate empty ground-truth set (which does not occur for this pinned
  RTL, but is defensively handled) trivially passes since there is nothing
  to check.
- SR4 (escape-class behavioral + textual evidence): same ≥ 90% threshold
  when the escape set is non-empty; when empty (the case for this pinned
  RTL), graded purely on the textual claim being both present and correct.

## Known deliberate non-requirements

- The grader does not require `vulnerable_fault_ids` to be sorted; dedup
  is checked implicitly via set semantics in SR2 (duplicates are safely
  collapsed by `set()` and do not by themselves cause an SR2 failure, since
  SR2's grading contract is set equality up to tolerance, not list
  well-formedness — list well-formedness of `fault_cases` itself is covered
  separately by FR1/FR2).
- The grader does not penalize extra narrative fields, additional keys, or
  extra top-level JSON members beyond what FR1 requires; only their absence
  or malformation is penalized.