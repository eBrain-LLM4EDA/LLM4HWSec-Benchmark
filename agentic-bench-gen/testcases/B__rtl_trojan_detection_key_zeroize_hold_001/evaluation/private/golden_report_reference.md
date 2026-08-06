# Private Grading Notes: `rtl_trojan_detection_key_zeroize_hold_001`

**Audience:** benchmark maintainers only. Not read by `evaluate.py` at
runtime (the grader locates everything dynamically from
`inputs/key_loader_ctrl.v`), and not shipped as participant-facing
documentation. This file exists purely to document, for humans
maintaining this task, what the hidden ground truth is and how the
FR4/SR1–SR4 checks in `evaluation/evaluate.py` relate to it, including
the per-candidate scoping fix applied to FR4 and SR2.

## Ground truth construct

In the shipped baseline RTL (`inputs/key_loader_ctrl.v`), the offending
logic is:

```verilog
wire zeroize_mask;
assign zeroize_mask = zeroize & ~bus_busy;

always @(*) begin : zeroize_block
    if (zeroize_mask)
        key_q_next = 32'b0;
    else if (bus_wr)
        key_q_next = bus_data;
    else
        key_q_next = key_q_r;
end
```

- `zeroize_mask` gates the emergency-erase request with `~bus_busy`, so
  the erase only actually takes effect when the bus is idle.
- When `zeroize=1` and `bus_busy=1` simultaneously, `zeroize_mask` is `0`,
  so the `if` branch is skipped; if `bus_wr` also happens to be low that
  cycle, `key_q_next` falls through to `key_q_r` — i.e. `key_q` holds
  (self-holds) its previous value instead of clearing.
- This directly contradicts `design_brief.md`'s documented priority
  order (`zeroize` must unconditionally beat bus activity), and the
  correct expected value of `key_q` under the trigger is `32'b0`.

An independently-produced golden submission is expected to phrase this
using different vocabulary/structure entirely (different label names,
different candidate ordering, prose instead of a priority list, etc.).
The grader must never depend on that phrasing — only on the *semantic*
content described below.

## Why FR4 and SR2 were rewritten (repair history)

The prior version of `evaluate.py` computed the FR4 "expected value"
check and the SR2 "root cause" check by searching **the entire report
body** (all candidates' text concatenated with the whole `summary`
string) for keyword hits. This was too permissive:

- An **FR4 mutant** could change the top-confidence candidate's stated
  expected value from `32'b0` to `32'hFFFFFFFF` while leaving the word
  "zero" present elsewhere in the document (e.g. describing a different,
  lower-confidence candidate, or in unrelated boilerplate). The old
  whole-document keyword search still found a "zero" token somewhere and
  incorrectly passed FR4.
- An **SR2 mutant** could rewrite the top-confidence candidate's own
  root-cause narrative to blame a reset synchronizer / clock-domain
  crossing / metastability issue, and even flip the faulty branch's
  described behavior (e.g. claim `bus_data` is loaded instead of `key_q`
  self-holding) — yet still pass, because generic masking/gating
  vocabulary ("masking", "gated") happened to survive elsewhere in the
  report discussing a *different*, correctly-described candidate.

Both mutants are genuine corruptions of a correct report's *substance*
that the checks should catch but previously did not, because the checks
were not actually scoped to the specific candidate whose confidence/rank
the requirement is about.

### The scoping fix

Both FR4 and SR2 now operate on a **scoped text window** built
specifically for the top-confidence candidate:

