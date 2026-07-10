# Fault-Injection Bypass Analysis: Secure-Boot Comparator

## Overview

You are given a small RTL module, `secure_boot_check.v`, that implements a
secure-boot signature-verification pipeline: it loads a signature over
several clock cycles, compares it against an expected value, and asserts a
`boot_allowed` output if the comparison succeeds. A companion fault model
document (`fault_model.md`) describes the fault-injection capability an
attacker is assumed to have against this design during boot.

Your task is to statically analyze the RTL together with the fault model
and produce a structured vulnerability report describing:

1. Every flip-flop / register in the design.
2. Every FSM state the design's control logic can be in.
3. The specific register(s)/control signal(s) whose fault would let an
   attacker bypass authentication.
4. Hardening recommendations for those specific signals.

You do **not** need to run simulation to complete this task — careful
reading of the Verilog source and the fault model is sufficient — but the
toolchain (`iverilog`, `vvp`, `yosys`) is available in the environment if
you want to double-check your reasoning (e.g., elaborate the design, dump
its state transitions, or hand-write a small testbench that forces a
register value and observes `boot_allowed`).

## Input Artifacts (read-only)

Located under `inputs/`:

- **`secure_boot_check.v`** — the RTL module under analysis. Self-contained
  Verilog-2001, simulatable with `iverilog -g2012` / `vvp` without any
  external IP.
- **`fault_model.md`** — describes the fault model you must reason about:
  a single-bit stuck-at/transient fault injected into exactly one
  flip-flop per simulated run, active for exactly one clock cycle, with
  an attacker who has physical/EM/clock-glitch access during the boot
  sequence.
- **`design_brief.md`** — a plain-language description of the module's
  intended behavior, FSM stages, and I/O, to help you interpret the RTL.

**Do not modify any file under `inputs/`.** Your analysis must be based on
these artifacts exactly as shipped.

## What You Submit

Exactly one file:

```
submission/vulnerability_report.json
```

A naive placeholder file already exists at that path — replace its
contents entirely with your real analysis. Nothing else you submit is
graded.

The report must be reproducible from static inspection of the RTL plus the
fault model. You may optionally use `iverilog`/`vvp`/`yosys` to validate
claims (e.g., write a small testbench that forces a candidate register to
a specific value at a specific cycle and confirms the effect on
`boot_allowed`), but this is not required to produce a complete report.

## Required JSON Schema

`vulnerability_report.json` must be a single JSON object (UTF-8) with
**exactly** these top-level keys (extra keys are ignored, but all four of
these are required):

```json
{
  "analyzed_registers": [
    {
      "name": "string — must exactly match a register identifier in secure_boot_check.v",
      "width": 1,
      "line": 42
    }
  ],
  "fsm_states": [
    "string — must exactly match a state parameter/localparam name in secure_boot_check.v"
  ],
  "critical_nodes": [
    {
      "signal": "string — register/signal name from secure_boot_check.v",
      "reason": "string — why this signal is critical",
      "exploit_scenario": "string — describes the fault-injection bypass"
    }
  ],
  "hardening_recommendations": [
    {
      "target_signal": "string — must match a signal named in critical_nodes",
      "technique": "string — the mitigation technique proposed",
      "rationale": "string — why this technique addresses the risk"
    }
  ]
}
```

Field-by-field requirements:

- **`analyzed_registers`**: one entry per flip-flop declared with `reg` and
  clocked in an `always @(posedge clk)` block in `secure_boot_check.v`.
  Each entry needs:
  - `name`: the exact register identifier as it appears in the RTL.
  - `width`: integer bit-width of the register as declared.
  - `line`: the line number (or `[start, end]` array of line numbers)
    in `secure_boot_check.v` where the register is assigned/clocked.
- **`fsm_states`**: an array of strings, one per distinct state
  encoding/parameter defined for the module's state machine. Names must
  match the parameter/localparam identifiers declared in the RTL exactly.
- **`critical_nodes`**: the register(s)/control signal(s) that, if
  faulted per the fault model, allow the design to report authentication
  success without ever completing a valid comparison. Each entry needs
  a `signal` name (must appear literally in the RTL), a `reason`
  explaining why it is critical, and an `exploit_scenario` describing the
  concrete fault sequence that causes a bypass.
- **`hardening_recommendations`**: concrete mitigations, one or more per
  critical node, each naming the exact `target_signal` it addresses, the
  proposed `technique`, and a `rationale` for why it prevents a
  single-bit fault from silently altering the authentication decision.

## Constraints

- Do not edit `inputs/secure_boot_check.v`, `inputs/fault_model.md`, or
  `inputs/design_brief.md`. Only `submission/vulnerability_report.json`
  is graded.
- `submission/vulnerability_report.json` must be valid JSON containing
  exactly the four required top-level keys described above.
- Every register/state/signal name you reference anywhere in the report
  must be an exact, case-sensitive substring found in
  `inputs/secure_boot_check.v`. Names that don't appear in the RTL will
  not be credited.
- All numeric fields (`width`, `line`) must be JSON integers (or, for
  `line`, an array of two integers `[start, end]`).
- The RTL is plain synthesizable Verilog-2001; no external IP or
  proprietary primitives are used, so it elaborates and simulates cleanly
  with `iverilog -g2012` and `vvp`.

## Suggested Workflow

1. Read `design_brief.md` for context on the module's intended function
   and stage names.
2. Read `fault_model.md` to understand the fault capability you're
   reasoning against.
3. Read `secure_boot_check.v` line by line:
   - List every `reg`-declared, clocked flip-flop → `analyzed_registers`.
   - List every state parameter/localparam → `fsm_states`.
   - Trace which register(s) directly gate the `boot_allowed` (or
     equivalent) output, and determine what a single-bit fault on each
     would do to the authentication outcome.
4. (Optional) Use `iverilog`/`vvp` to write a scratch testbench that
   forces a candidate register to a chosen value for one clock cycle and
   observes whether `boot_allowed` asserts without a genuine signature
   match. Use `yosys` if you want to inspect the synthesized structure.
5. Write up `critical_nodes` describing the exact bypass mechanism.
6. Write `hardening_recommendations` proposing concrete, targeted
   mitigations (e.g., redundant/complementary checks, majority voting,
   checksum-based state validation) for each critical node — generic or
   unrelated advice will not be credited.
7. Save your completed report to `submission/vulnerability_report.json`,
   replacing the placeholder file.