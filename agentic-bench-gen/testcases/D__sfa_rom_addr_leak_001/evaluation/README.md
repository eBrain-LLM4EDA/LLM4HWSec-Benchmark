# Evaluation Guide: Secret-Dependent ROM Address-Bus Leakage Review

## What is graded

`evaluate.py` grades a single answer file that you submit:

```
submission/vulnerability_report.json
```

No other submitted files are read or graded. You must not modify anything under `inputs/`.

For reference while writing your report, `evaluate.py` reads (but does not grade) the following input artifacts:

- `inputs/subst_lookup.v` — the RTL module under review.
- `inputs/address_traces.json` — captured `(public_index, observed_rom_addr)` pairs from a fixed, unknown `secret_key`.
- `inputs/design_brief.md` — a functional description of the module's intended behavior.

## Required JSON schema

Your `submission/vulnerability_report.json` must be a single JSON object with exactly these fields:

```json
{
  "leaking_signals": [string, ...],
  "non_leaking_signals": [string, ...],
  "recovered_secret_key": <integer 0-15>,
  "leakage_relationship": "<string>",
  "mitigation_patch": "<string containing Verilog RTL>",
  "mitigation_rationale": "<string>"
}
```

Field notes:

- **`leaking_signals`** — a non-empty array of exact RTL signal names (as they appear in `inputs/subst_lookup.v`) that carry secret-dependent information observable on an address bus or memory-indexing path.
- **`non_leaking_signals`** — a non-empty array of exact RTL signal names that do NOT carry secret-dependent information observable in this threat model (address/bus observation only — not internal register/wire values that are never placed on an observable bus or memory port).
- **`recovered_secret_key`** — an integer in `[0, 15]` representing the `secret_key` value you determined from `inputs/address_traces.json`. This value must be consistent with *every* entry in the trace file, not merely a majority of them.
- **`leakage_relationship`** — a precise mathematical/logical statement of how the leaking signal(s) relate to `public_index` and `secret_key` (e.g. of the form `rom_addr_q = public_index XOR secret_key`). State the relationship explicitly; do not merely allude to it.
- **`mitigation_patch`** — a Verilog RTL snippet or full replacement module that eliminates any secret-dependent memory/array addressing while preserving the module's original `table_data` behavior for every `(public_index, secret_key)` combination.
- **`mitigation_rationale`** — a prose explanation of why your patch removes the address-dependent leakage while preserving functional correctness.

## Requirements on signal names

Every string you list in `leaking_signals` or `non_leaking_signals` must correspond to a signal that is actually declared, assigned, or referenced in `inputs/subst_lookup.v` (ports, internal `wire`/`reg` declarations, `assign` targets, or always-block assignment targets). Both arrays must be non-empty.

## Requirements on `mitigation_patch`

Your `mitigation_patch` should define a complete, self-contained Verilog module. For it to be simulated and checked for functional equivalence against the original module, it should:

- Declare a module named `subst_lookup_patched` (preferred), and
- Expose the same port list as the original module: `clk`, `rst_n`, `public_index [3:0]`, `secret_key [3:0]`, `table_data [3:0]` (output), matching the pinned interface:

  ```verilog
  module subst_lookup_patched(
      input  wire       clk,
      input  wire       rst_n,
      input  wire [3:0] public_index,
      input  wire [3:0] secret_key,
      output wire [3:0] table_data
  );
  ```

If you instead reuse the original module's name in your patch text, the grader will attempt to rename it internally for co-simulation purposes, but supplying a distinctly named module (`subst_lookup_patched`) with the exact pinned port list is the most robust way to ensure your submission is evaluated as intended.

Your patched module's `table_data` output must match the original module's `table_data` output for every one of the 256 possible `(public_index, secret_key)` combinations, respecting the same reset and pipeline-latency behavior described in `inputs/design_brief.md`. A full-table-scan or bit-sliced boolean-evaluation strategy (evaluating all ROM entries in parallel and selecting the correct one without computing a secret-dependent address) is an example of a valid approach — this is not the only valid approach, and any implementation is acceptable as long as it satisfies this functional-equivalence property and does not compute a secret-dependent index used to select a memory location.

## How grading works

- Your submitted JSON is checked for the presence and correct types of all six required fields.
- Your `recovered_secret_key` is checked against **every** entry in `inputs/address_traces.json` under the relationship `observed_rom_addr = public_index XOR recovered_secret_key`.
- Your `leaking_signals` / `non_leaking_signals` lists are checked against the real signal names present in `inputs/subst_lookup.v`.
- Your `leakage_relationship` text is checked for a substantive, correctly-directed description of the leakage mechanism.
- Your `mitigation_patch` is optionally compiled and simulated with `iverilog`/`vvp` (if available in the grading environment) to verify:
  1. It is syntactically valid Verilog.
  2. It produces identical `table_data` outputs to the original module across all 256 `(public_index, secret_key)` combinations.
  3. It does not still compute a secret-dependent memory address from `public_index` and `secret_key`.

The report content itself — not any particular phrasing, coding style, or naming convention beyond what is required above — is what determines whether your submission passes. There is no requirement to match the original module's internal implementation style; any correct, functionally equivalent, address-leak-free mitigation is acceptable.

## Deterministic outcome

Every check produces exactly one `[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>` line for each of the following requirement IDs: `FR1`, `FR2`, `FR3`, `FR4`, `SR1`, `SR2`, `SR3`. The grader exits `0` only if every check passes.