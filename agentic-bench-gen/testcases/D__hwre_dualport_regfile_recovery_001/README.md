# Recover a Dual-Read Register File and Collision Behavior

## Task

You have been handed the remnants of a small storage block that was
flattened during synthesis: a gate-level netlist and a thin obfuscated
RTL wrapper around it. The original word-level design intent — how many
entries it has, how writes and reads relate in time, and what happens
when a read targets the same address as a write on the same clock edge
— was lost when the design was expanded into primitive gates and had its
internal signals renamed.

Your job is to **reverse-engineer the exact input/output timing behavior**
of this block and re-express it as clean, word-level, synthesizable
Verilog: a 4-entry by 8-bit storage array with one synchronous write port
and two independent, fully combinational read ports.

You do not need to match the gate-level structure. You need to match its
**observable behavior**, cycle for cycle, under simulation.

## Input artifacts (do not edit)

All files under `inputs/` are read-only reference material. Do not modify
them — the evaluator reads them directly to build its reference and test
harness.

- `inputs/design_brief.md` — plain-language functional description of the
  block: what it is, how it's used, and its observed read/write behavior.
- `inputs/gate_netlist.v` — the flattened gate-level netlist (flip-flops,
  address decoders, and multiplexer trees built from primitive gates).
- `inputs/obfuscated_wrapper.v` — a thin wrapper instantiating the gate
  netlist with meaningless internal signal names, representing how the
  block appears embedded in a larger flattened design.

Study these to infer the exact write, reset, and read/write collision
semantics. The gate netlist is provided for structural inspection and to
let you simulate it yourself as a behavioral oracle if useful, but your
graded answer must be original word-level RTL, not a copy or thin
rewrap of the netlist.

## Required output

Submit **exactly one file**: `submission/recovered_rtl.v`

It must define **exactly one module** named `reg_file_recovered` with
this exact port list:

```
module reg_file_recovered (
    input        clk,
    input        rst,      // synchronous, active-high
    input        we,       // write enable, active-high
    input  [1:0] waddr,    // write address, 4 entries: 0..3
    input  [7:0] wdata,    // write data
    input  [1:0] raddr0,   // read port 0 address, combinational
    input  [1:0] raddr1,   // read port 1 address, combinational
    output [7:0] rdata0,   // read port 0 data
    output [7:0] rdata1    // read port 1 data
);
```

## Timing contract (summary — this is what gets graded)

- **Write:** synchronous. On each rising edge of `clk` where `rst=0` and
  `we=1`, the 8-bit entry at `waddr` is updated to `wdata`. Exactly one
  entry changes per enabled edge.
- **Reset:** synchronous, active-high. While `rst=1` at a rising edge,
  all four entries are cleared to `8'h00` on that edge (this takes
  priority over `we`; no write occurs while `rst=1`). The cleared values
  become visible starting immediately after that edge.
- **Reads:** purely combinational, zero cycles of latency. `rdata0` and
  `rdata1` always reflect the *current* contents of the entries addressed
  by `raddr0` and `raddr1`, and update immediately (same delta cycle)
  whenever the addressed entry's value changes or the address itself
  changes — no additional clock edge is ever needed to observe a change.
- **Write-forwarding / collision rule:** if a read address equals the
  write address on a cycle where a write commits, that read port shows
  the *old* value up to and including the moment just before the edge,
  and the *newly written* value immediately after that same edge — with
  no extra one-cycle delay. This falls out naturally from clocked storage
  plus purely combinational reads; do not add a separate bypass
  multiplexer for this case.
- The two read ports are fully independent of each other.

Internal storage must be modeled as explicit clocked registers (e.g. a
`reg [7:0]` array of 4 entries updated in an `always @(posedge clk)`
block) — not latches, not combinational feedback. Reads must be
implemented as plain combinational multiplexers (`assign` or
`always @(*)`) with no extra pipeline stage. Your file must be
self-contained (no dependency on external modules) and free of any
`$stop`/`$finish` or other non-synthesizable simulation-only constructs.

## How you will be graded

Grading is **behavioral simulation**, not a source-code diff. Your
submission is compiled with `iverilog` alongside a hidden testbench and
an independently-authored reference design (built only from the public
port list and timing contract above), then simulated with `vvp`. Both
designs are driven with the same randomized sequences of writes, reads,
collisions, and resets, and their `rdata0`/`rdata1` waveforms are
compared cycle by cycle. `yosys` may also be used for structural
sanity checks.

The metrics reported are:

- **cycle_accurate_match_rate** — fraction of simulated clock cycles,
  across all randomized test sequences, where your `rdata0`/`rdata1`
  exactly match the reference design.
- **word_recovery_rate** — fraction of the four register entries for
  which targeted single-address write-then-read tests confirm correct
  read/write mapping.
- **structural_match_accuracy** — a static check confirming you used
  explicit clocked storage and combinational read muxing (no latches,
  no combinational feedback loops); this can only flag disallowed
  constructs, it never grants a pass on its own.
- **functional_equivalence** — pass/fail per test scenario (basic
  read/write, collision, reset-then-read, dual-port independence)
  indicating full behavioral equivalence with the reference across the
  randomized regression.

A stub that ties `rdata0`/`rdata1` to zero or passes inputs straight
through will compile but fail every behavioral metric — that is the
baseline currently sitting in `submission/recovered_rtl.v`, and it is
what you are expected to replace.