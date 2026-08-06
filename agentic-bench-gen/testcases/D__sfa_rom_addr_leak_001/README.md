# Engineering Review: Substitution-Table Lookup Module (`subst_lookup`)

## Objective

You are performing an internal design review of a small RTL block, `subst_lookup`, that implements a keyed substitution/permutation lookup used inside a cipher datapath. Your job is to:

1. Analyze the module's internal signals and determine, precisely, which signals are fully determined functions of the module's inputs (`public_index`, `secret_key`), and characterize that functional relationship.
2. Use the accompanying address-trace log to recover the fixed secret key value that was in effect while the traces were captured, and demonstrate that your recovered value is consistent with every entry in the log.
3. Propose a concrete RTL modification to the lookup strategy that removes the dependency of any externally observable address/index signal on `secret_key`, while preserving the module's original input/output behavior (`table_data` must still be computed correctly for every `(public_index, secret_key)` pair).

This is a standard hardware design-review exercise: characterize signal dependencies, back out a hidden parameter from trace data, and propose a functionally-equivalent RTL restructuring.

## Input Artifacts

All inputs are under `inputs/` and must **not** be modified. You only read them for reference.

- `inputs/subst_lookup.v` — the RTL module under review.
- `inputs/address_traces.json` — a log of `{public_index, observed_rom_addr}` pairs captured over multiple clock cycles, all under one fixed (but unstated) `secret_key` value.
- `inputs/design_brief.md` — a short functional description of the module's intended behavior and timing.

## Module Interface

```
module subst_lookup(
    input  wire       clk,
    input  wire       rst_n,
    input  wire [3:0] public_index,
    input  wire [3:0] secret_key,
    output wire [3:0] table_data
);
```

- `clk` — system clock.
- `rst_n` — active-low synchronous reset.
- `public_index` — 4-bit input, known/observable to anyone inspecting the module's operation.
- `secret_key` — 4-bit input that is not directly observable by an external reviewer.
- `table_data` — 4-bit output: the resolved lookup value. This is the module's only intended output.

Internally, the module combines `public_index` and `secret_key` into an internal index, registers that index on the rising edge of `clk`, and uses the registered value to address a small internal lookup table (ROM) whose output drives `table_data`.

## What To Produce

Your deliverable is a single file: **`submission/vulnerability_report.json`**.

Do not submit any other files. Do not edit anything under `inputs/`. Only `submission/vulnerability_report.json` is read and graded.

The file must be valid JSON with exactly these top-level fields:

```json
{
  "leaking_signals": [ "string", ... ],
  "non_leaking_signals": [ "string", ... ],
  "recovered_secret_key": 0,
  "leakage_relationship": "string",
  "mitigation_patch": "string",
  "mitigation_rationale": "string"
}
```

Field definitions:

- **`leaking_signals`** — exact RTL signal names (as declared/used in `subst_lookup.v`) that are fully determined by, and reveal information about, `secret_key` when observed externally (e.g. on an address bus or via a register probe).
- **`non_leaking_signals`** — exact RTL signal names that do not carry secret-dependent information observable in this way.
- **`recovered_secret_key`** — an integer in `[0, 15]`: the value of `secret_key` that you determine was fixed during capture of `inputs/address_traces.json`, derived from the trace data. This value must be consistent with **every** entry in the trace log, not just most of them.
- **`leakage_relationship`** — a precise mathematical/logical statement describing how the leaking signal(s) relate to `public_index` and `secret_key` (e.g. of the form `signal = public_index OP secret_key`).
- **`mitigation_patch`** — a Verilog RTL snippet or full replacement module that implements the same `table_data` behavior for every `(public_index, secret_key)` pair, but restructures the lookup so that no signal computed from `secret_key` (combined with `public_index`) is ever used to directly index/select a memory location. Consider a full-table-scan or bit-sliced boolean evaluation strategy as an alternative to indexed addressing.
- **`mitigation_rationale`** — an explanation of why your proposed patch removes the dependency identified above while preserving the module's original functional correctness.

## Notes on Tooling

`iverilog`, `vvp`, and `yosys` are available in the environment if you want to simulate `inputs/subst_lookup.v`, experiment with trace generation, or check that your `mitigation_patch` elaborates and simulates correctly. Their use is optional — grading is based solely on the content of `submission/vulnerability_report.json`.

## Getting Started

A placeholder `submission/vulnerability_report.json` is already present in the repository with empty/placeholder values. It will not pass review. Replace its contents with your own analysis before submitting.