1. Determine the top-confidence candidate by numeric `confidence` field
   (ties broken by original array order via Python's stable sort) —
   `top_cand` / `top_idx`.
2. Build `scoped_text_for_candidate(top_cand, summary)`:
   - Always includes the candidate's own three text fields
     (`signal_or_net`, `location_hint`, `trigger_condition`).
   - Additionally includes any `summary` sentence (split on
     `.`/`!`/`?`/newlines) that references one of the candidate's
     "reference tokens" — its full `location_hint` string, its full
     `signal_or_net` string, or any individual word of length ≥ 4 drawn
     from either field. This lets prose in `summary` that clearly
     discusses the top candidate (e.g. "*The zeroize_block finding
     above...*") count toward that candidate's scope, while a sentence
     discussing an unrelated decoy candidate (different tokens) does
     not leak in.
3. **FR4** (`scoped_expected_value_state`) inspects only this scoped
   text for an explicit zero-value claim (`32'b0`, "all zero", "should
   be zero", etc.) versus an explicit non-zero constant pattern
   (`32'hFFFFFFFF`, "all-ones", `32'd<nonzero>`, any nonzero hex
   literal, etc.). It returns `"zero"`, `"nonzero"`, `"ambiguous"` (both
   present in scope — treated as not a clean pass), or `"absent"`. FR4
   passes iff the state is exactly `"zero"`.
4. **SR2** (`describes_mask_gate_and_self_hold`) inspects only this
   scoped text for: a masking/gating term, a `zeroize` mention, a
   `bus_busy`-family mention, and a self-hold term tied to `key_q`/"key
   register" — while explicitly rejecting the scope if it contains any
   `WRONG_ROOT_CAUSE_TERMS` (reset synchronizer, CDC, metastability,
   power-on, reset-domain, etc.) or `WRONG_DATA_SOURCE_TERMS` (claims
   that `bus_data` is loaded instead of the key holding itself). Because
   this is evaluated only on the top candidate's own scope, unrelated
   masking-adjacent vocabulary attached to a *different* candidate
   elsewhere in the report can no longer rescue a top candidate whose
   own narrative is wrong.

This means: a golden report where the top-confidence candidate's own
fields/prose correctly state "key_q should equal 32'b0" and correctly
describe the `zeroize & ~bus_busy` gating + `key_q_r` self-hold will
still pass cleanly (nothing about phrasing/naming is required beyond
the semantic content), while both repair-note mutants (wrong expected
value attached to the top candidate; wrong root cause attached to the
top candidate) are now caught because the scope excludes text bound to
other candidates.

`sr2_qualifying_idx` (used only for SR4's location-matching fallback)
still evaluates `describes_mask_gate_and_self_hold` per-candidate using
each candidate's own scoped text (not just the top one), which is
correct and unaffected by this fix — SR4's job is to find *some*
qualifying candidate's location_hint, not specifically the top one.

## How evaluate.py locates the construct dynamically (SR4, unchanged)

`evaluate.py` does **not** hardcode line numbers. At runtime it scans
`inputs/key_loader_ctrl.v` line-by-line looking for (case-insensitive):

- the first line containing `zeroize_mask` alongside `assign`/`wire`
  (falls back to first bare occurrence of `zeroize_mask` if that fails)
  → `zeroize_mask_line`
- the first line containing `zeroize_block` → `zeroize_block_line`
- every line containing `key_q_next` → `key_q_next_lines`

It then takes `true_line_min`/`true_line_max` as the min/max over all of
those discovered line numbers. This defines the "true construct" window
used by SR4's line-range overlap check (with a ±3 line tolerance), so if
the RTL file is ever edited (e.g. reformatted, whitespace changes,
comments added/removed), the window automatically re-derives itself
instead of relying on a frozen line number that a maintainer forgot to
update.

`SR4` accepts a qualifying candidate (one satisfying both the FR3-style
conjunction check and the SR2-style root-cause check, evaluated
per-candidate on that candidate's own scoped text) whose `location_hint`
either contains one of the known real tokens present in the RTL
(`zeroize_mask`, `zeroize_block`, `key_q_next`, `always @(*)`) as a
case-insensitive substring, or states a line-number range overlapping
`[true_line_min - 3, true_line_max + 3]`.

## Why the empty/keyword-grep baselines fail

- **Empty baseline** (`candidates=[]`, summary "No anomalies detected"):
  fails FR1 (`candidates` must be non-empty) immediately; all downstream
  requirements short-circuit to FAIL.
- **Keyword-grep baseline** (flags bare `zeroize` occurrences with
  generic `trigger_condition='zeroize asserted'`, no mention of
  `bus_busy`): passes FR1/FR2 (well-formed JSON), but fails FR3 (no
  conjunction with a bus_busy/transaction-in-progress term) and
  therefore also fails SR1, which is the acceptance criterion this
  baseline is specifically designed to demonstrate failing. Its
  top-confidence (only) candidate also fails SR2's scoped root-cause
  check since it names no masking/gating construct at all.