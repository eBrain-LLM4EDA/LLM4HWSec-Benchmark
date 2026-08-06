# RTL Hardware Trojan Detection — Evaluation Harness

## What gets graded

This task ships a fixed instruction-decode RTL module under `inputs/`:

- `inputs/decode_ctrl.v` — the RTL design under analysis.
- `inputs/design_brief.md` — documentation of the module's intended behavior.
- `inputs/opcode_map.txt` — the authoritative table of documented opcodes and
  their expected output values.

You must **not modify anything under `inputs/`**. Your job is to analyze
these fixed artifacts and produce a security analysis report at:

```
submission/trojan_report.json
```

`evaluate.py` reads the `inputs/` artifacts for reference, optionally
cross-checks them by simulating `inputs/decode_ctrl.v` against a hidden
testbench (using `iverilog`/`vvp`), and grades the **content of your
submitted report** against the expected findings. The RTL and its
documentation are not modified by grading — only your report is scored.

## Required schema: `submission/trojan_report.json`

The file must be valid JSON, structured as a single top-level object:

```json
{
  "candidates": [
    {
      "trigger_opcode": "0x5A",
      "payload_signal": "some_output_net",
      "confidence": 0.85,
      "rationale": "Free-text explanation of the evidence supporting this finding."
    }
  ],
  "summary": "optional free-text summary"
}
```

Field requirements for every element of `candidates`:

- `trigger_opcode` (string) — an 8-bit opcode value or a description of the
  triggering condition. Hex (`"0x5A"`), Verilog-style (`"8'hE7"`), binary
  (`"0b01011010"`), and plain decimal/hex-digit strings are all accepted and
  normalized before comparison.
- `payload_signal` (string) — the exact RTL net/output name that is
  illegitimately asserted by the finding (e.g. `write_enable`,
  `privilege_ok`).
- `confidence` (number) — a value in `[0, 1]` expressing how confident you
  are in this specific finding.
- `rationale` (string, non-empty) — a free-text explanation of the evidence
  behind the finding. A rationale should reference concrete evidence (e.g.
  divergence from the documented opcode table, structure of the RTL code,
  or simulation results) rather than being a generic, unsubstantiated
  claim.

The top-level `summary` field is optional and is not required for grading.

An empty `candidates` array (`{"candidates": []}`) is treated as a
naive "no finding" baseline and will **fail** the detection-related checks.

## Toolchain usage

`iverilog` and `vvp` are available in the evaluation environment and are
used internally by `evaluate.py` to simulate `inputs/decode_ctrl.v` and
cross-check its behavior against `inputs/opcode_map.txt` (e.g. confirming
that documented opcodes produce their documented outputs, and identifying
any opcode values whose simulated behavior deviates from the "undocumented
opcodes must be inert" contract described in `inputs/design_brief.md`).

You are welcome to run the same toolchain yourself while doing your own
analysis (e.g. simulating specific opcode values against
`inputs/decode_ctrl.v` to confirm a hypothesis before including it in your
report), but doing so is entirely optional — a correct, well-evidenced
report is all that is required for grading.

## What causes a report to fail

- An empty `candidates` array.
- A report that includes, at high confidence, any candidate citing an
  opcode already listed in `inputs/opcode_map.txt` as a documented
  instruction, or naming an unrelated signal (e.g. `alu_op`, `valid`,
  `write_enable` in isolation) as its finding — this counts as a false
  positive and will fail the false-positive control, **even if** another
  candidate in the same submission correctly identifies the true finding.
  Keep every candidate you submit well-supported; do not pad the
  `candidates` array with speculative or low-value entries just to appear
  thorough.
- Malformed JSON, a missing `candidates` key, or candidate objects missing
  any of the required fields (`trigger_opcode`, `payload_signal`,
  `confidence`, `rationale`).
- A generic, boilerplate rationale (e.g. "Trojan detected." with no
  supporting detail) attached to an otherwise correct finding.

## Running the evaluator

From the repository root:

```
python3 evaluation/evaluate.py
```

The script prints one line per requirement in the form:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <reason>
```

The process exits with code `0` only if every requirement line reports
`PASS`; otherwise it exits non-zero.