# Evaluation: Gate-Level Trojan Detection — `perm_cone`

This document describes how `evaluate.py` grades a submitted
`submission/trojan_report.json` for the `gate_trojan_detection_demorgan_bypass_001`
task. It is intended for maintainers of the benchmark harness; participants
should refer to the public task specification instead.

## What evaluate.py does

1. **Loads input artifacts.**
   `evaluate.py` reads:
   - `inputs/perm_cone_netlist.v` — the gate-level netlist under analysis.
   - `inputs/reference_truth_table.txt` — the exhaustive 32-line specification
     of correct `grant` behavior for every `(req_level, owner_id)` combination.
   - `submission/trojan_report.json` — the participant's answer file.

   If any of these files is missing, the corresponding requirement checks
   emit `[TEST] FAIL: SETUP: <path> not found` and the script exits with a
   non-zero status immediately. `SETUP` failures are infrastructure-only
   and are not counted as detected mutants.

2. **Computes ground truth via exhaustive simulation.**
   `evaluate.py` contains a small regex-based Verilog gate-level simulator
   that parses the primitive-cell instantiations (`inv`, `nand2`, `nand3`,
   `nor2`) inside the `perm_cone` module body, resolves named port
   connections and simple wire aliases (e.g. `wire a1 = req_level[1];`),
   and propagates signal values to a fixed point for each of the 32 input
   vectors. This yields the netlist's actual `grant` value for every
   vector, which is compared against `inputs/reference_truth_table.txt` to
   compute the ground-truth set of diverging vectors — this is never
   hardcoded, it is derived programmatically from the two input files at
   grading time. For the currently shipped, corrected
   `inputs/perm_cone_netlist.v`, this exhaustive comparison yields exactly
   one diverging vector (`req_level='10'`, `owner_id='101'`,
   `expected_grant=0`, `observed_grant=1`), consistent with the intended
   single-vector authorization-bypass ground truth for this task. No other
   input combination — including `req_level='10'`, `owner_id='100'` —
   diverges from the reference.

3. **Optional iverilog/vvp cross-check.**
   If `iverilog` and `vvp` are available on `PATH`, `evaluate.py` also
   compiles `inputs/perm_cone_netlist.v` together with
   `evaluation/tb_perm_cone.v` (an exhaustive testbench that enumerates all
   32 vectors and prints one `VEC req_level=... owner_id=... grant=...`
   line per vector) and compares the simulated `grant` values against the
   Python simulator's results. Any disagreement is logged as a warning to
   stderr for diagnostic purposes only; it does not change any PASS/FAIL
   verdict. The Python simulator is always the authoritative source for
   grading, since the toolchain may not be installed in every grading
   environment. This cross-check is purely informational and is not tied
   to any individual requirement id.

4. **Identifies ground-truth suspect instances.**
   For the single diverging vector found above, `evaluate.py` performs a
   single-instance output-flip sensitivity analysis: it simulates the
   netlist normally, then re-simulates while forcing each instance's
   output to its complement one at a time, and checks whether doing so
   makes `grant` match the reference value for that vector. The set of
   instances for which this flip restores correctness is the ground-truth
   suspect set — again computed structurally from the netlist, not
   hardcoded to any specific instance name. With the corrected netlist's
   topology, the correction sub-cone that feeds `u_perm_nand3`'s owner-id
   qualifier input is dedicated exclusively to Term 3 and does not share
   gates with the T1/T2 pre-combining stage or the final OR-reduction
   stage, so this analysis resolves to exactly one instance —
   `u_perm_nand3` — rather than implicating the entire downstream OR-tree
   or unrelated gates elsewhere in the design.

5. **Grades the submission against FR1–FR4 and SR1–SR4.**
   Using the ground truth computed above, along with the schema described
   in the task's public interface, `evaluate.py` evaluates eight
   requirements:

   - **FR1** — `submission/trojan_report.json` is valid JSON containing all
     required top-level keys (`trojan_detected`, `suspect_instances`,
     `diverging_vectors`, `explanation`) with the correct JSON types.
   - **FR2** — every entry in `diverging_vectors` has a well-formed
     `req_level` (2-char binary string), `owner_id` (3-char binary
     string), and integer `expected_grant`/`observed_grant` in `{0, 1}`.
   - **FR3** — every name in `suspect_instances` corresponds to an actual
     gate instance identifier that appears in
     `inputs/perm_cone_netlist.v`.
   - **FR4** — `trojan_detected=false` implies an empty `diverging_vectors`
     list, and `trojan_detected=true` implies a non-empty one.
   - **SR1** — since exhaustive simulation confirms a real divergence
     exists between the netlist and the reference truth table,
     `trojan_detected` must be `true`.
   - **SR2** — the submitted `diverging_vectors`, normalized to
     `(req_level, owner_id, expected_grant, observed_grant)` tuples, must
     be exactly set-equal to the ground-truth diverging set. For the
     corrected netlist this ground-truth set is exactly one vector
     (`req_level='10'`, `owner_id='101'`, `expected_grant=0`,
     `observed_grant=1`) — no missing entries and no spurious extras
     (such as `req_level='10'`, `owner_id='100'`, which is bit-exact
     between netlist and reference and must NOT be reported).
   - **SR3** — `suspect_instances` must contain every instance identified
     by the flip-sensitivity analysis as causally responsible for the
     divergence. For the corrected netlist this ground-truth suspect set
     is exactly `{u_perm_nand3}`.
   - **SR4** — the false-positive rate, computed as the fraction of
     submitted vectors/instances that are not corroborated by the ground
     truth, must be exactly zero.

   Each requirement emits exactly one standardized marker line:
   - `[TEST] PASS: <requirement_id>`
   - `[TEST] FAIL: <requirement_id>: <brief reason>`

## Exit codes

- **Exit 0** — every requirement (`FR1`–`FR4`, `SR1`–`SR4`) passed.
- **Exit non-zero** — at least one requirement failed, or a `SETUP`
  failure occurred (missing input/submission file).

## Participant constraints (for context)

Participants must not modify any file under `inputs/`; grading only reads
those files for reference. The only file participants author is
`submission/trojan_report.json`, which must conform exactly to the JSON
schema documented in the task's public interface (`public_spec.interface`).
A naive/empty baseline report (`trojan_detected=false` with empty lists)
is expected to fail `SR1` and `SR2`, since exhaustive simulation of this
netlist against the reference truth table reveals a genuine, single-vector
authorization-bypass divergence at `req_level='10'`, `owner_id='101'`. A
report that correctly identifies that single vector and `u_perm_nand3` but
also pads its answer with additional, non-diverging vectors or unrelated
instance names is expected to fail `SR4` due to a nonzero false-positive
rate.