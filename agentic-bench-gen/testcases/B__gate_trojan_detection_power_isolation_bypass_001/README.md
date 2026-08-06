# Gate-Level Trojan Detection: Secure-Domain Isolation Cell

## Background

You are given a small, fully synthesized gate-level Verilog design, `isolation_wrapper`, that
implements a power-gating isolation cell for a secure register domain. The idea behind this
kind of cell is standard practice in secure SoC design: when a secure power domain is shut
down, its state must not "leak through" to any always-on output pin. Verification engineers
are expected to confirm that this isolation contract actually holds before the design is
signed off.

Your task is to analyze the provided netlist and determine whether the isolation contract
holds for **all** possible input combinations, and to report your findings in a structured
JSON file.

## Module Under Test

Top module: `isolation_wrapper`

| Port          | Direction | Width | Description                                         |
|---------------|-----------|-------|------------------------------------------------------|
| `secure_data` | input     | 4     | Data held by the secure domain                       |
| `power_down`  | input     | 1     | 1 = secure domain is shut down                        |
| `clk`         | input     | 1     | Present for interface uniformity; unused combinationally |
| `public_out`  | output    | 4     | Always-on, externally observable output               |

### Intended contract

The design is supposed to satisfy the following functional contract for every
`(secure_data, power_down)` combination:

- When `power_down == 1`: `public_out` must equal `4'b0000`, regardless of `secure_data`.
- When `power_down == 0`: `public_out` must equal `secure_data`.

## Provided Artifacts

- `inputs/isolation_wrapper_netlist.v` — the gate-level netlist under test, built entirely
  from `AND2`, `OR2`, and `MUX2` primitive instances plus wire declarations (no `always`
  blocks, no behavioral shortcuts).
- `inputs/primitive_library.v` — the primitive cell definitions (`AND2`, `OR2`, `MUX2`) used
  by the netlist, with named ports (`a`, `b`, `sel`, `y`).
- `inputs/design_brief.md` — the design brief describing the intended purpose and behavior of
  the isolation cell.

Both Verilog files elaborate and simulate cleanly together with `iverilog -g2012` and `vvp`.
The design is small enough (5 total input bits: 4-bit `secure_data` + 1-bit `power_down`) that
its behavior can be **exhaustively enumerated** over all 32 input combinations — you do not
need to guess at corner cases, you can check every one.

## Your Task

Determine whether the netlist actually implements the intended contract above, for every one
of the 32 possible `(secure_data, power_down)` input combinations. You may do this:

- **Structurally**, by reading through `isolation_wrapper_netlist.v` and
  `primitive_library.v` and tracing how each output bit of `public_out` is driven, gate by
  gate; and/or
- **Dynamically**, by writing your own small testbench and exhaustively simulating the
  netlist with `iverilog` + `vvp` across all 32 input vectors and comparing against the
  contract.

A combination of both approaches is recommended: simulation is good for catching a
discrepancy, and structural tracing is necessary to correctly identify *which* gate(s) and
net(s) are responsible for it.

If you find that the contract is violated for some input combination(s), you should be able
to point to:

1. Which specific bit(s) of `public_out` are affected.
2. Which specific gate instance(s) and/or net(s) in the netlist are responsible for the
   incorrect behavior.
3. The specific input assignment (values of `secure_data` and `power_down`) under which the
   violation is observed.

If you find no violation, your report should reflect that instead.

## What To Submit

Write your findings to `submission/trojan_report.json`. This is the **only** file that is
graded — you do not need to (and should not) modify anything under `inputs/`.

The file must be valid JSON with **exactly** these six top-level fields:

```json
{
  "trojan_present": true,
  "confidence": 0.95,
  "suspect_nodes": ["<gate instance or net name from isolation_wrapper_netlist.v>"],
  "affected_outputs": ["public_out[0]"],
  "violating_condition": "<short description of the input assignment that triggers the violation>",
  "analysis_summary": "<free-text summary of your analysis>"
}
```

Field requirements:

- **`trojan_present`** (`boolean`): `true` if you determine the netlist violates the isolation
  contract for at least one input combination, `false` otherwise.
- **`confidence`** (`float`, `0.0`–`1.0`): your confidence in the classification above.
- **`suspect_nodes`** (`array of strings`): instance or net names, **copied exactly** from
  `inputs/isolation_wrapper_netlist.v` (case-sensitive), that you believe are responsible for
  any violation. Leave empty if you find no violation.
- **`affected_outputs`** (`array of strings`): which bit(s) of `public_out` are actually
  compromised, using the exact naming convention `"public_out[N]"` (e.g. `"public_out[0]"`).
  Only list bits you can actually demonstrate are affected — do not pad this list with bits
  that behave correctly, since precision matters here as much as recall.
- **`violating_condition`** (`string`): a short, concrete description of the input assignment
  under which the contract fails (e.g. naming specific values for `power_down` and specific
  bits of `secure_data`), not a vague generality.
- **`analysis_summary`** (`string`): a short free-text summary of how you reached your
  conclusion.

## Starter Submission

A placeholder file is already checked in at `submission/trojan_report.json`. It currently
reports no findings at all (`trojan_present: false`, empty `suspect_nodes` and
`affected_outputs`). This is **not** a real analysis — it is only there to show you the
expected file location and JSON shape. You are expected to replace its contents with your own
findings after actually analyzing the netlist; the placeholder will not earn credit on its
own.

## Tips

- Remember that `clk` is present only for port-list uniformity — the logic here is purely
  combinational, so you do not need to worry about clock edges when reasoning about or
  simulating the design.
- Exhaustive enumeration of 32 input vectors is cheap; don't rely on spot-checking a few
  "obvious" cases only.
- Be precise about which bits of `public_out` are actually affected — a report that
  over-generalizes (e.g. claiming all four output bits are compromised when only one truly
  is) is considered less correct than one that pinpoints the exact affected bit(s).
- Instance/net names you cite in `suspect_nodes` are checked against the actual names declared
  in `inputs/isolation_wrapper_netlist.v`, so copy them exactly as they appear there.