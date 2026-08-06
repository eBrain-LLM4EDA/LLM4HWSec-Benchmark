# Gate-Level Trojan Detection — TMR Voter Cloning

## What this task is about

`inputs/tmr_voter_netlist.v` implements a Triple Modular Redundancy (TMR)
block: three replica instances (`u_replica_a`, `u_replica_b`, `u_replica_c`)
each compute the same function of shared primary inputs `a`, `b`, `c`, and
feed a majority voter (`u_voter3`) whose output is the top-level port
`voted_out`. The design is supposed to guarantee that any single replica
fault is masked by the 2-of-3 vote.

Your job as a participant is to analyze the netlist (structurally, and
optionally by simulating it with the provided toolchain) and produce a
single answer file:

```
submission/trojan_report.json
```

`evaluation/evaluate.py` reads `inputs/tmr_voter_netlist.v` and
`inputs/fault_harness_tb.v` for reference only. It does **not** grade the
netlist itself — it grades the content of your submitted
`trojan_report.json` against the hidden ground truth for this instance.

## Required fields (`trojan_report.json`)

| Field | Type | Meaning |
|---|---|---|
| `trojan_present` | boolean | `true` if a wiring anomaly defeating single-fault masking was found |
| `suspect_instances` | array of strings | gate-level instance names (as they appear in the netlist) implicated in the anomaly |
| `suspect_nets` | array of strings | net names carrying the corrupted/duplicated signal |
| `affected_output` | string | top-level output net vulnerable to a single fault |
| `root_cause` | string (<=500 chars) | free-text explanation of the defect |
| `confidence` | number in `[0.0, 1.0]` | self-reported confidence; recorded but not gating |

The file must be valid UTF-8 JSON with no trailing comments. If the file
cannot be parsed as JSON at all, or is not a JSON object, the grader FAILs
FR1 deterministically — this is caught and reported explicitly, it is never
silently swallowed by a later check.

## How grading works

### FR1 — Schema validity
The submission file must parse as JSON and contain all six fields above
with the correct types (`trojan_present` a real boolean, the two suspect
lists arrays of strings, `affected_output`/`root_cause` strings,
`confidence` a number in range). Any missing or mistyped field, or any
JSON parse failure, fails FR1 — and since every other check depends on
well-typed fields, all downstream requirements are also marked failed in
that case.

### FR2 — `suspect_instances` reference real instances
If `trojan_present` is `true`, every name in `suspect_instances` must
match (case-insensitively) an actual instance identifier that
`evaluate.py` parses out of `tmr_voter_netlist.v`'s instantiation
statements (only instances of modules actually declared in that file are
counted, so primitive gates like `and`/`or`/`buf` are not mistaken for
named instances). An empty list when `trojan_present=true` also fails.

### FR3 — `suspect_nets` reference real nets
Same idea as FR2 but for net/wire names: `evaluate.py` builds the set of
valid net names from `wire`/`input`/`output` declarations, `assign`
statements, primitive-gate argument lists, and named port connections
(`.port(net)`) in the netlist. If `trojan_present` is `true`,
`suspect_nets` must be non-empty and every entry must be a real,
parsed net name.

### FR4 — `affected_output` is a real top-level output
`affected_output` must exactly match (case-insensitively) one of the
output ports declared in the `tmr_top` module header — in this instance,
`voted_out`.

### SR1 — Identifies a wiring/connectivity defect, not a logic bug
The ground truth is that `voter_b` is driven by an inserted buffer/tap
cell from `replica_a`'s output net rather than from `replica_b`'s own
output net, so two of the three voter inputs trace back to the same
replica. To pass SR1:

- `trojan_present` must be `true`,
- `suspect_nets` must include at least one of the aliased nets involved
  in this duplication (the shared source net or either of the two
  affected voter-input nets), **and**
- `root_cause` must actually characterize the defect as a
  wiring/connectivity duplication or aliasing issue — i.e. that a single
  replica's output net is reaching two distinct voter inputs — rather
  than describing it as an internal logic-equation, functional, or
  gate-level Boolean-function defect inside some cell.

