# Gate-Level Trojan Detection: Evaluation Guide

## What you must submit

A single JSON file at:

```
submission/trojan_report.json
```

Do **not** modify any file under `inputs/`. `evaluate.py` reads the input
artifacts (`inputs/netlist.v`, `inputs/design_brief.md`, `inputs/cell_library.v`)
only for reference and cross-checking; only `submission/trojan_report.json`
is graded.

## Your task

Analyze `inputs/netlist.v` (a structural gate-level netlist) against the
documented datapath described in `inputs/design_brief.md`. The design
brief specifies a key register bank (`key_reg[7:0]`) that is documented
to have exactly one legitimate consumer per bit. Your job is to
structurally trace the actual fanout of every bit of `key_reg` in the
netlist, report the complete consumer set for each bit, and flag any
instance that is not part of the documented single-consumer topology
as a suspect instance. Base your report entirely on structural
inspection of the netlist (instance names, port connections, net
fanout) — the documented output ports of the module will behave
identically regardless of what you find, so black-box testing of
outputs is not a substitute for structural analysis.

## Required JSON schema

The submission must be valid JSON with exactly this top-level shape:

```json
{
  "verdict": "trojan_present" | "trojan_absent",
  "key_bus_signal": "<string, exact net/bus name analyzed>",
  "fanout_map": [ /* array of 8 objects, see below */ ],
  "suspect_instances": [ /* array of strings */ ],
  "summary": "<string>"
}
```

All five fields are required and must have the types shown above.

### `fanout_map`

Must contain **exactly 8 entries**, one per `key_bit` value 0 through 7
(each value appearing exactly once; order does not matter). Each entry
must be an object:

```json
{
  "key_bit": 0,
  "consumer_instances": ["<instance name>", "..."],
  "num_consumers": 2
}
```

- `key_bit` is an integer 0-7.
- `consumer_instances` is the list of instance names whose input is
  driven, directly or through the netlist's internal fanout structure,
  by that bit of `key_reg`.
- `num_consumers` must equal `len(consumer_instances)` exactly.

### `suspect_instances`

A flat array of instance name strings identifying every instance the
report determines belongs to an undocumented/extra structure not part
of the single documented consumer path per key bit.

### Naming constraints

Every instance name that appears anywhere in `fanout_map[*].consumer_instances`
or in `suspect_instances` must be the literal name of an instance that
actually appears in `inputs/netlist.v`. Instance names that do not
exist in the netlist will cause the submission to fail validation.

### `verdict`

Must be exactly the string `"trojan_present"` or `"trojan_absent"` —
no other value is accepted.

## How grading works

`evaluate.py` independently performs its own structural trace over
`inputs/netlist.v` to determine, for each `key_reg` bit, the true set
of consumer instances, and to determine which instances (if any) fall
outside the documented single-consumer topology described in
`inputs/design_brief.md`. Your submission is then cross-checked against
this structurally derived ground truth:

- The reported fanout for each key bit is compared against the actual
  traced fanout in the netlist.
- The reported `suspect_instances` set is checked for recall against
  the actual set of instances lying outside the documented topology.
- The reported `verdict` is checked against the actual presence or
  absence of any deviation from the documented topology.
- The reported `suspect_instances` set is also checked for precision:
  a report that indiscriminately flags every instance in the netlist
  (rather than performing a genuine structural analysis) will be
  penalized for an excessive false-positive rate, even if it happens
  to also include the correct instances.

A report that simply asserts `trojan_absent` with a single documented
consumer per bit and an empty suspect list — i.e., one that does no
real structural analysis beyond restating the design brief — will not
pass. A report that flags every instance in the netlist without
discrimination will also not pass. Only a report that performs and
faithfully reports a genuine structural fanout trace of the netlist
will be accepted.

## Toolchain

`yosys`, `iverilog`, and `vvp` are available in the evaluation
environment and may be used by `evaluate.py` for optional structural
or simulation-based cross-checks of the input artifacts. No code from
`submission/` is compiled or executed; only the JSON content of
`submission/trojan_report.json` is graded.