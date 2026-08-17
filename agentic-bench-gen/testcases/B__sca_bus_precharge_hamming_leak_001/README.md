# Bus Switching-Activity Analysis: `precharge_bus_wrapper`

## Overview

This task asks you to analyze a small RTL module, `precharge_bus_wrapper`, which
transports an 8-bit data word across a shared bus (`dbus[7:0]`) using a
two-phase **precharge / evaluate** protocol. Many bus designs use this kind
of scheme to normalize timing and drive strength across transfers.

Your job is to study the module's behavior and its documented timing
contract, reason about how the bus's per-cycle switching activity (i.e. how
many bits toggle from one cycle to the next) relates to the value being
transported, and then produce a structured findings report describing what
you observe and how you would harden the design against unwanted
observability of that switching activity — without breaking correct data
transport.

You are **not** asked to modify or resynthesize the RTL. Your deliverable is
a single JSON report file.

## What you're given (`inputs/`)

- **`precharge_bus_wrapper.v`** — the RTL module under analysis. Ports:
  `clk`, `rst_n` (active-low, synchronous), `load` (one-cycle pulse to start
  a transfer), `data_in[7:0]` (the transported data word), `dbus[7:0]`
  (the shared, externally observable bus), and `valid` (asserted for
  exactly one cycle when `dbus` carries the fully settled result of the
  most recent transfer).
- **`fault_model.json`** — describes the kind of external observer
  (probe type, what it can and cannot see, measurement granularity) you
  should assume when reasoning about this module.
- **`design_brief.md`** — documents the module's two-phase transfer
  protocol and timing contract in plain engineering terms: which cycle
  (relative to `load` being asserted) corresponds to the precharge phase
  and which corresponds to the evaluate phase.
- **`activity_trace_template.txt`** — an optional scaffolding template
  showing a suggested column layout (cycle, load, dbus value, valid,
  transition count) if you want to record your own simulation observations
  while investigating the module. It contains no results — you fill it in
  yourself if you choose to use it.

## What you must produce

A single file at:

```
submission/vulnerability_report.json
```

This file must be a single JSON object, UTF-8 encoded, with no commentary
outside the JSON. It must contain at least the following top-level keys:

| Field | Type | Description |
|---|---|---|
| `leaking_phase` | string | Which phase of the protocol (`"precharge"` or `"evaluate"`) is the one where the observable switching activity actually depends on the transported data word. |
| `affected_nets` | array of strings | Which bus net(s) the effect applies to. Reference real net names from the RTL (e.g. `"dbus[7:0]"` or individual bit indices) — do not invent net names that don't appear in the module. |
| `leakage_metric` | string | What quantity you would measure/observe to characterize the effect (e.g. describe it in terms of bit transitions or switching counts between consecutive cycles). |
| `mitigation` | string | A concrete RTL-level technique that would decouple the bus's observable switching activity from the data value being transported, while still delivering the correct value on `dbus` during the evaluate phase. |
| `functional_equivalence_claim` | boolean or string | A statement of whether (and why) your proposed mitigation still preserves the module's functional contract — i.e. does `dbus` still end up carrying (or losslessly encoding) `data_in`, and does `valid` still pulse correctly. |
| `transfer_timing` | object | `{ "precharge_cycle_offset": <int>, "evaluate_cycle_offset": <int> }` — the cycle offsets, relative to the cycle in which `load` is asserted, at which the precharge phase and the evaluate phase occur, per the module's documented two-phase protocol. |

You may include additional optional fields (e.g. `evidence`, `notes`) to
support your findings, but the fields above are required.

## Constraints

- Do **not** modify any file under `inputs/`. Your submission is graded by
  reading those files as reference material; changes to them are not
  considered.
- Your only deliverable is `submission/vulnerability_report.json`. There is
  no RTL, code, or patch to submit — this is a written analysis task.
- The file must be valid JSON: a single top-level object, UTF-8 encoded, and
  must not contain any trailing prose, comments, or markdown fences outside
  the JSON structure itself.
- Any mitigation you describe must remain compatible with the module's
  functional contract: `dbus` must still end up presenting `data_in`'s value
  (or a value from which it is losslessly recoverable) during the evaluate
  phase, and `valid` must still pulse for exactly one cycle per completed
  transfer.

## Tooling

`iverilog` and `vvp` are available in the environment if you want to
simulate `precharge_bus_wrapper.v` yourself (e.g. to trace `dbus` and
`valid` across cycles for various `data_in` values) while forming your
conclusions. This is entirely optional and for your own investigation —
grading is based solely on the contents of your submitted JSON report.

## Starting point

A placeholder `submission/vulnerability_report.json` is already present in
the repository. It has the correct shape (all required keys present) but
contains only stub/placeholder values and does **not** reflect a real
analysis of the module. Replace its contents with your own findings before
submitting.