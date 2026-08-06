# Last-Round Differential Fault Analysis on a Toy SPN

## Overview

The `inputs/` directory contains a small, self-contained 16-bit
substitution-permutation network (SPN) cipher implemented in Verilog,
along with a set of correct/faulty ciphertext trace pairs collected
from a fault-injection campaign against that hardware. Your job is to
analyze the RTL and the trace data to determine:

1. Which internal register in the design is structurally exposed to a
   transient single-nibble fault near the end of encryption.
2. Where (in time, relative to the final output) and which 4-bit
   nibble of that register the fault must hit to produce the observed
   differential ciphertext pairs.
3. How much of the final-round subkey an attacker can recover purely
   by comparing correct and faulty ciphertexts for the same
   plaintext/key (classic Biham-Shamir style differential fault
   analysis, DFA).
4. What concrete hardening measures would mitigate this exposure.

You will express your findings as a single JSON report at
`submission/vulnerability_report.json`.

## Provided artifacts (`inputs/`)

- `design_brief.md` — Plain-English description of the cipher: 16-bit
  plaintext/key, 4 rounds of key-mix + 4-bit S-box substitution +
  bit-permutation, with the final round omitting the permutation step.
  Describes the module hierarchy and top-level ports.
- `spn_core.v` — The cipher core: round logic, S-box table, round-key
  schedule, and the internal state pipeline register.
- `spn_top.v` — Top-level wrapper with a small FSM driving the core
  through its encryption cycles. This is the entry point for
  simulation with `iverilog`/`vvp` if you want to re-simulate the
  design yourself.
- `fault_model.md` — Describes the methodology used to generate the
  trace data: a transient single-nibble corruption injected into some
  internal register at some clock cycle relative to completion of
  encryption. The exact register, cycle, and nibble are **not**
  disclosed here — that is what you must determine.
- `trace_pairs.json` — A small set of plaintext/key/ciphertext trace
  records, each containing a fault-free ciphertext and a
  corresponding faulty ciphertext produced under the (fixed but
  undisclosed) fault condition described above.

**You may not modify anything under `inputs/`.** Treat it as read-only
reference material. Feel free to re-simulate `spn_core.v` /
`spn_top.v` with `iverilog`/`vvp` locally to test hypotheses about
where a fault must be injected to reproduce the patterns you see in
`trace_pairs.json`.

## What you must produce

A single file: **`submission/vulnerability_report.json`**

This is the only file that is graded. It must be valid UTF-8 JSON
(no comments, no trailing commas) and must contain **exactly** the
following seven top-level fields:

| Field | Type | Description |
|---|---|---|
| `vulnerable_register` | string | The exact RTL identifier (as it appears in `spn_core.v`, e.g. `state_q`) of the register you identify as exploitable. |
| `vulnerable_cycle_offset` | integer | Number of clock cycles **before** the final output cycle at which the fault must be injected into that register. `0` = the register's value on the last clock edge before output, `1` = one cycle earlier, etc. |
| `affected_nibble_index` | integer (0–3) | Which 4-bit nibble of the 16-bit register the fault model injects into. `0` = bits `[3:0]`, `1` = bits `[7:4]`, `2` = bits `[11:8]`, `3` = bits `[15:12]`. |
| `recovered_subkey_nibble_index` | integer (0–3) | Which nibble of the 16-bit final round key your analysis recovers. |
| `recovered_subkey_nibble_value` | string | The recovered 4-bit value, written as a single hex digit (e.g. `"9"`). |
| `analysis_method` | string (min 20 characters) | Free-text description of the differential technique you used, referencing `trace_pairs.json`. |
| `hardening_recommendations` | array of strings (at least 2 entries, each at least 10 characters, distinct) | Concrete, technically applicable hardening techniques targeted at the register you identified (e.g. redundancy, error-detection coding, temporal/spatial duplication, glitch-detection sensors). Generic advice unrelated to hardware fault mitigation (e.g. "use a stronger cipher") will not be credited. |

Any additional fields you include beyond these seven are ignored by
the grader. Do not omit any of the seven.

### Example skeleton (values are illustrative placeholders only — not answers)

```json
{
  "vulnerable_register": "some_reg_name",
  "vulnerable_cycle_offset": 0,
  "affected_nibble_index": 0,
  "recovered_subkey_nibble_index": 0,
  "recovered_subkey_nibble_value": "0",
  "analysis_method": "Describe your differential fault analysis approach here, referencing the trace pairs you used and the elimination steps.",
  "hardening_recommendations": [
    "First concrete hardening technique",
    "Second concrete hardening technique"
  ]
}
```

## How to approach it

- Read `design_brief.md` and `spn_core.v` to understand the round
  structure, the S-box, and the round-key schedule, and to identify
  which register(s) hold intermediate state close to the final output
  cycle.
- Read `fault_model.md` to understand exactly what kind of fault was
  injected and what information `trace_pairs.json` gives you about
  its effect.
- For each candidate value of the relevant final-round subkey nibble
  (there are only 16 possibilities, `0x0`–`0xF`), work backward through
  the S-box using the observed correct/faulty ciphertext differences
  in `trace_pairs.json` and check whether that candidate is consistent
  with *every* trace pair. Eliminate candidates that produce a
  contradiction. Correct analysis should leave you with a single
  surviving candidate.
- Determine which register and which cycle offset relative to the
  final output the fault must have hit in order to explain the
  differential pattern you observe — you can hypothesize a location
  and cross-check it by re-simulating `spn_top.v` with `iverilog`/`vvp`
  and injecting a fault at that location/cycle, then comparing the
  resulting faulty ciphertexts to `trace_pairs.json`.
- Propose hardening measures specific to the register and fault
  window you identified.

**Note:** This README does not publish the expected register name,
cycle offset, nibble index, or recovered key value. These are derived
entirely from analyzing the provided RTL and trace data; the grader
computes the correct answers independently by algorithmic
re-derivation from the same artifacts you have access to, not from
any value stated in this document.

## Constraints

- Do not modify any file under `inputs/`.
- Only add/edit `submission/vulnerability_report.json`.
- The report must be self-contained JSON — no external references.
- All reasoning claims (fault location, recovered key nibble) must be
  actually supported by analysis of the provided trace data; assertions
  without a documented elimination process will not be considered a
  correct key recovery, even if the final value happens to be right.

## Submission checklist

- [ ] `submission/vulnerability_report.json` exists and is valid JSON.
- [ ] All seven required fields present with correct types.
- [ ] `affected_nibble_index` and `recovered_subkey_nibble_index` are integers in `0..3`.
- [ ] `recovered_subkey_nibble_value` is exactly one hex character.
- [ ] `hardening_recommendations` has at least 2 distinct, substantive (≥10 character) entries relevant to the identified register.
- [ ] `analysis_method` is at least 20 characters and actually references the trace data / method used.
- [ ] No files under `inputs/` were modified.