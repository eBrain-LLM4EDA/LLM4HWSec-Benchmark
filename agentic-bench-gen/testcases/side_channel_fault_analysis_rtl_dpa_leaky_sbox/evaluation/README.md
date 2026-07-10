# Side-Channel Leakage Localization — Submission Guide

## Objective

Analyze the round datapath provided under `inputs/` (`round_datapath.v`,
`sbox_table.v`) together with the Hamming-distance power model
(`power_model.md`) and the accompanying testbench (`testbench_hd_trace.v`),
and produce a structured vulnerability report identifying which registers
show measurable data-dependent switching activity, plus concrete hardening
recommendations for any signal you flag as leaking.

Read `inputs/design_brief.md` for a description of the datapath's pipeline
stages and the full set of registers in scope for this analysis.

## What to submit

Write your findings to:

```
submission/vulnerability_report.json
```

Do **not** modify anything under `inputs/`. Only the submission file above
is graded.

## Required schema

```json
{
  "signals": [
    {
      "signal_name": "string",
      "hd_variance": 0.0,
      "flagged": true,
      "notes": "optional string"
    }
  ],
  "recommendations": [
    {
      "target_signal": "string",
      "technique": "string",
      "rationale": "string"
    }
  ]
}
```

- Top-level keys `signals` (array) and `recommendations` (array) are
  required. Any other top-level keys are ignored.
- Each entry in `signals` must have:
  - `signal_name` (string) — must exactly match a register name declared
    in `inputs/round_datapath.v` (as documented in `inputs/design_brief.md`).
  - `hd_variance` (number, not a string, not a boolean).
  - `flagged` (boolean).
  - `notes` (string, optional).
- Each entry in `recommendations` must have:
  - `target_signal` (string) — must reference a `signal_name` that also
    appears in the `signals` array. Dangling references (pointing at a
    signal not listed in `signals`) are invalid.
  - `technique` (string) — the concrete countermeasure mechanism proposed.
  - `rationale` (string) — why this signal/technique was chosen.

All numeric fields must be plain JSON numbers; all boolean fields must be
JSON `true`/`false`.

## Coverage requirement

Every register named in `inputs/design_brief.md` (the complete set of
pipeline registers documented there) must appear in your `signals` array
with a well-formed entry. Partial reports that omit any of these registers
will fail the coverage check, regardless of how accurate the entries that
are present are.

## How `hd_variance` must be computed

`hd_variance` is **not** a free-form estimate — it must be derived from
actually simulating the provided RTL and testbench, following the exact
procedure in `inputs/power_model.md`:

1. Simulate `inputs/round_datapath.v`, `inputs/sbox_table.v`, and
   `inputs/testbench_hd_trace.v` together, e.g.:

   ```
   iverilog -o sim.vvp inputs/round_datapath.v inputs/sbox_table.v inputs/testbench_hd_trace.v
   vvp sim.vvp
   ```

2. For each register column in the printed trace, walk the trace in cycle
   order and compute the Hamming distance `HD = popcount(prev XOR curr)`
   for every pair of consecutive printed cycles.

3. Compute the **Bessel-corrected sample variance** of that register's HD
   population:

   ```
   mean = (1/N) * sum(HD_i)
   hd_variance = (1 / (N - 1)) * sum((HD_i - mean)^2)
   ```

   using `N - 1` in the denominator, exactly as specified in
   `inputs/power_model.md`. Do not use the population-variance formula
   (dividing by `N`), and do not filter or partition the trace into
   subsets unless you clearly document your reasoning for doing so.

The evaluator independently re-simulates the same RTL/testbench and
recomputes these values itself, then cross-checks your submitted
`hd_variance` numbers (and the `flagged` status they imply) against that
recomputation for internal consistency, within a small tolerance. Numbers
must reflect the actual simulation output — inventing or estimating values
without running the simulation will not survive this cross-check.

## `flagged` and ranking

Set `flagged: true` on any signal whose Hamming-distance variance is
material enough, in your judgment as an analyst, to represent a
data-dependent leakage concern. Signals judged not to leak in a
meaningful way should be `flagged: false`. Your `hd_variance` numbers
should be consistent with your own flagging decisions and with the
relative ranking of signals implied by the simulated data — i.e. if you
flag a signal as leaking, its reported variance should stand out relative
to signals you do not flag.

## Hardening recommendations

For every signal you flag as leaking, provide at least one recommendation
in `recommendations` whose `target_signal` matches that signal, and whose
`technique` (or, if left blank, `rationale`) names a concrete, recognized
side-channel countermeasure mechanism, for example:

- Boolean or arithmetic masking (e.g. of the S-box input/output)
- Dual-rail or complementary logic
- Random precharge
- Hiding via balanced routing / constant switching activity
- Blinding

Generic, mechanism-free advice (e.g. "add more logic," "review the
design," "use better practices") without naming one of these (or an
equivalent recognized) technique will not satisfy the hardening checks.
Recommendations should be targeted at the specific signals that actually
show leakage in your analysis, rather than applied uniformly across the
whole datapath — diluting hardening effort onto non-leaky signals instead
of the genuinely leaky ones works against you.

## Summary of what is checked

- **Completeness**: every register from `inputs/design_brief.md` has a
  well-formed entry in `signals`.
- **Consistency with simulation**: reported `hd_variance` values for
  registers driven purely by plaintext (before any key mixing) must match
  a re-simulation of the provided testbench within a small tolerance.
- **Schema validity**: the submission is valid JSON matching the schema
  above exactly.
- **No dangling references**: every recommendation's `target_signal`
  exists in `signals`.
- **Substantive correctness**: registers whose transitions genuinely
  depend on key material must be correctly flagged, with `hd_variance`
  values consistent with re-simulation, and must not be out-ranked by
  non-key-dependent registers in your own reported numbers.
- **Hardening precision**: recommendations for genuinely leaky signals
  must name a recognized countermeasure mechanism, and hardening effort
  must not be exclusively aimed at non-leaky signals.