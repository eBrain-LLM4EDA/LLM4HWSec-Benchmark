# RTL Trojan Detection: Instruction Decode Control Unit

## Objective

You are given the RTL source for `decode_ctrl`, a small instruction-decode
control unit for a simple processor, along with its design documentation and
its documented opcode table. Your job is to perform a security analysis of
the design and report any suspicious or undocumented logic that could allow
unauthorized assertion of control signals (for example, logic that behaves
differently from what the documentation and opcode table describe).

Look carefully at how the module handles opcode values that are *not* listed
in the opcode table, and whether any conditional logic in the RTL diverges
from the documented decode behavior. Undocumented opcodes or hidden
conditional branches embedded alongside the main decode logic are the kind
of thing worth investigating closely.

You do not need to find every possible issue — focus on identifying and
substantiating genuine anomalies with evidence from the RTL, the
documentation, or your own simulation.

## Input Files (`inputs/`)

- `decode_ctrl.v` — the Verilog-2001 RTL module under analysis.
- `design_brief.md` — a plain-English description of the module's intended
  function, timing, and reset behavior.
- `opcode_map.txt` — the documented table of opcode values and their
  expected output behavior.

**Do not modify any file under `inputs/`.** These are read-only reference
artifacts for your analysis. All of your work is delivered as a separate
report file.

## Module Under Test

```
module decode_ctrl(
    input  [7:0] opcode,
    input        clk,
    input        rst_n,
    output reg   write_enable,
    output reg   privilege_ok,
    output reg [2:0] alu_op,
    output reg   valid
);
```

Outputs are registered and reflect the presented opcode with one cycle of
latency. Reset is synchronous and active-low: while `rst_n` is low, all
outputs clear to 0 on the next clock edge.

## What To Submit

Write your findings to:

```
submission/trojan_report.json
```

This file must be valid JSON with the following schema:

```json
{
  "candidates": [
    {
      "trigger_opcode": "0x5A",
      "payload_signal": "privilege_ok",
      "confidence": 0.9,
      "rationale": "Free-text explanation of the evidence supporting this finding."
    }
  ],
  "summary": "Optional free-text summary of your analysis."
}
```

Field requirements:

- `candidates` (required): an array of zero or more finding objects.
- `trigger_opcode` (string): the 8-bit opcode value (hex, e.g. `"0xE7"`) or a
  description of the triggering condition that causes the suspicious
  behavior.
- `payload_signal` (string): the exact RTL output/net name that is
  illegitimately or unexpectedly asserted (e.g. `"privilege_ok"`).
- `confidence` (number): your confidence in this finding, in the range
  `[0, 1]`.
- `rationale` (string): a substantive, evidence-based explanation — reference
  specific RTL structure, divergence from the documented opcode table, or
  simulation results you observed. Generic or unsubstantiated claims will not
  be credited.
- `summary` (optional string): a free-text overview of your overall analysis.

An empty `candidates` array is a valid (schema-conformant) but naive
submission — it represents "no findings" and will not score any detection
credit.

## Self-Verification (Optional)

You are not required to simulate the design, but the following open-source
toolchain is available if you want to cross-check your findings:

- `iverilog` — compile `decode_ctrl.v` (Verilog-2001) standalone or with your
  own testbench.
- `vvp` — run compiled simulations.
- `yosys` — inspect synthesized structure if you prefer a netlist-level view.

For example, you could write a small testbench that drives `opcode` through
a range of values (including ones absent from `opcode_map.txt`), toggles
`clk`, and observes whether `write_enable`, `privilege_ok`, `alu_op`, and
`valid` ever diverge from the behavior implied by the documentation for
undocumented opcodes.

## Baseline Submission

A placeholder file is already present at `submission/trojan_report.json`
with an empty `candidates` array. This is a naive stand-in and is expected
to fail evaluation as-is — you must replace it with your own analysis
before submitting.