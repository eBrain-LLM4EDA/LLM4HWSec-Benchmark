# Logic Deobfuscation: Locked Netlist Structural Analysis

## Task Overview

You are given a gate-level combinational netlist that has been logic-locked
using an unspecified key-insertion scheme. The netlist contains a set of key
inputs (`key[0]` through `key[9]`) that must be set to the correct secret
values for the circuit to compute its intended function. Incorrect key
values cause the circuit to compute the wrong output.

Your job is to analyze the **structure** of the netlist and produce a report
that identifies:

1. Which gates/wires implement key-dependent gating logic.
2. How the key inputs feed into the overall circuit topology.
3. Any key bit values that can be determined **purely from netlist
   structure** (i.e. without needing a functional oracle), along with your
   confidence and reasoning for each such determination.

Bits you cannot structurally determine should be reported as `unknown`
rather than guessed. Guessing incorrectly with high confidence is worse than
honestly reporting `unknown`.

## Input Artifacts

All input artifacts are in `inputs/` and must **not** be modified:

- `inputs/locked_netlist.v` — the gate-level Verilog netlist under
  analysis. This is the ground truth you are reverse-engineering.
- `inputs/locking_description.md` — a short description of the general
  class of locking scheme that may have been used, and pointers on how to
  approach the analysis.
- `inputs/primary_io.txt` — a plain-text reference table of the module's
  primary input/output ports (names, widths, directions) so you can
  cross-check identifiers against the netlist.

You may use `yosys` (e.g. `read_verilog`, `stat`, `show`), `iverilog`, and
`vvp` to inspect and simulate the netlist. These tools let you explore
structure and simulate the circuit **as given** — you do not have access to
any external functional oracle, golden output table, or reference key. Any
conclusion about key values must be justifiable from the netlist itself
(e.g., a key input wire is observed to be tied to a constant-driving cell,
a key literal only reaches a structurally identifiable substructure, etc.).

## What To Submit

Edit **only** `submission/recovered_key.json`. Do not modify anything under
`inputs/`. The evaluator reads the input artifacts for reference and grades
the content of your submission file.

### Schema

`submission/recovered_key.json` must be valid JSON with exactly this
top-level shape:

```json
{
  "key_bits": [
    {
      "key_input": "key[0]",
      "value": "0",
      "confidence": 0.9,
      "reasoning": "Explain the structural evidence here."
    }
  ],
  "key_gate_locations": [
    "instance_or_wire_name_from_netlist"
  ],
  "topology_summary": "Free-text description of the gating structure and how it connects to the primary output."
}
```

Field requirements:

- **`key_bits`**: a non-empty array containing **exactly one entry for
  every key input declared in `inputs/locked_netlist.v`** — no duplicates,
  no omissions.
  - `key_input`: must exactly match a key input wire name as it appears in
    `locked_netlist.v` (e.g. `"key[4]"`).
  - `value`: one of `"0"`, `"1"`, or `"unknown"`.
  - `confidence`: a number.
    - If `value` is `"0"` or `"1"`, confidence must be strictly greater
      than 0 and at most 1.
    - If `value` is `"unknown"`, confidence must be exactly `0`.
  - `reasoning`: a non-empty string. If `value` is `"0"` or `"1"`, this
    string must be at least 15 characters long and must explain the
    structural basis for the claim (a vague or generic sentence that does
    not correspond to real netlist evidence will be treated as
    unsupported).
- **`key_gate_locations`**: a non-empty array of strings. Every string must
  exactly match a gate instance name or wire name that actually exists in
  `inputs/locked_netlist.v`. This should list every gate/wire you believe
  implements or carries key-gating logic.
- **`topology_summary`**: a non-empty free-text string describing how the
  key-gating structure(s) you identified connect between internal locked
  nets and the primary output(s). Reference the actual net/port names
  involved (as found in the netlist) rather than describing things only in
  the abstract.

## Constraints

- Do not modify any file under `inputs/`.
- Submit only `submission/recovered_key.json`; no other files are graded.
- Base all structural claims on `inputs/locked_netlist.v` and
  `inputs/locking_description.md`. Do not assume access to any functional
  oracle beyond what you can observe by inspecting or simulating the
  provided netlist itself with `yosys`/`iverilog`/`vvp`.
- The netlist is small (well under 300 gate instances), so it is feasible
  to fully read through it by hand or to load it with
  `yosys -p "read_verilog inputs/locked_netlist.v; stat; show"` for a
  structural overview.
- Every `key_input` name in `key_bits` and every name in
  `key_gate_locations` must be a verbatim identifier found in
  `inputs/locked_netlist.v` — check with a simple text search if unsure.

## Suggested Approach

1. Read `inputs/primary_io.txt` to get the full port list, then confirm it
   against `inputs/locked_netlist.v`.
2. Read `inputs/locking_description.md` for general hints about the class
   of locking scheme in use.
3. Trace, gate by gate, how each `key[i]` input is consumed: does it feed a
   simple XOR/XNOR key gate directly gating a data path, does it feed into
   a larger sub-network, or is its declared input wire actually overridden
   by some other signal before it reaches any logic?
4. Look specifically for any place where a key input's declared wire does
   not actually drive the logic that "should" depend on it — e.g., a
   constant-driving cell substituted at the position where a key literal
   would otherwise be expected. Such a substitution is directly observable
   in the netlist text and is the strongest form of structural evidence
   you can report with high confidence.
5. For every key bit where you cannot point to concrete netlist evidence,
   report `"unknown"` with confidence `0` rather than fabricating a value.
6. Write `topology_summary` describing, using actual identifiers from the
   netlist, how the key-dependent substructures you found connect to the
   final primary output.