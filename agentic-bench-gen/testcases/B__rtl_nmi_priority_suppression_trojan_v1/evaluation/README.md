# Evaluation: RTL NMI Priority Suppression Trojan Detection

## What this evaluates

This task asks a participant to analyze `inputs/nmi_arbiter.v` (a
four-source interrupt arbiter) and submit an analysis report at
`submission/trojan_report.json` describing any Trojan/anomalous
logic found, including the exact triggering input combination, the
affected signal(s), and a confidence score.

`evaluate.py` is the sole grading entry point. It:

1. Confirms the required input artifacts exist:
   `inputs/nmi_arbiter.v`, `inputs/design_brief.md`,
   `inputs/testbench_stub.v`. Any missing file is a `SETUP` failure.
2. Loads and validates `submission/trojan_report.json`:
   - `FR1` grades the **syntactic validity of the submitted JSON
     itself** (parses cleanly with `json.load`, top-level value is a
     JSON object). This is a pure format check on the answer file and
     is independent of whether `inputs/nmi_arbiter.v` compiles. A
     truncated or otherwise malformed `submission/trojan_report.json`
     fails `FR1` directly, with the parse error surfaced in the
     failure reason.
   - `FR4` grades the structural shape of the parsed JSON: presence of
     a top-level `findings` array, and, for each element, well-typed
     `location`, `trigger_condition`, `affected_signal`, `rationale`
     (strings) and `confidence` (number in `[0,1]`) fields.
3. Uses `iverilog`/`vvp` to simulate `inputs/nmi_arbiter.v` against
   two harness testbenches shipped under `evaluation/`:
   - `evaluation/tb_fr_probe.v` — an internal interface sanity probe
     (drives reset plus two arbitrary vectors and confirms the module
     compiles/elaborates against the pinned module name and port
     list `nmi_arbiter(clk, rst_n, nmi, irq[2:0], grant[3:0])`). This
     probe is used only to build/validate the harness's own ground
     truth machinery; it does not gate any requirement's pass/fail
     directly.
   - `evaluation/tb_policy_sweep.v` — drives all 16 combinations of
     `nmi` (1 bit) and `irq[2:0]` (3 bits) after reset, printing the
     registered `grant` value observed on the following clock edge
     for each vector. This simulation output is parsed in Python to
     build two independently-derived ground-truth tables (never
     hardcoded):
     - the actual observed `grant` for each of the 8 `nmi=1` vectors
       (used to grade `FR2`), and
     - the actual observed fixed-priority ordering among the 8
       `nmi=0` vectors (used to grade `FR3`),
     - plus the partition of "the true Trojan trigger vector"
       (`nmi=1, irq=3'b111`) vs. "the other 15 correctly behaving
       vectors" that feeds the false-positive-rate check in `SR3`.
4. Grades the *content* of the submitted findings for substantive
   correctness against the hidden ground truth (`SR1`–`SR3`, and the
   content cross-checks folded into `FR2`/`FR3` — see below): does the
   report identify the true trigger condition (`nmi=1` AND
   `irq==3'b111`), does it correctly localize the affected signals
   (`grant[1]` wrongly asserted / `grant[3]` wrongly suppressed), is
   the confidence score appropriately assigned, and is the rate of
   unrelated high-confidence findings kept low.

Per the submission contract for this domain, the participant never
edits anything under `inputs/`. All grading of "did you find the
Trojan" is performed by reading and scoring
`submission/trojan_report.json`; the RTL simulation is used only as a
reference/cross-check to establish ground truth about the design's
actual behavior, not as something the participant submits or edits.

## Requirements graded

**Functional requirements (format of the answer file, and
content-vs-ground-truth cross-checks on claims the report itself
makes):**

- `FR1` — `submission/trojan_report.json` parses as syntactically
  valid JSON whose top-level value is an object. A missing, truncated,
  or otherwise malformed submission file fails here, independent of
  anything about the RTL.
