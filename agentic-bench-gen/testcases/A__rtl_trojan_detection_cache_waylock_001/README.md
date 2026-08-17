# RTL Security Audit: Set-Associative Cache Controller Way-Locking

## Background

You are auditing a synthesizable Verilog implementation of a small 2-way,
8-set cache controller, `cache_ctrl`, found in `inputs/cache_controller.v`.
The controller supports per-way locking: software (or a privileged agent)
can mark a specific way within a specific set as "locked," which is
intended to make that way permanently ineligible for eviction until it is
explicitly unlocked. This mechanism is meant to let sensitive resident
data (e.g. pinned lines) stay resident in the cache regardless of ordinary
traffic patterns.

Your job is to review the RTL, exercise it however you find useful, and
produce a written analysis report describing whether the documented
lock guarantee actually holds under all reachable input conditions, or
whether there exist conditions under which a locked way can still be
selected for eviction.

## Provided Artifacts (`inputs/`)

- **`cache_controller.v`** — the RTL under audit. Do not modify this file;
  your submission is a separate report, not a patch.
- **`design_brief.md`** — a functional description of the intended
  behavior: request format, hit/miss/fill flow, lock/unlock semantics,
  victim selection policy, and output timing.
- **`testbench_lock_basic.v`** — a self-checking testbench (runnable with
  `iverilog`/`vvp`) that exercises ordinary lock/unlock/hit/miss/fill
  scenarios against the RTL. It passes against the shipped design. You
  may use it as a starting point for your own experiments, extend it,
  or write entirely new testbenches/scripts of your own.

## Module Interface

```verilog
module cache_ctrl(
    input  wire       clk,
    input  wire       rst_n,
    input  wire [2:0] set_idx,
    input  wire [7:0] tag_in,
    input  wire       req_valid,
    input  wire       req_is_write,
    input  wire       secure_attr,
    input  wire       lock_way_req,
    input  wire [0:0] lock_way_sel,
    input  wire       unlock_way_req,
    input  wire [0:0] unlock_way_sel,
    output reg        hit,
    output reg  [0:0] hit_way,
    output reg  [0:0] victim_way,
    output reg  [1:0] lock_status
);
```

- `set_idx` selects one of 8 sets.
- `tag_in` and `secure_attr` accompany every request.
- `req_valid` / `req_is_write` drive a lookup or a fill.
- `lock_way_req` + `lock_way_sel` set the lock bit for the addressed way
  in the addressed set; `unlock_way_req` + `unlock_way_sel` clear it.
- `hit` / `hit_way` report the result of a lookup.
- `victim_way` reports which way (0 or 1) is selected for replacement
  when a request misses and requires a fill.
- `lock_status[1:0]` reports the current lock bits for the addressed set
  (bit *i* = way *i* locked), registered and valid one cycle after
  `set_idx` is presented.

All outputs are synchronous, Moore-style: they update on the rising edge
of `clk`, one cycle after the input event that defines them, and hold
their value until the next defining event. See `design_brief.md` for the
full functional description of intended lock/unlock/hit/miss/victim-select
behavior.

## Your Task

Determine whether the way-locking guarantee described in
`design_brief.md` — "a locked way is never chosen as the eviction
victim until it is explicitly unlocked" — actually holds for every
reachable combination of inputs, or whether some combination of
`set_idx`, `tag_in`, `secure_attr`, request timing, and lock state can
cause `victim_way` to select a way that is currently locked.

You are free to:

- Read the RTL directly.
- Extend or rewrite `testbench_lock_basic.v` and simulate with
  `iverilog` + `vvp`.
- Use `yosys` for structural analysis if helpful.
- Reason about the design by hand.

There is no requirement to use any particular tool; use whatever
combination of static reading and simulation gets you to a well-supported
conclusion.

## Deliverable

Produce a single JSON file at:

```
submission/trojan_report.json
```

matching this schema:

```json
{
  "candidates": [
    {
      "location": "string naming the implicated RTL signal/line/region",
      "confidence": 0.0,
      "rationale": "string explaining the mechanism"
    }
  ],
  "summary": "string summarizing overall findings",
  "tool_evidence": "string (or array of strings) describing any iverilog/vvp/yosys steps you actually performed, if any"
}
```

Requirements for a complete report:

- `candidates` must be an array. Each entry needs a `location`, a
  `confidence` in `[0, 1]`, and a `rationale`.
- At least one candidate's rationale must describe a **concrete**
  triggering condition (specific values or ranges for `set_idx`,
  `tag_in`, `secure_attr`, or lock state) that you claim causes
  incorrect victim selection — not just a generic "this code looks
  suspicious" statement.
- Your report must explicitly state whether the issue you found (if
  any) affects `hit`/`hit_way` reporting, the `lock_status` readback,
  or only the `victim_way` selection output — these are functionally
  distinct outputs and your report should be precise about scope.
- `tool_evidence` should describe what you actually ran (simulation
  commands, waveforms inspected, static analysis performed), even if
  that's "none — static read-through only."

A starter/placeholder file already exists at
`submission/trojan_report.json`. It is a stub with no real findings —
**replace it** with your own completed analysis before submitting. It
will not earn any credit as-is.

## Notes

- You are not modifying `cache_controller.v`; your output is the report
  only.
- Passing the provided testbench does not by itself establish that the
  design is free of issues — ordinary functional testing and a genuine
  security review are different activities, and your report should
  reflect whichever level of confidence your actual analysis supports.