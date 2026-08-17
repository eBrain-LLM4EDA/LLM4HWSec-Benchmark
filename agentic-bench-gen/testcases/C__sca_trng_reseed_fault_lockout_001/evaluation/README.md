# Evaluation: Fault-Forced TRNG Reseed to a Fixed Value

This directory contains the grading harness for task `sca_trng_reseed_fault_lockout_001`.

## What is graded

The submission is **not** code. It is an analysis report at:

```
submission/vulnerability_report.json
```

`evaluate.py` reads the reference RTL and supporting artifacts under `inputs/`:

- `inputs/trng_postproc.v` — the module under analysis
- `inputs/fault_model.json` — the generic fault taxonomy reference
- `inputs/design_brief.md` — the documented normal-operation behavior

It then grades the **content** of `submission/vulnerability_report.json` against
ground truth derived directly from `inputs/trng_postproc.v`. Participants must
not modify any file under `inputs/`; only the submitted report is graded.

If any of the three input files, or the submission file, cannot be found,
every requirement is reported as `[TEST] FAIL: <id>: SETUP: <path> not found`
and the script exits non-zero.

## Required report schema (FR1-FR4)

The report must be a single JSON object (parseable via a standard JSON
parser) containing at least the following top-level fields:

| Field | Type | Notes |
|---|---|---|
| `faultable_signal` | string | exact/normalizable RTL signal name |
| `fixed_state_value` | string | 0x-prefixed 32-bit hex value |
| `trigger_condition` | string | describes the exact input sequence causing the fault |
| `mitigation` | string | proposed hardening measure |
| `affected_outputs` | array of strings | subset of `["rand_out", "seed_valid"]` |
| `documented_reseed_behavior_correct` | boolean | correctness of the fault-free (entropy_ready=1) reseed path |
| `simulation_trace_description` | string | concrete cycle-by-cycle testbench scenario description |

Additional keys are permitted and ignored.

- **FR1** — `faultable_signal`, `fixed_state_value`, `trigger_condition`,
  `mitigation` must all be present and be strings; `fixed_state_value` must
  additionally parse as a well-formed hexadecimal value (0x-prefixed,
  `32'h`-prefixed, or bare hex up to 8 digits are all accepted and
  normalized).
- **FR2** — `affected_outputs` must be an array of strings, every element
  drawn from `{rand_out, seed_valid}`; `documented_reseed_behavior_correct`
  must be a strict JSON boolean.
- **FR3** — `simulation_trace_description` must be a non-empty string that
  references reset, `reseed_req`, `entropy_ready`, and an indication that
  `entropy_ready` is held low/deasserted during the scenario.
- **FR4** — the submission file must parse as valid JSON, with a top-level
  JSON object.

## Substantive correctness checks (SR1-SR4)

These checks verify that the report's *findings*, not just its shape, are
correct with respect to the RTL's actual documented behavior.

- **SR1** — `faultable_signal` must (after normalization) identify the
  `entropy_ready` handshake input as the signal whose suppression during a
  reseed request forces a fixed value into the internal seed state.
- **SR2** — `fixed_state_value`, normalized to a zero-padded 8-hex-digit
  lowercase form, must exactly match the fixed default constant that
  `evaluate.py` extracts directly from `inputs/trng_postproc.v` (the
  literal loaded into the internal seed register on the
  `reseed_req`-asserted-while-`entropy_ready`-low branch). This constant is
  parsed dynamically from the shipped RTL for each evaluation run — nothing
  is hardcoded in the grader.
- **SR3** — `mitigation` must substantively describe a
  repetition/health-check gating scheme: it must combine (a) a notion of
  counting or tracking consecutive reseed cycles/attempts that occur
  without ever observing genuine fresh entropy, with (b) a notion of
  gating, blocking, or withholding a downstream output (e.g. `rand_out`,
  `seed_valid`, or an equivalent "trustworthy output" concept) until a
  reseed with `entropy_ready` actually asserted is observed. Superficial
  fixes (widening the register, adding ECC/CRC, "add more randomness")
  without either of these two concepts are rejected.
- **SR4** — `affected_outputs` must include `rand_out`;
  `documented_reseed_behavior_correct` must be `true` (the fault-free,
  `entropy_ready`-high reseed path is indeed correct per the interface
  contract); and `trigger_condition` must clearly describe both
  `reseed_req` being asserted and `entropy_ready` being low/deasserted
  concurrently.

## Optional iverilog corroboration

`evaluation/tb_reseed_fault.v` is an optional corroborating testbench. When
`iverilog`/`vvp` are available, `evaluate.py` compiles this testbench
together with `inputs/trng_postproc.v`, drives reset followed by
`reseed_req` asserted with `entropy_ready` held low for two cycles, and
reads back the internal seed register value via a hierarchical reference
(`dut.seed_reg`) printed as `SEED_REG=0x%08x`.

This simulation is used only to corroborate the reported `fixed_state_value`
against the constant independently parsed from the RTL source:

- If the toolchain is unavailable, or compilation/simulation fails for any
  reason, this is reported informationally (`[INFO] ...`) and does **not**
  by itself cause any requirement to fail — the report-based checks above
  remain authoritative.
- If the simulation succeeds and clearly shows that the RTL's actual
  post-reseed `seed_reg` value differs from what the report claims (even
  though the report matched the value the parser extracted from source
  text), `SR2` is failed with an explanation, since the simulated behavior
  takes precedence as ground truth in that case.

## Pass/fail semantics

For each of `FR1`, `FR2`, `FR3`, `FR4`, `SR1`, `SR2`, `SR3`, `SR4`,
`evaluate.py` prints exactly one line:

```
[TEST] PASS: <id>
```
or
```
[TEST] FAIL: <id>: <reason>
```

The script exits `0` only if every requirement passes; otherwise it exits
non-zero.