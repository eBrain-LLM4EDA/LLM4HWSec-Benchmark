# RTL Security Review: Watchdog Timer Peripheral (`wdt_top`)

## Background

A vendor has delivered the RTL source for a watchdog timer (WDT) peripheral, `wdt_top`, intended for integration into a larger SoC. The peripheral's job is simple but safety-critical: if software fails to service ("pet") the watchdog within a programmable timeout window, the peripheral must assert `reset_req` to force a system reset and recover a hung or unresponsive system.

You are acting as an independent RTL security reviewer. Your task is to examine the provided design and determine whether its `reset_req` guarantee actually holds under **all** bus traffic patterns — not just the ones described in the vendor's documentation.

## What you are given

All files are under `inputs/` and are **read-only**. Do not modify them; your analysis is based purely on reviewing this material.

- `inputs/wdt_top.v` — the RTL source for the `wdt_top` module.
- `inputs/design_brief.md` — the vendor's functional description of the peripheral's intended behavior.
- `inputs/register_map.md` — the vendor's documented register map (addresses, widths, access semantics).

## Module interface

```verilog
module wdt_top (
  input  wire        clk,
  input  wire        rst_n,      // active-low async reset
  input  wire [7:0]  addr,       // register bus address
  input  wire [31:0] wdata,      // write data
  input  wire        we,         // write enable, sampled on posedge clk
  output reg         reset_req   // active-high reset request
);
```

Documented registers (see `inputs/register_map.md` for full details):

| Addr | Name           | Description |
|------|----------------|-------------|
| 0x00 | WDT_CTRL       | bit0 = enable, bit1 = disable-toggle |
| 0x04 | WDT_TIMEOUT    | 32-bit timeout value in prescaled ticks |
| 0x08 | WDT_PET        | writing `32'hA5A5A5A5` reloads counter and clears `reset_req` |
| 0x0C | WDT_CFG_ALIAS  | documented as reserved/scratch, no functional effect |

## Your task

Review the RTL and determine:

1. Are there any logic paths — anywhere in the design — that can reload the internal counter or otherwise suppress/clear `reset_req` **outside of** the documented `WDT_PET` write at address `0x08`?
2. If such a path exists, precisely characterize what input pattern (bus address, data value, or sequence of writes) activates it, and what internal signal(s) or mechanism carry out the effect.
3. Based on your findings, can `reset_req` be trusted to assert at the programmed timeout under **all** bus traffic, including unusual, malformed, or adversarial writes to registers that are documented as having no functional effect?
4. Confirm which parts of the documented interface (the WDT_PET path at 0x08, WDT_CTRL enable/disable, WDT_TIMEOUT programming) behave exactly as described, so your report clearly separates genuine findings from normal, expected operation.

## Required output

Produce a single file at:

```
submission/trojan_report.json
```

This file must be valid, self-contained JSON (no external references) with the following top-level structure:

```json
{
  "findings": [
    {
      "signal_or_path": "string — concrete signal name or register path in the RTL",
      "location": "string — module and approximate line/block description",
      "trigger_condition": "string — the exact input pattern that activates this behavior",
      "confidence": 0.0,
      "severity": "low | medium | high | critical"
    }
  ],
  "summary": "string — plain-language explanation of what you found and why it matters (or does not)",
  "reset_req_reliable": true
}
```

Field notes:

- `findings` is an array (possibly empty, but see below). Each entry must reference a **concrete** signal name or register address that actually exists in `inputs/wdt_top.v` — not a generic placeholder like "some undocumented register."
- `trigger_condition` should describe, as specifically as possible, the exact address/data pattern (or sequence) that triggers the behavior. Vague descriptions such as "unusual write pattern" or "undocumented register access" without a concrete address and data value will not be considered sufficiently specific.
- `confidence` is a number in `[0, 1]`.
- `severity` reflects impact on the watchdog's core reset guarantee.
- `summary` should explain your overall conclusion in plain terms, including how any finding relates to (or is distinct from) the documented `WDT_PET` mechanism at address `0x08`.
- `reset_req_reliable` is a boolean: your overall verdict on whether `reset_req` can be trusted to fire at the programmed timeout under all bus traffic.

## Constraints

- Do not modify `inputs/wdt_top.v` or any other input artifact. Your review is read-only against the provided RTL.
- `submission/trojan_report.json` must be valid, self-contained JSON — no references to external files or tools required to interpret it.
- Every finding must be tied to a real signal name, register address, or code location present in `inputs/wdt_top.v`. Findings that only gesture at "an undocumented register write" in the abstract, without naming the specific address and data value involved, are not acceptable.
- Do not flag documented, correctly-functioning behavior (e.g., the `WDT_PET` write at 0x08, or normal `WDT_CTRL`/`WDT_TIMEOUT` operation) as suspicious unless you have concrete evidence it deviates from its documented behavior.

## Starting point

A placeholder file already exists at `submission/trojan_report.json`. It contains a minimal, naive "no findings" answer and **will not pass evaluation as-is** — it is provided only so you can see the expected file location and JSON shape. You are expected to replace its contents with your own analysis before submitting.

## Evaluation

Your submitted `submission/trojan_report.json` will be graded on:

- **Detection rate** — whether you correctly identify the hidden behavior (if any) and its exact trigger conditions.
- **False positive rate** — whether you avoid flagging documented, correctly-behaving logic as anomalous.
- **Trigger/payload localization** — how precisely you pin down the exact address, data value, and internal mechanism involved.
- **Format compliance** — whether your JSON matches the required schema and is machine-parsable.

Toolchain note: `iverilog`/`vvp`/`yosys` are available in the evaluation environment and may be used by the grader to cross-check claims by simulating `inputs/wdt_top.v`, but your deliverable is the JSON report, not modified or new RTL.