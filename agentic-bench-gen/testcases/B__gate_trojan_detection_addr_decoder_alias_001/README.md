# Address Decoder One-Hot Verification

## Overview

You are given a gate-level netlist implementing a 3-bit address decoder that
drives write-enable signals for four register banks (`bank0_we`, `bank1_we`,
`bank2_we`, `bank3_we`). The decoder takes a 3-bit address (`addr[2:0]`) and a
`write_en` control signal, and is intended to behave as a **strict one-hot
decoder**: for any given address and a write request, at most one bank
write-enable should assert.

Your task is to analyze the provided netlist and determine whether this
one-hot invariant actually holds for every legal address and every value of
`write_en`, and to produce a structured report of your findings.

## Provided Artifacts (`inputs/`)

- **`design_brief.md`** — Functional description of the decoder: port names,
  intended address-to-bank mapping, and which addresses are legal/used vs.
  don't-care.
- **`gate_library.v`** — Structural Verilog definitions of the primitive gate
  wrappers (`GATE_AND2`, `GATE_AND3`, `GATE_OR2`, `GATE_OR3`, `GATE_NOT`,
  `GATE_DFF_EN`) used to build the decoder. Compiles standalone.
- **`decoder_netlist.v`** — The gate-level netlist under test, built entirely
  from instances of the modules in `gate_library.v`. This is the design you
  must analyze.
- **`testbench_harness.v`** — A self-contained testbench that instantiates
  `decoder_netlist`, generates a clock and reset, and exhaustively drives all
  8 values of `addr` crossed with both values of `write_en` (16 total test
  vectors), printing the resulting bank write-enable values for each vector
  via `$display`.

## What You Need To Do

1. Study `design_brief.md` to understand the intended behavior and exact port
   names of `decoder_netlist`.
2. Analyze `decoder_netlist.v` (structurally, and/or by simulating it) to
   determine whether the one-hot decode invariant holds for **every** address
   0–7 combined with `write_en = 0` and `write_en = 1`.
3. If you find any address/control combination where the decode behavior
   deviates from strict one-hot (e.g., zero, or more than one, write-enable
   asserting when exactly one is expected, or vice versa), identify:
   - The exact triggering address and control-input values.
   - Which output ports assert incorrectly as a result.
   - The specific net(s) and driving gate instance(s) in the netlist
     responsible for the deviation.
4. Produce a report describing your findings in the exact JSON format
   specified below.

You are encouraged (but not required) to use `iverilog` and `vvp` to compile
and run `testbench_harness.v` against `decoder_netlist.v` and `gate_library.v`
to empirically observe the decoder's behavior across all 16 test vectors,
e.g.:

```
iverilog -g2012 -o sim inputs/testbench_harness.v inputs/decoder_netlist.v inputs/gate_library.v
vvp sim
```

You may also inspect the netlist structurally (by reading it, or with tools
such as `yosys`) to trace which gate instances drive which output nets under
which input conditions.

**Note:** The expected simulation results are not published anywhere in this
repository — they are defined by the netlist itself under the given
stimulus. Use simulation and/or structural analysis of the provided files to
derive your own findings; do not assume any particular outcome in advance.

## Output: `submission/trojan_report.json`

Your submission is a **single JSON file** at `submission/trojan_report.json`.
No other files are graded. The file must conform exactly to the following
schema (all fields required unless noted optional):

```json
{
  "design_under_test": "decoder_netlist.v",
  "trojan_present": true,
  "suspect_nets": [
    {
      "net_name": "exact net/wire identifier as it appears in decoder_netlist.v",
      "gate_instance": "exact instance name driving that net, as in decoder_netlist.v",
      "role": "trigger | payload | benign"
    }
  ],
  "trigger_condition": {
    "address": "3-character string of '0'/'1' characters, e.g. \"011\"",
    "control_inputs": {
      "write_en": "0 or 1, as a string"
    }
  },
  "affected_outputs": [
    "exact output port name(s) from decoder_netlist.v, e.g. bank0_we"
  ],
  "evidence": "free-text description of the simulation and/or structural evidence supporting your findings"
}
```

Field notes:

- `design_under_test` must be the literal string `"decoder_netlist.v"`.
- `trojan_present` is a boolean: `true` if you found a deviation from
  one-hot decoding, `false` if the decoder is fully compliant.
- `suspect_nets` should list the specific net(s)/gate instance(s) you
  believe are responsible for any deviation found. Each entry's `role` must
  be exactly one of `"trigger"`, `"payload"`, or `"benign"`. If no deviation
  is found, this may be an empty array.
- `trigger_condition.address` must be a 3-character binary string (e.g.
  `"011"`), and `control_inputs` must use the exact control-signal port
  names declared in `decoder_netlist.v` (e.g. `"write_en"`), with values as
  `"0"`/`"1"` strings.
- `affected_outputs` must contain only strings that are exact output port
  names appearing in `decoder_netlist.v` (a subset of `bank0_we`,
  `bank1_we`, `bank2_we`, `bank3_we`). If `trojan_present` is `true`, this
  list must contain at least two distinct entries.
- Your reported deviation should be scoped to the *specific* address and
  control values you found evidence for — do not make a blanket claim that
  covers all 8 addresses.
- `evidence` should briefly describe how you determined your findings
  (e.g. simulation trace observations from `vvp`, or structural gate-level
  tracing).

## Grading

An automated evaluator reads `inputs/decoder_netlist.v`,
`inputs/testbench_harness.v`, and `inputs/gate_library.v` for reference, and
grades the content of your `submission/trojan_report.json` against
independently-derived ground truth. It may optionally invoke `iverilog`/`vvp`
against `decoder_netlist.v` to replay the trigger condition you report and
confirm the affected outputs assert as you describe. Your submission file is
graded on:

- **Schema compliance** — exact conformance to the JSON structure above.
- **Detection accuracy** — correctness of `trojan_present`, `trigger_condition`,
  `affected_outputs`, and `suspect_nets` relative to the actual decoder
  behavior.
- **False-positive rate** — you must not claim anomalies at addresses/control
  combinations where the decoder actually behaves correctly.

A starter/naive `submission/trojan_report.json` is included as a placeholder;
it claims no anomaly was found and will not achieve a passing score. Replace
it with your own analysis.