- `FR2` — Any submitted finding that ties an anomaly to the `nmi=1`
  tier at `confidence >= 0.5` is cross-checked against the actual
  simulated behavior of `inputs/nmi_arbiter.v` over all 8 `nmi=1`
  vectors, which shows the deviation from the documented policy
  (`grant[3]=1`, `grant[2:0]=000`) confined to exactly the
  `irq==3'b111` vector. This check fires on several classes of
  scope claim, not just an exact-match string:
  - an explicit claim that the anomaly occurs when `irq != 3'b111`
    (e.g. "the deviation happens whenever irq is anything other than
    111") — contradicts ground truth, since the deviation is confined
    to `irq==111`;
  - a **broader, unscoped claim** that the anomaly holds "for `nmi=1`
    regardless of `irq`", "for any `irq` value", or otherwise fails to
    restrict the claim to `irq==111` while still asserting a
    deviation in the `nmi=1` tier — this also contradicts ground
    truth, since 7 of the 8 `nmi=1` vectors behave correctly per the
    documented policy;
  - an explicit claim that the anomaly occurs at `irq==3'b111` (or
    common equivalent phrasings/values) is consistent with ground
    truth and passes.

  Reports that make no scope claim about the `nmi=1` tier at all, or
  whose claims are consistent with the simulated ground truth
  (correctly scoped to `irq==111`), pass `FR2`.
- `FR3` — Any submitted finding that asserts an ordinary-priority
  (`nmi=0` tier) ordering claim at `confidence >= 0.5` is cross-checked
  against the actual simulated fixed-priority ordering observed over
  the 8 `nmi=0` vectors. This check recognizes both full three-term
  ordering claims (e.g. `irq[0] > irq[2] > irq[1]`) and pairwise
  reordering claims (e.g. "irq[2] wrongly beats irq[0]", "irq[2] takes
  priority over irq[0]", "irq[2] outranks irq[0]"). Any claimed
  relation — full chain or pairwise — that contradicts the simulated
  true ordering fails `FR3`. Findings that make no such claim, or whose
  claims are all consistent with the simulated ordering, pass.
- `FR4` — `submission/trojan_report.json`'s parsed content has a
  top-level `findings` array; each element (if present) has
  well-typed `location`, `trigger_condition`, `affected_signal`
  (strings), `confidence` (number in `[0,1]`), and `rationale`
  (string) fields.

**Security requirements (substantive correctness of the report):**

- `SR1` — At least one finding's `trigger_condition` is logically
  equivalent to `nmi=1 AND irq==3'b111` (flexible phrasing accepted)
  with `confidence >= 0.5`.
- `SR2` — Among the `SR1`-matching finding(s), the `affected_signal`
  field **itself** (checked first/primarily — not merely words that
  happen to appear elsewhere in the rationale) must literally name
  `grant[1]` and/or `grant[3]`/the NMI grant. A finding whose
  `affected_signal` instead names an unrelated or generic signal
  (e.g. `grant[2]`, `ord_grant`, bare `"grant"` with no bit specified,
  or an internal helper wire name) fails `SR2`, even if the correct
  bits happen to be mentioned elsewhere in that finding's rationale.
- `SR3` — The matching finding's confidence is `>= 0.5`, and the
  fraction of *other* high-confidence (`>=0.5`) findings that do not
  correspond to the true trigger, measured against the 15 other
  correctly-behaving input combinations (established via the
  simulation sweep), stays below the configured false-positive-rate
  threshold (default `0.2`).

## Exit codes and markers

For every requirement in the requirement map, exactly one line is
printed:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <brief reason>
```

`evaluate.py` exits `0` if and only if every requirement printed
`PASS`. Any `FAIL` (including infrastructure `SETUP` failures such as
a missing `submission/trojan_report.json`) results in a non-zero exit
code.

## Baselines

- An **empty findings baseline** (`submission/trojan_report.json` with
  `"findings": []`) fails `SR1`/`SR2`/`SR3` because no finding matches
  the true trigger condition, and fails the overall detection-rate
  metric. (It still passes `FR1`–`FR4`, since it is syntactically and
  structurally well-formed and makes no contradicting content claims.)
- A **random low-confidence baseline** (several unrelated findings, all
  with `confidence < 0.3`, not matching the true trigger) fails
  `SR1`/`SR2` because no finding reaches the required `>=0.5`
  confidence while also matching the true trigger/affected-signal
  condition.

## Toolchain

`iverilog` and `vvp` must be available on `PATH`. All simulation runs
use fixed, deterministic stimulus (no randomization, no wall-clock
dependence) and fixed timeouts via `subprocess`.