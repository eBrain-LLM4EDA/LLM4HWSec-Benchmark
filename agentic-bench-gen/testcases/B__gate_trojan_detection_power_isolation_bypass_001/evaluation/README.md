# Gate-Level Trojan Detection: Secure-Domain Isolation Cell — Evaluation Harness

## What this evaluates

This is a **report_grading** task: the participant does not submit code. They
submit an analysis artifact at:

```
submission/trojan_report.json
```

`evaluate.py` reads the reference netlist and supporting files under
`inputs/`:

- `inputs/isolation_wrapper_netlist.v`
- `inputs/primitive_library.v`
- `inputs/design_brief.md`

and grades the *content* of `submission/trojan_report.json` against ground
truth derived from those reference files. Participants must never edit files
under `inputs/`; only `submission/trojan_report.json` is graded.

## How grading works

1. **Schema validation (FR1).** The submitted JSON is parsed and checked for
   the six required top-level fields (`trojan_present`, `confidence`,
   `suspect_nodes`, `affected_outputs`, `violating_condition`,
   `analysis_summary`) with the exact types specified in the task interface.

2. **Structural parsing of the netlist.** `evaluate.py` parses
   `inputs/isolation_wrapper_netlist.v` directly (regex-based structural
   parsing of `AND2`/`OR2`/`MUX2` instantiations and `assign` statements) to
   build:
   - the set of real gate instance names actually present in the netlist
     (used to validate `suspect_nodes` references, FR3);
   - a net driver/consumer graph used to compute the backward fan-in cone of
     each `public_out` bit (used to validate bypass-path relevance, SR3).

   No netlist-specific names are hardcoded — everything is derived from the
   file's own syntax, so any structurally-valid reference netlist (with
   different instance names, wire names, or bypass topology) is graded
   correctly.

3. **Exhaustive co-simulation (ground truth).** `evaluate.py` compiles
   `inputs/isolation_wrapper_netlist.v` and `inputs/primitive_library.v`
   together with `evaluation/tb_isolation.v` using `iverilog`, then runs the
   result with `vvp`. The testbench drives all 32 combinations of
   `(secure_data[3:0], power_down)` and prints one line per vector. This
   establishes ground truth independently of any hardcoded expectations:
   - whether an isolation violation exists at all (SR1);
   - exactly which `public_out` bit(s) are compromised (SR2);
   - the specific triggering vector (`power_down=1`, `secure_data[0]=1`) used
     to substantiate the submitted `violating_condition` (SR4).

4. **Substantive correctness (SR checks).** The submission's
   `trojan_present`, `affected_outputs`, `suspect_nodes`, and
   `violating_condition` fields are checked against the ground truth
   established above — not against any fixed/hardcoded expected report.

## Running the harness

From the repository root:

```
python3 evaluation/evaluate.py
```

Requirements:
- Python 3 standard library only.
- `iverilog` and `vvp` available on `PATH` (used for exhaustive
  simulation-based ground-truth derivation and cross-checks).

## Output format

Each requirement (FR1–FR4, SR1–SR4) emits exactly one line:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <brief reason>
```

## Exit codes

- **0** — every requirement passed.
- **non-zero (1)** — at least one requirement failed, including:
  - `submission/trojan_report.json` missing (`SETUP` failure), or
  - any required `inputs/`/`evaluation/` file missing (`SETUP` failure), or
  - malformed JSON / missing or mistyped fields (FR1), or
  - a substantively incorrect finding (any of FR2–FR4, SR1–SR4).

`SETUP` failures indicate infrastructure problems (missing files) rather than
an incorrect analysis, and are reported with the `SETUP` tag in the failure
message for clarity.

## Notes on toolchain failures

If `iverilog`/`vvp` are unavailable, fail to compile, or time out, every
requirement that depends on simulated ground truth (SR1, SR2, SR3, SR4) is
reported as `[TEST] FAIL` with a diagnostic message describing the
compilation/simulation error — this is treated as a grading failure, not a
silent skip, since ground truth could not be established.