# Anti-SAT Locked Netlist Analysis — Submission Instructions

This directory contains the automated grading harness for the logic
deobfuscation / SAT-attack-assistance task. This README describes how to
produce and validate your submission. It intentionally does not disclose
any of the hidden ground-truth values, gate names, or key values used
internally by the grader — those are exactly what your analysis is
expected to (re)discover from the provided netlist.

## What you are given

Under `inputs/` you will find:

- `locked_netlist.v` — the gate-level combinational netlist to analyze.
- `locking_description.md` — background on the general class of locking
  techniques that may be present, and general guidance on what structural
  evidence to look for.
- `primary_io.txt` — a reference listing of the module's primary input,
  key input, and primary output ports (names, widths, directions).

You may inspect these files freely, and you may use the available
toolchain (`yosys`, `iverilog`, `vvp`) to help your analysis — for
example, loading the netlist into `yosys` for a structural overview, or
using `iverilog`/`vvp` to simulate the netlist as given. None of this
tooling is required to pass; you may also do the entire analysis by
reading the netlist text directly, since it is small (well under 300
gate instances).

**Do not modify anything under `inputs/`.** Only your answer file under
`submission/` is read and graded.

## What you must produce

A single JSON file at:

```
submission/recovered_key.json
```

conforming exactly to the schema defined in the task's public
specification (`public_spec.interface`):

```json
{
  "key_bits": [
    {
      "key_input": "key[<i>]",
      "value": "0" | "1" | "unknown",
      "confidence": <number in [0,1]>,
      "reasoning": "<non-empty explanation string>"
    },
    ...
  ],
  "key_gate_locations": ["<instance/wire name>", ...],
  "topology_summary": "<free-text description>"
}
```

Notes on the schema, drawn directly from the public interface:

- `key_bits` must be a non-empty array that covers **every** key input
  declared in `locked_netlist.v` (check `primary_io.txt` and the `key`
  port declaration for the exact bit range and naming convention) — no
  duplicates, no omissions.
- `key_gate_locations` must be a non-empty array of exact identifiers
  (gate instance names or wire names) that actually appear in
  `locked_netlist.v`.
- `topology_summary` must be a non-empty string describing how the
  key-gating structure(s) you identified connect to the circuit's
  internal nets and primary output(s), naming the specific nets/ports
  involved.
- For any `key_bits` entry with `value` `"0"` or `"1"`, `confidence` must
  be a number in `(0, 1]` and `reasoning` must be a non-empty string of
  at least 15 characters explaining the structural basis for the claim.
- For any `key_bits` entry with `value` `"unknown"`, `confidence` must be
  exactly `0`.

## How to run the grader locally

From the repository root:

```
python3 evaluation/evaluate.py
```

`evaluate.py`:

- reads `inputs/locked_netlist.v`, `inputs/locking_description.md`, and
  `inputs/primary_io.txt` for reference (as ground truth about the
  circuit under analysis, not as something to modify);
- reads and grades `submission/recovered_key.json`;
- optionally may invoke `yosys`/`iverilog`/`vvp` against the input
  artifacts for cross-checks, but the pass/fail verdict is always
  determined by grading the content of your submitted answer file;
- prints one line per checked requirement, either
  `[TEST] PASS: <requirement_id>` or
  `[TEST] FAIL: <requirement_id>: <reason>`;
- exits with status `0` only if every requirement passes, and non-zero
  otherwise.

If `submission/recovered_key.json` is missing, is not valid JSON, or is
not a JSON object, every requirement is reported as failing and the
grader exits non-zero — make sure your file exists at exactly that path
and parses as a JSON object before submitting.

## What is being checked

The grader applies two broad categories of checks. It does not reveal
which specific bits, wires, or gate names it expects — your submission
is judged against the actual content of `inputs/locked_netlist.v`.

**Format / schema checks** — these verify the *shape* of your answer,
independent of whether your conclusions are correct:

- Every key input declared in the netlist is covered in `key_bits`
  exactly once (no gaps, no duplicates).
- Every `key_input` name in `key_bits` and every entry in
  `key_gate_locations` must correspond to an identifier that genuinely
  exists in `locked_netlist.v` — invented or misspelled names will not
  validate.
- Any key bit reported with a concrete value (`"0"` or `"1"`) must carry
  a valid confidence score and a substantive (non-trivial-length)
  reasoning string explaining the structural evidence behind the claim.
- Any key bit reported as `"unknown"` must carry a confidence of exactly
  `0` — do not report a nonzero confidence alongside `"unknown"`, and do
  not use `"unknown"` as a way to sneak in a nonzero confidence guess.

**Substantive-correctness checks** — these verify that your *conclusions*
are actually right, by comparing them against the real structure of
`locked_netlist.v`:

- Whether the gate/wire identifiers you list in `key_gate_locations`
  actually correspond to the netlist's key-gating logic (as opposed to
  arbitrary or unrelated identifiers that merely happen to exist in the
  file).
- Whether any key bits you claim to have determined with high confidence
  are actually correct, and whether that determination is genuinely
  supportable from netlist structure alone (as opposed to a guess dressed
  up with a high confidence value). Bits that are not structurally
  determinable should be left as `"unknown"` rather than asserted.
- Whether your `topology_summary` correctly and substantively describes
  how the identified gating logic combines with the rest of the design
  to affect the primary output, naming the actual internal net(s) and
  output port(s) involved — a generic or vague description will not
  satisfy this check.

## Tips

- Read the entire netlist; it is short. Pay attention to instance names,
  wire names, and how literals are constructed and combined, since
  synthesis/locking artifacts are often visible directly in the text.
- Distinguish between logic that is part of the circuit's ordinary
  function and logic that exists specifically to gate/mask that function
  based on the key.
- Be conservative: only report a concrete `0`/`1` value with high
  confidence when you have concrete, checkable, structural evidence for
  it in the netlist text. When in doubt, report `"unknown"` with
  confidence `0` rather than guessing — high-confidence claims that are
  not backed by genuine structural evidence are penalized, not rewarded.