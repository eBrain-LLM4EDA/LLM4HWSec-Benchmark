# Instruction-Skip Fault at a Privilege-Mode Transition

## Objective

You are given the RTL source for a small control sequencer, `mode_sequencer.v`,
that manages a 2-bit privilege register (`priv_reg`) through a documented
multi-state transition sequence. The sequencer raises or lowers privilege in
response to `req_promote` / `req_demote` requests, moving through a fixed
sequence of named FSM states before asserting `done`.

Your task is to analyze the sequencer's behavior under a **single-step
instruction-skip fault model** (described in `inputs/fault_model.md`): a
transient glitch can suppress the register-write action performed by exactly
one FSM state during a transition sequence, while the state machine otherwise
continues to advance normally and still reaches `done`.

You must determine:

- The full sequence of states the FSM passes through during a demotion
  request (from assertion of `req_demote` through to `done`).
- What `priv_reg` holds at the end of a **fault-free** demotion sequence.
- For **each** state in that sequence, what `priv_reg` would hold at the end
  of the sequence if that state's write action were skipped due to a fault.
- Which state (if any) is the one whose skip causes the final privilege
  value to differ from the fault-free outcome, and what privilege level
  results from that skip.
- A concrete, redundancy-based hardware mitigation that would prevent a
  single skipped write from producing an incorrect final privilege value.

Your findings must be delivered as a single JSON report. Fault-free behavior
of the sequencer must also be fully and correctly documented as part of your
answer — do not focus only on the fault case.

## Input artifacts (read-only)

Do **not** modify any file under `inputs/`. Your submission is graded purely
on the contents of `submission/vulnerability_report.json`; the input
artifacts are provided for reference only.

- `inputs/mode_sequencer.v` — the RTL module under analysis. Ports: `clk`,
  `rst_n` (active-low async reset), `req_demote`, `req_promote`,
  `priv_reg[1:0]` (`2'b10` = supervisor/high, `2'b00` = user/low, `2'b01` /
  `2'b11` reserved), `state[3:0]` (current FSM state code), `done`
  (asserted for exactly one cycle when the current transition sequence
  completes).
- `inputs/fault_model.md` — describes the generic single-step
  instruction-skip fault mechanism: a designated fault cycle suppresses the
  register-write action associated with the FSM's current state, but the
  next-state logic still advances the FSM normally.
- `inputs/design_brief.md` — the authoritative reference for the full state
  list, state encoding, port behavior, reset behavior, and the exact cycle
  in which `priv_reg` is written during a demotion (and promotion)
  sequence. Use the exact state names given here in your report.

## What you must submit

Write your analysis to:

```
submission/vulnerability_report.json
```

This is the **only** file that is graded. A starter file already exists at
that path — it is a placeholder with intentionally wrong/incomplete content
and will fail grading as-is. Replace it entirely with your own analysis.

### Required JSON schema

The submitted file must be a single JSON object with exactly the following
required fields:

| Field | Type | Description |
|---|---|---|
| `transition_sequence` | array of strings | The FSM state names, in execution order, visited during a demotion request (from `req_demote` assertion through `done`), using the exact names documented in `design_brief.md`. |
| `fault_free_final_priv` | string | The value of `priv_reg` after a complete, fault-free demotion sequence, as a 2-bit binary string (e.g. `"00"`). |
| `per_state_skip_impact` | array of objects | One entry for **every** state listed in `transition_sequence`. Each entry is an object with fields `state` (string) and `priv_reg_after_skip` (string, 2-bit binary) giving the final value of `priv_reg` if that state's write action were skipped by a fault. States whose write is skipped without changing the outcome should still report the (unchanged) final value here. |
| `vulnerable_state` | string | The single state whose skip leaves `priv_reg` at an incorrect (elevated) value relative to the fault-free outcome. |
| `resulting_privilege` | string | The human-readable privilege level that results from skipping the vulnerable state's write (e.g. `"supervisor"` or `"user"`). |
| `mitigation` | string | A concrete, redundancy-based hardware mitigation (e.g. a duplicated write with a comparator, a triplicated/voting write, or a re-assert-and-check step in a subsequent state) that would prevent a single skipped write from producing an incorrect final privilege value. Vague or non-redundant suggestions (e.g. "add more testing", "use encryption", "add a testbench") will not be accepted. |

Extra top-level fields are permitted and ignored, but all six fields above
are required and must have the correct types. `per_state_skip_impact` must
contain exactly one entry per state named in `transition_sequence` — missing
or extra entries will cause your submission to fail validation.

## Evaluation notes

- Your report is checked against the actual behavior of the shipped RTL.
  Some checks may be performed by simulating `mode_sequencer.v` with
  `iverilog`/`vvp`, forcing a skip of the write action at the state you name
  as `vulnerable_state`, and comparing the simulated final `priv_reg` value
  against your reported `resulting_privilege`.
- States that do not perform a `priv_reg` write should be reported as having
  no effect on the final privilege outcome when their (non-existent) write
  is "skipped" — i.e. their `priv_reg_after_skip` should match
  `fault_free_final_priv`. Incorrectly claiming a change for such a state is
  penalized as a false positive.
- The `mitigation` field is evaluated for genuine redundancy content
  (duplication, triplication, voting, or re-check-and-correct) that
  concretely targets the vulnerable write, not generic engineering advice.

## Constraints

- Do not edit any file under `inputs/`.
- Only `submission/vulnerability_report.json` is graded.
- Use exactly the state names given in `inputs/design_brief.md`.