A report that lists the exact right net names (e.g. `net_repa_out`,
`voter_b`) but narrates the cause as, say, "the buffer's internal
equation is wrong" or "the voter's internal logic incorrectly computes
its function" **fails SR1**, even though the listed nodes are correct —
because that narrative mischaracterizes a connectivity/aliasing bug as a
functional/logic-design bug, and the whole point of this exercise is
recognizing *which class* of defect this is. This also rules out reports
that only complain about "the voter is broken" in the abstract, with no
wiring/aliasing framing at all.

### SR2 — Names the specific cloning instance
The report must unambiguously identify the actual buffer/tap instance
responsible for the aliasing — either by:

- listing its real instance name in `suspect_instances`, or
- describing in `root_cause` (in prose) that replica_a's output net is
  the one feeding voter_b's input, using recognizable tokens for both
  sides of that relationship.

Naming **only** the voter instance in `suspect_instances` (with no
supporting causal narrative naming the replica_a → voter_b relationship)
is explicitly insufficient and fails SR2 — pointing at the voter, or at
the replicas in general, without pinning down the specific cloning/tap
cell or the specific replica-to-voter-input relationship responsible, does
not identify the actual defect.

### SR3 — Flags replica_b's true output as dangling/unused
`evaluate.py` performs a structural fanout scan over the netlist to
confirm that replica_b's genuine output net has no consumer anywhere in
the design (the structural fingerprint of the attack: replica_b's real
work product is computed but never used). The submission must flag this
specific net as dangling/unused/disconnected — either by listing it in
`suspect_nets` or by describing it as unused in `root_cause` alongside a
reference to replica_b.

### SR4 — Correct affected output and non-negation of the finding
`trojan_present` must be `true`, and `affected_output` must equal
`voted_out`. `evaluate.py` also makes a best-effort attempt to
empirically corroborate this by compiling and simulating the netlist
together with an auxiliary fault-injection testbench
(`evaluation/fault_sim_tb.v`, distinct from `inputs/fault_harness_tb.v`)
via `iverilog`/`vvp`, comparing a fault-free run against a run with a
stuck-at fault forced onto replica_a's output net. This corroboration is
best-effort and does not itself gate the verdict beyond the field checks
above (missing toolchain, compile errors, or timeouts are swallowed
without affecting the result) — the field-level checks are always
authoritative for PASS/FAIL.

## What must fail

- A missing `submission/trojan_report.json` fails every requirement with
  a `SETUP` reason and exits non-zero.
- A malformed/unparseable `trojan_report.json` fails FR1 deterministically
  (and, since downstream checks depend on it, every other requirement).
- The naive/empty baseline (`trojan_present=false`, empty suspect lists)
  fails every SR check, because it never asserts the trojan exists at
  all, never names the cloning instance, never flags the dangling net,
  and never identifies `voted_out` as affected under
  `trojan_present=true`.
- A report that names only the voter instance, or only unrelated
  instances, without identifying the true cloning cell (or an
  unambiguous causal replica-to-voter-input description), fails SR2.
- A report that lists the right net names but narrates the defect as an
  internal logic/functional bug rather than a wiring/duplication issue
  fails SR1, even though the net evidence is present. In other words,
  getting the affected nodes right is necessary but not sufficient for
  SR1 — the narrative must also correctly classify *what kind* of defect
  this is.
- A report that only accuses the voter or unrelated instances/nets,
  without identifying the true cloning cell or the aliased/dangling
  nets, fails SR2 and/or SR3 even if `trojan_present=true`.

## What must pass

Any report — regardless of wording, JSON key ordering, or exact phrasing
in `root_cause` — that correctly sets `trojan_present=true`,
`affected_output="voted_out"`, names the real cloning/tap instance (or
unambiguously describes the replica_a→voter_b aliasing) rather than only
naming the voter, correctly characterizes the defect as a
wiring/connectivity duplication (not an internal logic bug), includes the
aliased net(s) and the dangling replica_b output net among
`suspect_nets`, and only references real instance/net names parsed from
`tmr_voter_netlist.v`, will pass all eight checks — independent of how
differently it is structured or worded compared to any reference
implementation.