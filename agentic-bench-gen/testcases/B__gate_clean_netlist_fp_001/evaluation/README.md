# Gate-Level Trojan Detection — Evaluation Guide

## Objective

You are given a small gate-level (structural Verilog) netlist for a
control/datapath module, along with a design brief and a primary I/O
description. Your job is to analyze the netlist and produce a trojan
analysis report.

## Constraints

- **Do not modify anything under `inputs/`.** Only create/modify files
  under `submission/`.
- The netlist and design brief are self-contained; you do not need any
  external IP or datasheets to complete the analysis.
- Optional cross-checks with `yosys`, `iverilog`, and `vvp` against
  `inputs/gate_netlist.v` are allowed but not required.

## What to submit

Create `submission/trojan_report.json` containing **exactly** these four
top-level fields:

| Field           | Type            | Description                                                                 |
|------------------|-----------------|-------------------------------------------------------------------------------|
| `infected`       | boolean         | `true` if you believe the netlist contains a hardware Trojan, else `false`.   |
| `suspect_nodes`  | array of string | Net/gate/instance names implicated as trigger or payload logic. Empty if clean. |
| `rationale`      | string          | Non-empty explanation of the structural/functional evidence for your verdict. |
| `confidence`     | number          | A value in `[0, 1]` reflecting your confidence in the verdict.               |

No other top-level fields are permitted, and none of the four may be
omitted.

### Requirements on the content

1. **Schema correctness (FR1).** The JSON must parse and contain exactly
   the four fields above with the correct types (`infected` a boolean,
   `suspect_nodes` a list of strings, `rationale` a non-empty string,
   `confidence` a number between 0 and 1 inclusive).

2. **Real identifiers only (FR2).** Every string you list in
   `suspect_nodes` must correspond to an actual wire, port, or gate
   instance identifier that appears verbatim (as a whole word/token) in
   `inputs/gate_netlist.v` — e.g. a wire name, a port name, or a
   `U_`-prefixed instance name. Do not invent names.

3. **Internal consistency (FR3).** If `infected` is `true`,
   `suspect_nodes` must contain at least one entry. If `infected` is
   `false`, `suspect_nodes` must be an empty array.

4. **Grounded rationale (FR4).** Your `rationale` must reference at
   least one specific net, wire, or instance name that actually appears
   in `inputs/gate_netlist.v` — not a generic statement that could apply
   to any netlist. This shows you actually inspected the provided files
   rather than guessing.

## Ground truth for this task

For this particular netlist, **the correct verdict is that the design
is Trojan-free**: `infected` must be `false` and `suspect_nodes` must be
an empty array.

The netlist does contain several nets and structures with low toggle
probability that can superficially resemble trojan trigger circuitry —
for example a reset synchronizer chain, a power-on initialization
counter, and a saturation/overflow comparator built from a wide AND
structure. A naive analysis that flags "rare activity" or "high fan-in
AND gate feeding a rarely-active net" as inherently suspicious, without
checking whether that rare behavior is functionally justified by the
design's documented intent, will produce a **false positive** and will
**fail** this task's grading.

### Rationale quality — naming is not enough

It is not sufficient for your `rationale` to simply **list** the
rare-activity nets/modules you considered (e.g. the reset synchronizer
chain, the init counter, the saturation comparator) and then assert a
blanket verdict such as "looks fine" or "rare activity is generally not
a concern." A bare list of names, or a generic unsupported dismissal
that never explains *why* each specific rare signal is benign, **will
fail grading** — even if `infected`/`suspect_nodes` are otherwise
correct.

Instead, for each rare-activity region you discuss, your rationale must
**connect the named net/module to a specific reason it is functionally
justified**, using explanatory/connecting language. For example:

- "`rst_sync1` and `rst_sync2` only toggle around reset events, **because**
  they form the standard 2-flop release-synchronizer for `rst_n`..."
- "`init_cnt`/`init_done_latched` are active only during the one-time
  post-reset settling window, **which is expected since** the design
  brief documents a fixed power-on initialization sequence..."
- "`sat_cmp_ge_max` is rarely asserted **by design**, as it is the
  saturation comparator for the accumulator's overflow clamp, not an
  unrelated trigger condition..."

In short: name the signal, *and* explain — with a clause that actually
connects the name to a documented functional reason — why its rare
activity is legitimate rather than suspicious. Simply enumerating net
names, or making an unsupported claim that rare signals are "not a
concern" without engaging with each one's documented purpose, does not
demonstrate real analysis and will not satisfy this task's grading. The
exact criteria used to judge "sufficiently grounded" are not published
here, but a rationale that concretely engages with the specific
rare-activity nets in the netlist, their documented purpose, and why
that purpose makes the rare activity benign is expected to succeed.

## Self-check

Run the grader locally with:

```
python3 evaluation/evaluate.py
```

It reads `inputs/gate_netlist.v`, `inputs/design_brief.md`,
`inputs/primary_io.txt`, and `submission/trojan_report.json`, and prints
one line per requirement:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <reason>
```

The script exits `0` only if every requirement passes. A missing
`submission/trojan_report.json` (or missing input file) will be reported
as a `SETUP` failure.