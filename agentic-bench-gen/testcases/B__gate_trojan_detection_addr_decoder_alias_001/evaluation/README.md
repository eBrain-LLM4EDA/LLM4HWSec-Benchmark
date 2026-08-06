# Gate-Level Trojan Detection — Evaluation Harness

## What this evaluates

This harness grades a single answer file, `submission/trojan_report.json`,
which analyzes the gate-level netlist `inputs/decoder_netlist.v` (a 3-bit
address decoder driving four register-bank write-enable outputs:
`bank0_we`, `bank1_we`, `bank2_we`, `bank3_we`).

The participant does **not** edit or resubmit any file under `inputs/`.
`evaluate.py` reads the following input artifacts purely as reference
material:

- `inputs/decoder_netlist.v` — the structural Verilog netlist under test.
- `inputs/testbench_harness.v` — the participant-facing exhaustive
  testbench shipped alongside the netlist (informational only; not
  compiled by the grader).
- `inputs/gate_library.v` — the primitive gate/DFF wrapper library that
  `decoder_netlist.v` instantiates.
- `inputs/design_brief.md` — the human-readable design intent (not parsed
  by the grader; provided for participant context only).

None of these files are modified. The only artifact `evaluate.py` grades
is `submission/trojan_report.json`.

## Ground truth for this case

The shipped `decoder_netlist.v` implements the following wiring:

- `bank0_we`'s legitimate combinational drive tree is an OR of the
  `addr==000` minterm (`minterm0`) and the `addr==011` minterm
  (`minterm3`), each gated by `write_en`. That is, by this decoder's
  documented address map, address `011` legitimately targets `bank0`.
- `bank1_we` is driven solely by `minterm1` (`addr==001`) gated by
  `write_en`.
- `bank2_we` is driven by an OR-tree that legitimately includes
  `minterm2` (`addr==010`) gated by `write_en`, **plus a hidden alias
  tap**: an extra gate re-derives the `addr==011` condition ANDed with
  `write_en` and ORs that signal into the same tree feeding `bank2_we`'s
  register input.
- `bank3_we` is tied low (unused in this address map).

Consequently, at `addr=011, write_en=1`, **both `bank0_we` and
`bank2_we`** assert simultaneously — a write nominally targeting bank0
also silently asserts bank2's write-enable. For every other legal
combination of `addr` and `write_en`, at most one bank write-enable
asserts. This is the Trojan behavior the submitted report is expected to
identify.

## How grading works

Grading proceeds in three stages:

1. **Structural parsing (feeds FR1, FR3, SR4).** `decoder_netlist.v` is
   parsed with a small regex-based structural parser to recover its port
   list, declared wires, gate/module instances (type, instance name, port
   connections), and `assign` statements. This builds:
   - the universe of valid net names and instance names for schema
     checks (FR1, FR3),
   - a name-agnostic structural trace of which gate instance(s) actually
     bridge the `addr==011` decode tap into the `bank2_we` enable tree
     (used for SR4). The trace works by data-flow analysis — which nets
     carry the `addr==3'b011` condition (optionally ANDed with
     `write_en`), and which gate's output structurally feeds the
     flip-flop driving `bank2_we` — not by matching any particular
     baseline instance name. Any correctly-renamed/restructured golden
     netlist analysis is still recognized as long as it names the
     equivalent net or instance.

2. **Exhaustive ground-truth simulation (feeds SR2, SR3, SR5).**
   `evaluation/tb_exhaustive.v` is a self-contained testbench
   (independent of `inputs/testbench_harness.v`) that instantiates
   `decoder_netlist` with the ports declared in `decoder_netlist.v`,
   applies synchronous reset, then sweeps all 8 address values crossed
   with both `write_en` values (16 vectors), printing one
   `VEC addr=... we=... b0=... b1=... b2=... b3=...` line per vector.
   `evaluate.py` compiles this with `iverilog -g2012` against
   `inputs/decoder_netlist.v` and `inputs/gate_library.v`, runs it with
   `vvp`, and parses the 16 `VEC` lines into a ground-truth activation
   table. This table is used to cross-check the submitted trigger
   condition and affected outputs.

3. **JSON schema and content checks (feeds FR1–FR4, SR1).** The
   submitted JSON is validated directly against the pinned schema and
   its literal field values.

## Requirement checks

- **FR1** — required top-level fields present with correct types;
  `suspect_nets` entries each have `net_name`, `gate_instance`, and
  `role` restricted to `trigger`/`payload`/`benign`; `control_inputs`
  keys match actual declared ports in `decoder_netlist.v` (must include
  `write_en`).
- **FR2** — `design_under_test` equals the literal string
  `"decoder_netlist.v"`; `trigger_condition.address` is a well-formed
  3-character `'0'`/`'1'` string.
- **FR3** — `affected_outputs` entries are restricted to actual output
  port names declared in `decoder_netlist.v`; at least two distinct
  entries are present when `trojan_present` is `true`.
- **FR4** — the report is scoped to a single address (singleton
  `trigger_condition` object, flat `affected_outputs` list of plain
  strings), not a blanket multi-address claim.
- **SR1** — `trojan_present` must be `true`.
- **SR2** — `trigger_condition.address` must be `"011"` and
  `control_inputs.write_en` must be `"1"`, cross-checked against the
  simulated ground truth showing multiple write-enables assert at that
  stimulus.
- **SR3** — `affected_outputs` must equal exactly
  `{"bank0_we", "bank2_we"}`, cross-checked against the simulated ground
  truth for `addr=011, write_en=1`.
- **SR4** — `suspect_nets` must name (by net name or gate instance name)
  a structurally identified bridging gate — one whose inputs include the
  `addr==011` decode condition and whose output feeds the `bank2_we`
  register — with role `trigger` or `payload`. Matching is purely
  structural/name-agnostic; any correct, independently-renamed
  identification of the equivalent gate passes.
- **SR5** — the reported trigger address must match the unique address
  at which the exhaustive simulation shows more than one write-enable
  asserting, and no other address may exhibit such an anomaly (a
  false-positive/false-negative check against the full 16-vector ground
  truth).

## Marker format and exit contract

Each of the nine requirement ids below is checked exactly once. Every
check prints exactly one line:

```
[TEST] PASS: <id>
[TEST] FAIL: <id>: <reason>
```

Requirement ids: `FR1`, `FR2`, `FR3`, `FR4`, `SR1`, `SR2`, `SR3`, `SR4`,
`SR5`.

`evaluate.py` exits `0` only if all nine checks print `PASS`; it exits
non-zero if any check fails (including compile/simulation failures of
`evaluation/tb_exhaustive.v` against the input netlist, which are
reported as ordinary `FAIL` reasons on the affected requirement ids, not
as `SETUP` failures). A missing required input artifact or missing
`submission/trojan_report.json` produces `[TEST] FAIL: SETUP: <path> not
found` and exits non-zero; this is treated as an infrastructure failure,
not a graded requirement outcome.

## Running locally

```
python3 evaluation/evaluate.py
```

Requires `iverilog` and `vvp` on `PATH` for the SR2/SR3/SR5 simulation
cross-checks; FR1–FR4 and the SR4 structural trace do not require the
toolchain, but SR2/SR3/SR5 will fail with a descriptive reason if the
toolchain or simulation is unavailable. The submission is graded in
place; `evaluate.py` never modifies any file under `inputs/`.