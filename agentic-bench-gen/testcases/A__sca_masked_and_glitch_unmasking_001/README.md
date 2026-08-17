# Side-Channel Review: `masked_and` Gadget

## Background

Your team maintains a small RTL gadget, `masked_and`, that combines two
secret operands represented as two-share Boolean values into a
two-share Boolean output, such that:

```
q0 XOR q1 == (a0 XOR a1) AND (b0 XOR b1)
```

The module is intended to be used as a building block inside a larger
first-order masked datapath. Ports:

| Port | Direction | Width | Description |
|------|-----------|-------|-------------|
| `a0` | input | 1 | Share 0 of operand A |
| `a1` | input | 1 | Share 1 of operand A |
| `b0` | input | 1 | Share 0 of operand B |
| `b1` | input | 1 | Share 1 of operand B |
| `r`  | input | 1 | Fresh random mask bit |
| `q0` | output | 1 | Share 0 of result |
| `q1` | output | 1 | Share 1 of result |

You have been asked to perform an engineering review of the gadget's
internal signal structure ahead of a physical implementation sign-off:
document which internal nets carry which partial products, how those
nets are combined, where (if anywhere) registers exist in the signal
path, and propose a concrete RTL restructuring — with register
placement — that you believe improves the gadget's robustness with
respect to timing-dependent recombination of signals derived from the
input shares. Justify why your proposed placement changes the
ordering/arrival-time relationship of signals at the recombination
point.

## Provided Artifacts (`inputs/`)

- **`masked_and.v`** — the Verilog-2001 RTL source for the gadget.
- **`fault_model.json`** — a description of the observation/trace
  model assumed for this review (what an evaluator/attacker is
  assumed able to observe, and under what timing assumptions).
- **`design_brief.md`** — a short functional specification of the
  module: purpose, port list, and the intended algebraic invariant.
- **`sim_trace.vcd.txt`** — a small, human-readable stimulus/response
  table showing sample input assignments and the corresponding
  `q0`/`q1` outputs produced by the RTL, useful for sanity-checking
  your understanding of the module's behavior.

You are free to inspect these files, and to independently simulate
`inputs/masked_and.v` using `iverilog`/`vvp` (both available in this
environment) to explore its behavior, build your own testbenches, or
trace signal values. `yosys` is also available if you want to inspect
the synthesized structure. None of this exploration output needs to
be submitted — only the final report described below.

**Do not modify any file under `inputs/`.** Your analysis and
proposal go entirely into the submission file described next.

## Objective

Produce a structured engineering report at:

```
submission/vulnerability_report.json
```

that documents your findings about the gadget's internal signal
structure and proposes a register-placement change to the RTL. This
file is what gets graded — the `inputs/` files are reference material
only and are not evaluated directly.

A **naive placeholder file already exists** at
`submission/vulnerability_report.json`. It contains empty/default
values and does **not** constitute a real analysis — you must replace
its contents with your own findings before submitting. Submitting the
placeholder as-is will not satisfy the review requirements.

## Required Output Schema

`submission/vulnerability_report.json` must be a single valid UTF-8
JSON document (no trailing commentary) with exactly the following
top-level fields:

```json
{
  "suspect_nets": ["string", "..."],
  "algebraic_masking_correct": true,
  "vulnerability_summary": "string, at least 40 characters",
  "hardening_proposal": {
    "registers_to_add": ["string", "..."],
    "placement_description": "string, at least 40 characters"
  },
  "confidence": 0.0
}
```

Field-by-field requirements:

1. **`suspect_nets`** (array of strings): the exact identifiers, as
   they appear in `inputs/masked_and.v`, of the internal net(s) you
   consider most relevant to your findings. Every entry must
   correspond to a wire/reg actually declared or assigned in that
   file.

2. **`algebraic_masking_correct`** (boolean): your assessment of
   whether `q0 XOR q1` equals the correct AND of the unmasked
   operands under static (steady-state, non-transient) evaluation of
   the RTL. You can check this yourself with `iverilog`/`vvp`.

3. **`vulnerability_summary`** (string, ≥40 characters): a
   substantive description, in your own words, of the mechanism by
   which the nets you named in `suspect_nets` matter to the review —
   i.e., what is significant about how they are computed and
   combined.

4. **`hardening_proposal`** (object):
   - **`registers_to_add`** (array of strings, non-empty): exact
     signal names — each must exist in `inputs/masked_and.v`, or be a
     clearly-derived share-domain equivalent name — that you propose
     to register.
   - **`placement_description`** (string, ≥40 characters): where in
     the dataflow, relative to which existing combinational stage(s),
     the new registers should go, and why that placement matters for
     the ordering/arrival-time relationship of the signals involved.

5. **`confidence`** (number): a value between `0.0` and `1.0`
   reflecting your confidence in the report.

## Notes on Grading

Your submitted `vulnerability_report.json` will be checked for:

- structural validity (correct JSON, all required fields present with
  the correct types), and
- substantive correctness of the content (whether the named nets,
  algebraic assessment, summary, and register-placement proposal are
  actually consistent with `inputs/masked_and.v`'s real structure).

`iverilog` and `vvp` may be used during grading to cross-check
claims made against the RTL in `inputs/masked_and.v`, using stimulus
consistent with `inputs/sim_trace.vcd.txt`.