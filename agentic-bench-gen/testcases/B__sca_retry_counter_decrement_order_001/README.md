# Decrement-After-Check Ordering in a PIN Retry Counter

## Task

You are given the RTL for a legacy PIN-check authentication controller,
`inputs/pin_check_fsm.v`, along with its intended functional behavior
(`inputs/design_brief.md`), a reference testbench showing correct
fault-free operation (`inputs/testbench_reference.v`), and a description
of the fault-injection threat model the device must be analyzed against
(`inputs/fault_model.md`).

Your job is to analyze the finite-state machine's behavior **under fault
injection** and produce a vulnerability report identifying:

1. Which state transition in the FSM is exploitable under the fault
   model described in `fault_model.md`.
2. The precise timing window (relative to the `pin_valid` strobe) during
   which the fault must land to succeed.
3. A concrete RTL-level remediation that closes the vulnerability
   **without** changing the module's documented fault-free behavior.

This is a read-only analysis task. **You do not modify or resubmit any
RTL.** Your only deliverable is a JSON answer file.

## Module under test

`inputs/pin_check_fsm.v` implements:

```
module pin_check_fsm(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  pin_in,
    input  wire        pin_valid,
    output reg         auth_ok,
    output reg         locked_out,
    output reg  [3:0]  attempts_left
);
```

- `clk` / `rst_n`: system clock and active-low synchronous reset.
- `pin_in`: 8-bit candidate PIN, valid for comparison whenever
  `pin_valid` is asserted.
- `pin_valid`: one-cycle strobe indicating `pin_in` should be checked.
- `auth_ok`: asserted for exactly one clock cycle, two cycles after the
  cycle in which `pin_valid` was asserted, if and only if `pin_in`
  matched the stored secret and the device was not locked out.
- `locked_out`: becomes 1 the cycle after the retry counter reaches 0
  following a failed comparison, and stays 1 until reset.
- `attempts_left`: registered 4-bit remaining-retry count, reset to
  `4'd3`.

See `inputs/design_brief.md` for the full functional specification
(3-attempt lockout policy, strobe protocol, output timing) and
`inputs/testbench_reference.v` for a worked fault-free example showing
`attempts_left` progressing `3 -> 2 -> 1 -> 0` across three consecutive
wrong PINs and `locked_out` asserting afterward.

## Fault model

`inputs/fault_model.md` describes a single-event-transient state-skip
fault: a glitch (voltage, clock, or EM) can cause the FSM's state
register to skip one intended transition for a single clock edge,
landing directly in the state that would normally follow the *next*
state, without corrupting any data register or the comparison result
itself. Read this file carefully — your analysis should reason about
where in this specific FSM such a skip has security consequences, if
anywhere.

You are encouraged to use `iverilog` / `vvp` (both available in this
environment) to instrument `inputs/pin_check_fsm.v` and
`inputs/testbench_reference.v` yourself — e.g. write your own scratch
testbench that forces the state register to skip a transition on a
chosen cycle, and observe what happens to `attempts_left`,
`locked_out`, and `auth_ok`. This is optional but may help you confirm
your findings; only the JSON report described below is graded.

## Required output

Produce `submission/vulnerability_report.json`, replacing the
placeholder file already present at that path. The file must be valid
JSON with the following top-level fields:

| Field | Type | Description |
|---|---|---|
| `vulnerable_transition` | string | The exploitable state transition, named using the source and destination state identifiers exactly as they appear as `localparam`/`parameter` names in `pin_check_fsm.v` (e.g. `"STATE_A->STATE_B"` or an equivalent unambiguous phrasing naming both states). |
| `glitch_window` | string | A precise description of the cycle(s), relative to the `pin_valid` assertion, during which the fault must be injected for the attack to succeed. Avoid vague answers like "any time" — describe the specific window and why it matters. |
| `remediation` | string | A concrete description of the RTL-level change that would close the vulnerable window. Describe *what changes and where* (e.g. which state's logic moves, what new signal or restore path is introduced), not just a generic mitigation name. |
| `affected_signals` | array of strings | At least the retry-counter signal and the relevant authentication/lockout output signals affected by the vulnerability. |
| `fault_free_behavior_preserved` | boolean | Whether your proposed remediation preserves the documented fault-free 3-attempt lockout sequence shown in `testbench_reference.v`. |
| `fault_free_justification` | string | A short explanation of why the remediation does or does not preserve that sequence (attempts_left counting down from reset value to 0 over three consecutive fault-free failures, then `locked_out` asserting). |
| `state_names_referenced` | array of strings | State names you referenced above, restricted to identifiers that literally appear as `localparam`/`parameter` declarations in `inputs/pin_check_fsm.v`. |
| `confidence` | number | A value between 0 and 1 reflecting your confidence in the finding. |
| `method` | string | One of `"static_analysis"`, `"simulation"`, or `"both"`, describing how you derived the finding. |

An example of the required shape (values are illustrative placeholders,
**not** correct answers — see `submission/vulnerability_report.json`
for the starting file you must replace):

```json
{
  "vulnerable_transition": "SOURCE_STATE->DEST_STATE",
  "glitch_window": "describe the precise window here",
  "remediation": "describe the concrete RTL change here",
  "affected_signals": ["signal_a", "signal_b"],
  "fault_free_behavior_preserved": true,
  "fault_free_justification": "explain why here",
  "state_names_referenced": ["STATE_X", "STATE_Y"],
  "confidence": 0.9,
  "method": "both"
}
```

## Grading

`evaluate.py` reads the artifacts under `inputs/` for reference and
grades the JSON fields of your submitted report against a hidden
ground truth. It may also optionally cross-simulate
`inputs/pin_check_fsm.v` together with `inputs/testbench_reference.v`
(and a forced-fault stimulus) to verify that factual claims in your
report are consistent with the RTL's actual behavior.

You do not need to match any particular wording. What matters is that
your report:

- names the correct vulnerable transition (both source and destination
  state, spelled as in the RTL),
- correctly characterizes the timing window of the fault,
- proposes a remediation that is concrete, technically sound, and
  actually closes the window,
- correctly assesses (and justifies) whether that remediation preserves
  the documented fault-free lockout behavior, and
- includes all required fields with the correct types.

A report that is empty, vague, or names the wrong transition/window
will fail grading — this is exactly the state of the placeholder file
currently at `submission/vulnerability_report.json`. Replace it with
your own analysis.