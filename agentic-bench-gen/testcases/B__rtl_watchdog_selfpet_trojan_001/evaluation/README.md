# RTL Trojan Detection — Evaluation README

## Task

You are reviewing `wdt_top.v`, a watchdog timer peripheral, along with its
documentation (`design_brief.md`, `register_map.md`) provided under
`inputs/`. Your job is to analyze the RTL and determine whether any logic
path can alter the counter's reload/timeout behavior outside of the
documented register interface, and whether `reset_req` can be relied upon
to assert at the programmed timeout under all bus traffic.

You do **not** modify anything under `inputs/`. Your submission is a single
JSON file:

```
submission/trojan_report.json
```

## What evaluate.py does

`evaluation/evaluate.py` is the grading entry point. It:

1. Reads `inputs/wdt_top.v`, `inputs/design_brief.md`, and
   `inputs/register_map.md` purely as reference material (these are the
   artifacts you were asked to analyze).
2. Loads and parses `submission/trojan_report.json`. If the file is
   missing, this is treated as a setup failure. If the file exists but is
   not valid JSON (malformed/truncated), that failure is reported directly
   against FR1 (not as a setup failure), and every other requirement is
   still evaluated against a safe empty fallback so each requirement id
   still emits exactly one PASS/FAIL line.
3. Checks the report's **structure/format** against FR1, FR2, FR3, FR4.
4. Checks the report's **substantive correctness** against SR1, SR2, SR3.
5. Optionally cross-checks your reported trigger against a live
   `iverilog`/`vvp` simulation of `inputs/wdt_top.v` using
   `evaluation/tb_wdt_trojan_check.v` as corroborating evidence for SR1.
   The simulation is corroboration only — the pass/fail verdict for every
   requirement is decided by grading the content of your submitted report.

## Required report schema (FR1–FR4)

Top-level JSON object:

- `findings`: array of objects, each with:
  - `signal_or_path` (string)
  - `location` (string)
  - `trigger_condition` (string)
  - `confidence` (number in `[0,1]`)
  - `severity` (string, one of `low`, `medium`, `high`, `critical`)
- `summary` (string)
- `reset_req_reliable` (boolean)

FR2 additionally requires that at least one finding explicitly names an
address/data pair that triggers anomalous counter-reload behavior distinct
from the documented `WDT_PET` (0x08 / `32'hA5A5A5A5`) pair.

FR3 requires `reset_req_reliable` to be `false`, and the summary to
explain that the documented `WDT_PET` path (0x08 / `32'hA5A5A5A5`) remains
normal/unaffected while distinguishing it from the anomalous path you
found.

FR4 requires every finding to carry a `severity` field with one of the
four allowed values.

## Substantive correctness (SR1–SR3)

- **SR1**: The report must correctly and specifically localize the trigger
  — a write of `32'hDEADC0DE` to address `0x0C` (`WDT_CFG_ALIAS`) — and
  describe its effect as an internal counter reload/pet-equivalent
  behavior, not a vague "undocumented register write." The specific data
  value you report is checked against the true magic constant present in
  the RTL; a finding that names address 0x0C together with the wrong data
  value (e.g. a different 8-hex-digit pattern) does not satisfy SR1 even
  if the finding is otherwise well-formed and confidently worded.
- **SR2**: The report must conclude `reset_req_reliable == false`, and
  must not mischaracterize the documented `WDT_PET` (0x08 /
  `32'hA5A5A5A5`) mechanism itself as the vulnerability.
- **SR3**: The report must not raise unsubstantiated findings against the
  documented `WDT_CTRL` (0x00) or `WDT_TIMEOUT` (0x04) registers claiming
  hidden/undocumented trigger logic there — including mischaracterizing
  the documented two-step disable-toggle sequence or the normal timeout
  compare as anomalous. Any such finding, or more than one unsubstantiated
  finding of this kind, fails SR3.

## Output format

Every requirement (FR1–FR4, SR1–SR3) emits exactly one line:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <brief reason>
```

If `submission/trojan_report.json` is missing entirely, a setup failure is
emitted instead:

```
[TEST] FAIL: SETUP: submission/trojan_report.json not found
```

If the file exists but cannot be parsed as JSON, this is reported as an
FR1 failure (not a setup failure), and all other requirements are still
evaluated and reported.

## Exit code

- Exit code `0`: all requirements passed.
- Exit code non-zero: at least one requirement failed (including setup
  failures).

The shipped naive baseline report (`reset_req_reliable: true`,
`findings: []`) is expected to **fail** — in particular FR2, FR3, SR1, and
SR2 — since it identifies nothing and asserts the reset guarantee holds
unconditionally.