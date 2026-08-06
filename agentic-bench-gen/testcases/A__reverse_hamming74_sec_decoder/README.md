# Recover a Hamming(7,4) Single-Error-Correcting Decoder

## Background

You have been handed a flattened, obfuscated gate-level netlist extracted from
an undocumented storage controller: `inputs/flattened_netlist.v`. It describes
a single combinational module that takes a 7-bit codeword and produces:

- a recovered 4-bit data word,
- a corrected 7-bit codeword,
- an error-detected flag.

All internal signal names in the netlist have been replaced with generic
labels (`n1`, `n2`, `_T_3`, ...) and the logic has been flattened, so no
parity-position or syndrome naming survives. Your job is to analyze the
netlist's behavior (by reading its structure and/or simulating it), recover
the intended word-level function, and re-implement it as clean, readable RTL.

See `inputs/design_brief.md` for functional context and hints on how such
decoders are typically structured, and `inputs/flattened_netlist.v` as the
artifact you must reverse engineer. Nothing in this repository states the
exact bit-position convention or syndrome ordering used by this particular
design — that is precisely what you need to determine.

## Your task

Write a single, self-contained Verilog file at:

```
submission/recovered_rtl.v
```

It must define **exactly one** module with this literal declaration:

```verilog
module recovered_decoder (
  input  [6:0] codeword,
  output [3:0] data,
  output [6:0] corrected_codeword,
  output       error_detected
);
```

### Behavioral requirement

For every one of the 128 possible values of `codeword` (`7'b0000000` through
`7'b1111111`), your module's `data`, `corrected_codeword`, and
`error_detected` outputs must exactly match the behavior of the reference
netlist when both are driven with the same input value and allowed to settle.

Concretely:

- If `codeword` is a valid (error-free) codeword of the underlying code,
  `error_detected` must be 0 and `corrected_codeword` must equal `codeword`
  unchanged.
- If `codeword` contains exactly one bit flipped relative to a valid
  codeword, `error_detected` must be 1 and `corrected_codeword` must equal
  the corresponding valid codeword (the erroneous bit flipped back).
- `data[3:0]` must be extracted from the corrected codeword using whatever
  bit-position convention the reference netlist actually implements — this
  is exactly what you must recover from the netlist.

This module is **purely combinational**: no clocks, no registers, no
`always @(posedge ...)` blocks, no internal state. Every output must be a
function of the current value of `codeword` alone, settling within the same
delta cycle as any input change.

## Constraints

- The submission must be a single self-contained Verilog-2001 (or
  SystemVerilog) file with no dependence on external libraries or
  proprietary IP.
- The submission must **not** instantiate or reference the original
  flattened netlist module; it must be an independently written,
  human-readable RTL description.
- Internal signal names inside your module are entirely up to you — only
  the observable outputs at the pinned interface are graded.
- The module must be purely combinational, as described above.
- The file must compile cleanly under `iverilog` with no errors, and must
  contain exactly one module named `recovered_decoder` with the exact port
  list given above.

## How grading works

Grading is **behavioral**, not textual. The evaluator will:

1. Compile `inputs/flattened_netlist.v` (wrapped as the reference) together
   with your `submission/recovered_rtl.v` and a generated testbench, using
   `iverilog`.
2. Run the simulation with `vvp`.
3. Drive all 128 values of `codeword` (`7'b0000000` through `7'b1111111`)
   sequentially, with a `#5` settling delay after each value is applied.
4. At each step, sample `data`, `corrected_codeword`, and `error_detected`
   from both the reference and your submission and compare them.

**PASS** requires all three output signals to match exactly across all
128 codewords. A single mismatch on any signal, for any codeword, causes
**FAIL**. A submission that fails to compile under `iverilog` is graded
FAIL with a compile-error diagnostic.

Note: this repository does not publish the expected output values for any
codeword. The correct behavior is fully determined by the algorithm
implemented in `inputs/flattened_netlist.v`, and the evaluator computes and
checks it by simulation — your job is to analyze and reproduce that
behavior, not to match a table of published answers.

## What's provided

- `inputs/flattened_netlist.v` — the obfuscated gate-level netlist to
  reverse engineer.
- `inputs/design_brief.md` — narrative context and general hints about how
  single-error-correcting decoders of this style are typically structured.
- `submission/recovered_rtl.v` — a placeholder starter file (currently an
  intentionally wrong stub). Replace its contents with your recovered RTL
  before submitting.

## Suggested approach

1. Read through `inputs/flattened_netlist.v` to understand its combinational
   structure — look for XOR fan-in trees (candidates for syndrome/parity
   computation) versus simple pass-through or mux structures (candidates for
   data extraction and correction).
2. Simulate the netlist yourself (e.g. with `iverilog`/`vvp`) over the full
   128-value input space and build a truth table.
3. Identify which codeword bit positions behave as "parity" bits (each
   participates in exactly one syndrome XOR group with a distinct pattern)
   versus "data" bits.
4. Determine how the syndrome value maps to a bit position for correction,
   and how the corrected bits map onto `data[3:0]`.
5. Re-implement your understanding as clean, independent RTL in
   `submission/recovered_rtl.v` and verify it against the netlist yourself
   before submitting.