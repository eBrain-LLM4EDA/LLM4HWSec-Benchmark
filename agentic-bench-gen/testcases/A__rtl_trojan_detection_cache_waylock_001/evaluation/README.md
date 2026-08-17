# Evaluation Guide — RTL Trojan Detection: Way-Lock Release in `cache_ctrl`

## What you are auditing

The RTL under review is `inputs/cache_controller.v`, a 2-way, 8-set cache
controller (`cache_ctrl`) implementing per-way locking as described in
`inputs/design_brief.md`. `inputs/testbench_lock_basic.v` demonstrates
ordinary functional behavior and passes on the shipped RTL — it does not,
by itself, reveal whether the documented lock guarantee holds under every
reachable input sequence.

Your job is to review the design (using any tracing/simulation you find
useful, including `iverilog`/`vvp`) and produce a findings report.

## What you must submit

A single file at:

```
submission/trojan_report.json
```

matching this schema:

```json
{
  "candidates": [
    {
      "location": "string naming the RTL signal/line or module region implicated",
      "confidence": 0.0,
      "rationale": "string explaining the mechanism, including any concrete triggering condition"
    }
  ],
  "summary": "string",
  "tool_evidence": "string or array describing any iverilog/vvp/yosys steps performed, if any"
)
```

Do not modify any file under `inputs/`. Grading reads `inputs/` only for
reference and optional corroboration; it grades the content of your
`submission/trojan_report.json`.

## How `evaluate.py` grades your submission

Grading proceeds in two layers. Every check below must produce a PASS or
FAIL — there is no partial/skip state.

### Format checks (FR1–FR4)

- **FR1** — The file must be valid JSON with top-level `candidates`
  (array), `summary` (string), and `tool_evidence` (string or array).
- **FR2** — Every entry in `candidates` must have a non-empty string
  `location`, a numeric `confidence` in `[0,1]`, and a non-empty string
  `rationale`.
- **FR3** — At least one candidate's `rationale` must state a *concrete*
  triggering condition — specific values for `tag_in` and `secure_attr`
  (not a generic "looks suspicious" statement). See the accepted forms
  below.
- **FR4** — Your report must explicitly say which output(s) are affected:
  `victim_way` selection, versus `hit`/`hit_way`, versus `lock_status`.
  Since these are functionally distinct outputs, be explicit about scope.
  Concretely, the same statement (or the report overall) must make **both**
  halves of a contrastive claim:
  1. an explicit statement that `victim_way`/eviction *is* affected
     (e.g. "victim_way selection is compromised", "only victim_way is
     affected"); **and**
  2. an explicit statement that `hit`, `hit_way`, and/or `lock_status`
     *are unaffected/correct/unchanged* (e.g. "hit_way, hit, and
     lock_status remain correct and unaffected").

  A bare mention of the word `victim_way` or `eviction` somewhere in the
  report — without the accompanying statement that the other outputs are
  unaffected — is **not** sufficient to satisfy FR4. The scope claim must
  be explicit and contrastive, not merely present.

If the JSON is missing, malformed, or not an object, every requirement
(FR1–FR4, SR1–SR4) is marked FAIL under a `SETUP` reason.

### Substantive checks (SR1–SR4)

These grade *what your report claims*, checked against the hidden ground
truth. A generic "this looks suspicious" report, or an empty
`candidates` list, will fail these.

- **SR1** — Some candidate (or the summary) must **affirmatively and
  without hedging** state that a way with its lock bit set can still be
  selected as `victim_way` / evicted — i.e., that the eviction-protection
  guarantee can be bypassed. Merely flagging combinational logic that
  "touches `lock_bits`" without concluding this consequence does not
  satisfy SR1. Critically, describing the bypass *mechanism* is not
  enough if the same text then denies, hedges, or retracts the
  consequence: reports containing phrasing such as "no concrete evidence
  that a locked way is ever actually evicted", "this should be treated as
  a benign/spurious anomaly rather than a security-relevant lock bypass",
  "inconclusive", or "the guarantee appears to remain intact in practice"
  **fail SR1**, even though bypass-mechanism vocabulary (locked/evict/
  victim/bypass) is present. You must commit to the affirmative
  conclusion that the bypass **does** occur under the identified
  condition, not merely that the code raises a question about it.
- **SR2** — Some candidate (or the summary) must name **both** parts of
  the actual triggering condition together: a specific `tag_in` value
  equivalent to `0xA5`, and `secure_attr` equivalent to logic-low/0/
  deasserted. Accepted equivalent forms for the tag value include:
  - `0xA5` / `0xa5`
  - `165` (decimal)
  - `8'hA5`, `8'b10100101`

  Accepted equivalent forms for the security attribute include:
  - `secure_attr == 0` / `secure_attr = 0`
  - "secure_attr low" / "secure_attr deasserted" / "secure_attr false" /
    "secure_attr cleared"

  Naming only one of the two (tag or attribute) is not sufficient —
  both must appear together as the activating condition. As an optional
  corroboration step, `evaluate.py` may compile and simulate
  `inputs/cache_controller.v` with a hidden directed testbench to confirm
  that this trigger reproduces the lock bypass; this is used for
  informational context only and does not independently determine your
  SR2 verdict — your report content is what is graded.
- **SR3** — Your report must not claim that `hit`, `hit_way`, or
  `lock_status` are wrong, corrupted, or compromised. These outputs are
  unaffected by the defect; false claims about them are penalized as
  false positives, even if your primary finding (victim-way bypass) is
  correct.
- **SR4** — Among the candidates that satisfy SR1 (affirmative,
  unhedged) and SR2 (i.e., the correct finding), at least one must carry
  `confidence >= 0.6`. Burying the correct finding at low confidence
  among many hedged, unrelated guesses does not satisfy SR4.

## Tips for self-verification before submitting

`iverilog` and `vvp` are available in this environment. You may write
your own testbench against the pinned module interface:

```
module cache_ctrl(
    input  wire       clk,
    input  wire       rst_n,
    input  wire [2:0] set_idx,
    input  wire [7:0] tag_in,
    input  wire       req_valid,
    input  wire       req_is_write,
    input  wire       secure_attr,
    input  wire       lock_way_req,
    input  wire [0:0] lock_way_sel,
    input  wire       unlock_way_req,
    input  wire [0:0] unlock_way_sel,
    output reg        hit,
    output reg  [0:0] hit_way,
    output reg  [0:0] victim_way,
    output reg  [1:0] lock_status
);
```

to compile `inputs/cache_controller.v` together with a driver of your own
design and observe `victim_way` under a locked way, across a variety of
`tag_in`/`secure_attr` combinations and request sequences, to confirm
whatever hypothesis you report. Remember: all outputs are registered
(Moore-style) and become valid one cycle after the defining input event,
per the timing contract in `inputs/design_brief.md`.

Your `tool_evidence` field should briefly describe what you ran (if
anything) to reach your conclusions.