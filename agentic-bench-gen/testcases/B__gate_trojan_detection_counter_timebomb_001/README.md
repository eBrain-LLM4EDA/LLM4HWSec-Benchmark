# Gate-Level Trojan Detection: Counter Time-Bomb Localization

## Objective

You are given a gate-level Verilog netlist for a small synchronous datapath
(an 8-bit accumulator) along with its documented functional specification.
Your job is to analyze every net/register/gate of interest in the netlist,
classify its functional role, and report whether the implementation deviates
from its documented specification.

For each node of interest you should determine which of the following roles
it plays:

- `counter` — a state element that is not part of the documented datapath
  and appears to free-run or accumulate independently of the primary
  function.
- `comparator` — decision logic that evaluates a condition (e.g. a terminal
  count or equality check) over one or more signals.
- `payload` — a gate that alters or corrupts a primary output or datapath
  signal based on the output of trigger/decision logic.
- `datapath` — a node that is part of the documented, intended function of
  the module (e.g. the adder/accumulator chain).
- `io` — a primary input or output port of the module.

## Provided Files

- `inputs/netlist.v` — the gate-level netlist under analysis. Read the
  module header carefully; the module name here is what you must report as
  `design_name`.
- `inputs/design_brief.md` — the documented functional specification for
  the module (what it is *supposed* to do).
- `inputs/baseline_testbench.v` — a testbench you may use to simulate the
  netlist for your own exploration. It is not graded and is provided purely
  as an aid.

## Optional Self-Check Simulation

You may use the standard open-source toolchain to simulate the netlist and
observe its behavior over time. From the root of this task directory:

```
iverilog -g2012 -o sim.out inputs/netlist.v inputs/baseline_testbench.v
vvp sim.out
```

This will drive the module with a short stimulus sequence and print the
primary output and selected internal signals via `$display`/`$monitor`.
Note that the testbench run is intentionally short — you should not rely
solely on simulation traces to reach your conclusions. Consider tracing the
structural connectivity of the netlist (fan-in/fan-out of each register and
gate) to understand what each signal actually does over a longer horizon
than the testbench covers.

Simulation is entirely optional and is not scored. Only your submitted
report is graded.

## What You Must Submit

Create (overwrite) the file:

```
submission/trojan_report.json
```

This is the **only** file that is graded. Do not modify any files under
`inputs/`. A placeholder/starter version of this file is already present in
`submission/trojan_report.json` — you must replace its contents with your
own analysis before submitting.

### Required JSON Schema

The file must be valid UTF-8 JSON with exactly the following top-level
fields:

```json
{
  "design_name": "string",
  "is_trojan_detected": true,
  "suspect_nodes": ["net_name_1", "net_name_2"],
  "stage_labels": {
    "net_name_1": "counter",
    "net_name_2": "comparator"
  },
  "summary": "A description of your analysis method, at least 20 characters long."
}
```

Field-by-field requirements:

- **`design_name`** (string, required): must exactly match the module name
  declared at the top of `inputs/netlist.v` (e.g. `module <this_name>
  (...);`). Copy it verbatim — do not paraphrase or add/remove
  underscores.
- **`is_trojan_detected`** (boolean, required): your overall verdict on
  whether the netlist contains logic that deviates from
  `inputs/design_brief.md`.
- **`suspect_nodes`** (array of strings, required): the exact net, register,
  or gate-output names (as they literally appear in `inputs/netlist.v`) that
  you believe are suspicious, undocumented, or responsible for any
  deviation from the documented spec. Every entry here must be a real
  identifier that appears in `inputs/netlist.v` — invented or
  misspelled names will not be credited.
- **`stage_labels`** (object, required): a mapping from net/wire/register
  name to exactly one of the five role strings: `"counter"`,
  `"comparator"`, `"payload"`, `"datapath"`, or `"io"`. As with
  `suspect_nodes`, every key must be a real identifier that appears in
  `inputs/netlist.v`. You are not required to label every single net in
  the design, but you should label all nodes relevant to your findings,
  including the legitimate documented datapath nodes (labeled
  `"datapath"` or `"io"` as appropriate) so that your report distinguishes
  genuine functional logic from anything anomalous.
- **`summary`** (string, required, at least 20 characters): a short
  free-text description of the method you used to reach your conclusions
  (e.g. what you inspected, what you simulated, what led to your verdict).

### Example Skeleton (illustrative structure only — not a real analysis)

```json
{
  "design_name": "example_module",
  "is_trojan_detected": false,
  "suspect_nodes": [],
  "stage_labels": {
    "clk": "io",
    "rst": "io",
    "out": "io"
  },
  "summary": "Reviewed port list and register update logic; found no anomalies."
}
```

Do not submit this example as-is — it is only meant to show the required
JSON shape. Your real report must reflect your own analysis of the actual
netlist.

## Grading

Your submission is graded automatically and entirely from the content of
`submission/trojan_report.json`:

1. The file must parse as valid JSON and satisfy the schema described
   above (field presence, correct types, valid net names, non-empty
   `summary`).
2. Your reported verdict and node classifications are compared against a
   hidden ground-truth annotation of the netlist that is **not** shipped
   to you. This ground truth identifies which nodes (if any) constitute
   undocumented/anomalous logic versus legitimate documented datapath
   logic.
3. Your score reflects both how much of the true anomalous logic you
   correctly identified and labeled, and how well you avoided mislabeling
   legitimate documented datapath logic as anomalous.

No other files are read for grading besides `submission/trojan_report.json`.
Files under `inputs/` are reference material only and are never modified or
graded.