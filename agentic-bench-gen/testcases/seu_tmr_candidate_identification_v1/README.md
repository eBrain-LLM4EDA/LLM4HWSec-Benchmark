# SEU Hardening Candidate Identification for a Controller/Datapath RTL Module

## Objective

You are given a small RTL controller/datapath design and an accompanying single-event-upset (SEU) fault model. Your job is to analyze the design and produce a structured vulnerability/hardening report that:

1. Inventories **every register (flip-flop group)** declared in the RTL.
2. Classifies each register as either `control_state` or `data_pipeline`.
3. Recommends whether each register should receive **Triple Modular Redundancy (TMR)** hardening against SEUs, given a fixed area/power hardening budget.
4. Justifies each recommendation with a concrete engineering rationale grounded in the fault model.

You must produce your answer as a single JSON file. This is an analysis task — you are not modifying or resynthesizing the RTL, only reasoning about it.

## Inputs

All input artifacts live under `inputs/` and must **not** be modified:

- `inputs/controller_datapath.v` — the RTL module under analysis (a controller FSM plus a small datapath). This is the authoritative source for register names and bit widths.
- `inputs/fault_model.md` — background reading describing the generic SEU fault assumptions used for this analysis, and a general explanation of what TMR is and why it costs area/power.
- `inputs/register_map.json` — a plain reference listing each register's name, bit width, and a one-line functional description, to help you locate and understand signals quickly. It does not contain any classification or recommendation — that is your job.

You may use `iverilog`, `vvp`, and `yosys` if you want to simulate or elaborate the design to check your understanding (e.g. tracing FSM transitions, confirming bit widths), but this is optional and not required to complete the task.

## Output

Submit your analysis as:

```
submission/vulnerability_report.json
```

This is the **only** file that will be graded. Do not submit anything else, and do not edit any file under `inputs/`. A starter/placeholder file already exists at that path — you must replace its contents with your real analysis (the placeholder is intentionally incomplete and will not pass evaluation).

## Required JSON Schema

Your submitted file must be valid UTF-8 JSON with exactly this top-level shape:

```json
{
  "schema_version": "1.0",
  "summary": {
    "total_registers": <int>,
    "control_state_count": <int>,
    "data_pipeline_count": <int>,
    "tmr_recommended_count": <int>
  },
  "registers": [
    {
      "signal_name": "<string>",
      "bit_width": <int>,
      "category": "control_state" | "data_pipeline",
      "tmr_recommended": <bool>,
      "justification": "<non-empty string>"
    },
    ...
  ]
}
```

### Field requirements

- `schema_version` must be the literal string `"1.0"`.
- `summary.total_registers` must equal the number of entries in `registers`.
- `summary.control_state_count` / `summary.data_pipeline_count` must equal the number of entries with the corresponding `category`.
- `summary.tmr_recommended_count` must equal the number of entries with `tmr_recommended: true`.
- Each entry in `registers` must include **all five** fields listed above, with correct types.
- `signal_name` must exactly match a register name as declared in `inputs/controller_datapath.v` (same spelling/case). Do not invent register names that do not appear in the RTL, and do not omit any that do.
- `bit_width` must exactly match the bit width of that signal as declared in the RTL.
- `category` must be exactly one of the two literal strings `"control_state"` or `"data_pipeline"`.
- `justification` must be a real, non-empty explanation of your reasoning for that specific register — not generic boilerplate copy-pasted across every entry. Explain *why* that register's role makes it more or less sensitive to a silent single-bit corruption, given the fault model.

## Constraints

- Do **not** edit any file under `inputs/`. Files there are reference-only.
- Submit **only** `submission/vulnerability_report.json`. No other files under `submission/` are read or graded.
- Every register you report must correspond to an actual `reg`-declared storage element in `inputs/controller_datapath.v`, matched by name and bit width exactly as declared there.
- Do not fabricate registers, and do not omit any that exist in the RTL.
- Output must be plain JSON — no markdown formatting, no code fences, no comments, no trailing commentary, and no additional top-level keys beyond `schema_version`, `summary`, and `registers`.

## Notes on approach

Under a fixed hardening budget, TMR cannot be applied to everything — it triples area and power for whatever it protects. A defensible report should reflect genuine prioritization: some registers, if corrupted by a single bit-flip, could silently steer the design into an invalid or incorrect behavior with no way for downstream logic to detect or recover from it before the next legitimate update. Others produce a bounded, transient numerical error that is naturally overwritten or superseded within a cycle or two of normal operation. Your justifications should reflect this kind of reasoning about each specific register's role in the design, based on what you can observe by reading the RTL and the fault model — not a one-size-fits-all template answer.