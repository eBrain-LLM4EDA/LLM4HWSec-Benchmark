# SECDED Codec Fault Analysis

## Overview

You are given a synthesizable Verilog implementation of an 8-bit extended-Hamming (SECDED-style) encoder/decoder, `inputs/secded_codec.v`, along with a fixed enumeration of single-bit and two-bit memory faults, `inputs/fault_model.json`. Your task is to analyze the decoder's behavior for every enumerated fault case and produce a structured report at `submission/vulnerability_report.json`.

You do **not** edit any file under `inputs/`. Your only deliverable is `submission/vulnerability_report.json`.

## The RTL Interface

```verilog
module secded_codec(
    input  wire [7:0]  data_in,
    input  wire        encode_en,
    input  wire [12:0] codeword_in,
    output wire [12:0] codeword_out,
    output wire [7:0]  data_out,
    output wire [3:0]  syndrome,
    output wire        overall_parity_error,
    output wire        correctable,
    output wire        uncorrectable,
    output wire [12:0] correction_mask
);
```

- When `encode_en = 1`, the module encodes `data_in` into a 13-bit extended Hamming codeword on `codeword_out`.
- When `encode_en = 0`, `codeword_in` is treated as a (possibly faulty) stored codeword. The module computes:
  - `syndrome` (4 bits): nonzero if any of the four Hamming parity checks (covering bit groups at positions 1, 2, 4, 8) mismatch.
  - `overall_parity_error` (1 bit): 1 if the extended/overall parity bit (bit 0) is violated across all 13 bits.
  - `correctable` / `uncorrectable`: decoder's decision flags about whether (and how) to act on the detected error.
  - `correction_mask` (13 bits): the mask XORed with `codeword_in` before extracting `data_out`.
  - `data_out` (8 bits): the 8 data bits extracted after applying `correction_mask` (or the raw data bits if no correction is applied).

## Codeword Layout

The 13-bit codeword uses the standard extended-Hamming(13,8) layout:

- Bit position **0**: overall (extended) parity bit, covering all other 12 bits.
- Bit positions **1, 2, 4, 8**: Hamming parity bits, each covering a specific subset of the remaining bit positions per standard Hamming placement.
- All other bit positions (3, 5, 6, 7, 9, 10, 11, 12): the 8 data bits, in ascending bit-position order.

See `inputs/design_brief.md` for further background on the intended SECDED semantics (what syndrome and overall parity are supposed to indicate together).

## Fault Model

`inputs/fault_model.json` is a JSON array of exactly 91 fault case objects, each with:

```json
{
  "fault_id": "single_b3",
  "bit_positions": [3],
  "codeword_in": "1011001101100"
}
```

- 13 entries are single-bit flips (`bit_positions` has one element, covering all bit positions 0 through 12).
- 78 entries are two-bit flips (`bit_positions` has two elements, covering all C(13,2) pairs).
- Every `codeword_in` is derived by XOR-flipping the listed bit positions of one fixed, correctly-encoded reference codeword (the reference 8-bit data value and its corresponding correct 13-bit codeword are stated explicitly at the top of `fault_model.json`).

## Optional Cross-Checking

`inputs/fault_enum_tb.v` is a self-contained Verilog testbench that instantiates `secded_codec`, drives it with the same fixed reference codeword and the same fault patterns, and prints the observed `syndrome`, `overall_parity_error`, `correctable`, `uncorrectable`, `correction_mask`, and `data_out` for each case. It can be run standalone with:

```
iverilog -g2012 -o sim inputs/secded_codec.v inputs/fault_enum_tb.v
vvp sim
```

Running this testbench is entirely optional — it is provided purely as a convenience for cross-checking your own analysis. It does not need to be modified or submitted, and it prints only simulated observations, not any "expected" or "correct" answer.

## Your Task

For every one of the 91 fault cases in `fault_model.json`, determine and report:

1. What classification the decoder's behavior corresponds to for that fault: `"no_error"`, `"corrected"`, or `"detected_uncorrectable"`.
2. The observed values of `syndrome`, `overall_parity_error`, `correctable`, `uncorrectable`, `correction_mask`, and `data_out` for that fault case.

You should also:

- Identify the set of fault cases for which you believe the decoder's behavior represents a genuine data-integrity risk (i.e., cases where the decoder's reported status does not accurately reflect the true correctness of `data_out`), and list their `fault_id`s.
- Provide concrete hardening suggestions for the decoder logic based on your analysis.

## Required Output: `submission/vulnerability_report.json`

Write a single JSON object with exactly these top-level fields:

```json
{
  "fault_cases": [
    {
      "fault_id": "single_b3",
      "bit_positions": [3],
      "classification": "corrected",
      "observed_outputs": {
        "syndrome": "0011",
        "overall_parity_error": 1,
        "correctable": 1,
        "uncorrectable": 0,
        "correction_mask": "0000000001000",
        "data_out": "10110010"
      }
    }
  ],
  "summary": {
    "num_no_error": 0,
    "num_corrected": 0,
    "num_detected_uncorrectable": 0
  },
  "vulnerable_fault_ids": [],
  "hardening_suggestions": []
}
```

Field requirements:

- `fault_cases`: one array element per fault case in `fault_model.json` — exactly 91 elements, no duplicates, no missing `fault_id`s. Each element must include:
  - `fault_id` (string, matching a `fault_model.json` entry),
  - `bit_positions` (array of integers, matching that entry),
  - `classification` (string, one of `"no_error"`, `"corrected"`, `"detected_uncorrectable"`),
  - `observed_outputs` (object with keys `syndrome`, `overall_parity_error`, `correctable`, `uncorrectable`, `correction_mask`, `data_out`; `syndrome` and `correction_mask` may be given as binary strings or integers, `data_out` as an 8-bit string or integer, the flag fields as `0`/`1`).
- `summary`: object with integer fields `num_no_error`, `num_corrected`, `num_detected_uncorrectable`, whose sum must equal 91 and must match the counts implied by your per-case `classification` values.
- `vulnerable_fault_ids`: array of `fault_id` strings you have determined represent a genuine data-integrity risk, as described above.
- `hardening_suggestions`: array of strings describing concrete improvements to the decoder logic to eliminate the risks you found.

## Notes

- This is purely an analysis task: no code changes to `inputs/` are graded. Only the content of `submission/vulnerability_report.json` is evaluated.
- A starter/placeholder file already exists at `submission/vulnerability_report.json` — it is intentionally incomplete and must be replaced with your real analysis.
- Field names and types in your submission must match the schema above exactly; malformed or missing fields will cause your submission to fail structural checks regardless of the quality of your analysis.