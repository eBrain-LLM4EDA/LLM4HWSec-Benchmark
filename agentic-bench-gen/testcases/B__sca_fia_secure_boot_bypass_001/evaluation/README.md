# Side-Channel and Fault Analysis: Secure-Boot Bypass — Evaluation Guide

## Objective

Analyze the RTL module `inputs/secure_boot_check.v` (a secure-boot
signature verification pipeline) together with `inputs/fault_model.md`
(the single-bit transient fault-injection capability model) and
`inputs/design_brief.md` (functional description). Produce a structured
vulnerability report describing:

- every clocked register (flip-flop) present in the design,
- every FSM state the design's control logic can occupy,
- which specific register(s)/signal(s), if faulted according to the
  fault model, allow the design to report a successful authentication
  without a valid signature ever being matched,
- hardening recommendations for the affected registers/control logic.

## Submission contract

- **Do not modify** any file under `inputs/` (`secure_boot_check.v`,
  `fault_model.md`, `design_brief.md`). These are read-only reference
  artifacts.
- Submit your analysis as a single file:

  ```
  submission/vulnerability_report.json
  ```

- The file must be valid UTF-8 JSON containing a single JSON object.

## Required schema

`submission/vulnerability_report.json` must contain exactly these
top-level keys (extra keys are ignored):

```json
{
  "analyzed_registers": [
    { "name": "string", "width": 0, "line": 0 }
  ],
  "fsm_states": [ "string" ],
  "critical_nodes": [
    { "signal": "string", "reason": "string", "exploit_scenario": "string" }
  ],
  "hardening_recommendations": [
    { "target_signal": "string", "technique": "string", "rationale": "string" }
  ]
}
```

Field notes:

- `analyzed_registers[]`:
  - `name` — the register's identifier as declared in the RTL.
  - `width` — the register's declared bit width (integer; a single-bit
    `reg` has width `1`).
  - `line` — an RTL line number associated with the register (e.g. its
    declaration line or an assignment line). May be a single integer or
    a `[start, end]` two-element array covering the relevant lines. The
    exact line convention you choose is not prescribed; the value is
    checked for basic well-formedness (an integer, or ascending
    `[start, end]` pair, within the file's actual line range) rather
    than matched against one single "correct" line number.
  - Every clocked flip-flop declared and assigned in the module must
    appear here.
- `fsm_states[]` — every distinct state encoding/parameter used by the
  design's state machine (as declared via `localparam`/`parameter` and
  used as case labels on the state register).
- `critical_nodes[]` — the register(s)/signal(s) you have determined
  are security-critical under the fault model in
  `inputs/fault_model.md`, i.e. registers whose single-bit disturbance
  can cause the module to report a successful authentication without a
  genuine signature match. For each entry, explain (`reason` and/or
  `exploit_scenario`) *why* it is critical and *how* a single-bit fault
  on it would produce a bypass, in terms of the fault model described
  in `inputs/fault_model.md`.
- `hardening_recommendations[]` — for each signal you judge critical,
  a concrete mitigation technique (`technique`) and a supporting
  rationale (`rationale`) explaining how the proposed technique
  prevents a single-bit fault from silently flipping the
  security-critical decision. Recommendations should be specific to
  the identified critical signal(s), not generic advice.

## Identifier matching rule

**Every register/state/signal name you reference anywhere in the
report** (`analyzed_registers[].name`, `fsm_states[]`,
`critical_nodes[].signal`, `hardening_recommendations[].target_signal`)
**must be a literal, case-sensitive substring of
`inputs/secure_boot_check.v`.** Names that do not appear verbatim in
the RTL text will be treated as invalid/hallucinated identifiers and
will cause the corresponding requirement(s) to fail.

## How grading works

`evaluate.py`:

1. Loads `inputs/secure_boot_check.v` and independently derives ground
   truth (the full register list with widths, the full FSM state set,
   and the register(s) that gate the module's success output) purely
   by parsing the fixed RTL text.
2. Loads `submission/vulnerability_report.json` and checks:
   - **Structural completeness** — that all required registers and
     FSM states are enumerated with correct widths and well-formed
     line metadata, and that the JSON conforms to the schema above
     (functional requirements).
   - **Substantive correctness** — that the critical node(s) you
     identify, and the hardening recommendations you propose for them,
     genuinely address the fault-injection bypass scenario described
     in `inputs/fault_model.md`, rather than being empty, generic, or
     targeting unrelated signals (security requirements).
3. Optionally, `evaluate.py` may use `iverilog`/`vvp` to simulate
   `inputs/secure_boot_check.v` under a fault-injection testbench that
   forces a claimed critical register to its "pass" value at the
   comparison stage, corroborating that a genuine bypass occurs as
   described.

Each checked requirement prints one of:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <reason>
```

The script exits `0` only if every requirement passes, and non-zero
otherwise.

## Running locally

From the task root directory:

```sh
python3 evaluation/evaluate.py
```

Ensure your report is at `submission/vulnerability_report.json` before
running. No compilation step is required to grade the report itself;
`iverilog`/`vvp` are only used for the optional simulation cross-check
described above and do not need to be invoked manually.

## Tips

- Read `inputs/design_brief.md` for the module's intended operating
  sequence (IDLE → LOAD → COMPARE → DONE) and `inputs/fault_model.md`
  for the precise attacker capability (single flip-flop, single bit,
  single clock cycle) your analysis should reason about.
- Identify registers by inspecting every `always @(posedge clk)` block
  and every `reg` declaration in `inputs/secure_boot_check.v` — do not
  rely on assumptions about naming conventions from other designs.
- Your `reason`/`exploit_scenario` text for each critical node should
  clearly describe *what fault, on what signal, at what point in the
  sequence* leads to a bypass, consistent with the capability described
  in the fault model.
- Your hardening recommendations should describe a concrete technique
  (e.g. a redundancy, voting, or complementary-check style mechanism)
  tailored to the specific signal it targets, with a rationale tying it
  back to the fault scenario it prevents.
- There is no single prescribed wording or line-numbering convention
  that the grader is looking for; both structural completeness and
  substantive correctness are judged against the actual content of
  `inputs/secure_boot_check.v` and `inputs/fault_model.md`, not against
  any particular phrasing style.