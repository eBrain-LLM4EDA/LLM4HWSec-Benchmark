# Gate-Level Trojan Detection: Peripheral Controller Analysis

## Objective

You are given a flat gate-level netlist of a peripheral controller block. The
controller includes a `secure_enable` control net that is intended to gate
access to a protected register interface. Your task is to **structurally
analyze the netlist** and determine whether any control net is driven by
something other than the logic implied by the design intent, and to report
your findings in a structured JSON file.

You should treat this as a hardware assurance exercise: assume the RTL/netlist
may have been altered somewhere between design intent and the shipped
netlist, and your job is to find and characterize any such alteration using
netlist-level evidence (drivers, fan-in, fan-out, cell types) — not just by
reading the design brief and trusting it matches the netlist.

## Input Artifacts

All inputs live under `inputs/`. **Do not modify any file in this
directory.** Your analysis output goes only into `submission/`.

| File | Description |
|---|---|
| `inputs/controller_netlist.v` | Flat structural Verilog netlist of the `controller` module, built entirely from cells declared in `cell_library.v`. |
| `inputs/cell_library.v` | Verilog definitions of the primitive cells used by the netlist (`AND2`, `OR2`, `INV`, `BUF`, `DFF`, `TIEHI`, `TIELO`, `MUX2`). |
| `inputs/design_brief.md` | Plain functional description of what the controller is supposed to do, including the intended behavior of `secure_enable`. |
| `inputs/testbench_regression.v` | A self-contained regression testbench exercising ordinary functional stimulus. |

## Suggested Workflow

You may use any combination of manual inspection, scripting, and EDA
tooling. Two toolchains are available in the environment:

1. **Simulation** (iverilog / vvp), useful for confirming basic functional
   behavior and for sanity-checking your understanding of the design:

   ```sh
   iverilog -g2012 -o sim inputs/cell_library.v inputs/controller_netlist.v inputs/testbench_regression.v
   vvp sim
   ```

2. **Static structural analysis** (Yosys, or your own netlist parser),
   useful for answering questions the regression testbench cannot answer,
   such as:
   - What cell instance actually drives a given net?
   - Are there internal nets or cell outputs with no load (dangling logic)?
   - Does the fan-in of a control signal match what the design brief
     describes?

   Example Yosys invocation:

   ```sh
   yosys -p "read_verilog inputs/cell_library.v inputs/controller_netlist.v; hierarchy -check; select -list"
   ```

**Important:** the regression testbench passing (i.e. `data_out` and
`secure_enable` looking "reasonable" for the stimulus provided) does **not**
by itself establish that the netlist is free of anomalies. The provided
stimulus is representative functional-verification-style stimulus; it is not
an exhaustive proof of correctness, and a netlist can behave identically to
the intended design across the tested stimulus while still containing a
structural deviation from design intent that only shows up under net-level
inspection or under stimulus the regression suite does not happen to cover.
You are encouraged to look at the netlist directly rather than relying
solely on simulation results.

## Output: `submission/trojan_report.json`

You must produce a single JSON file at `submission/trojan_report.json`
(replacing the placeholder file already present there) with the following
schema.

### Required fields (always)

| Field | Type | Description |
|---|---|---|
| `verdict` | string | Either `"trojan_detected"` or `"clean"`. |
| `suspect_instances` | array of strings | Instance names (exact strings as they appear in `controller_netlist.v`) that you consider suspicious or relevant to your verdict. May be empty if `verdict` is `"clean"`. |
| `rationale` | string | An explanation of the structural evidence supporting your verdict — e.g. what you found by examining drivers, fan-in, or fan-out, and why it is (or is not) consistent with the intended design described in `design_brief.md`. |

### Conditionally required fields

If `verdict` is `"trojan_detected"`, you must also include:

| Field | Type | Description |
|---|---|---|
| `compromised_net` | string | The exact name of the net (as it appears in `controller_netlist.v`) whose driver you believe is anomalous. |
| `driver_instance` | string | The exact instance name of the cell that actually drives `compromised_net`. |

### Optional field

| Field | Type | Description |
|---|---|---|
| `orphaned_logic` | array of strings | Instance names whose outputs you have determined are unconnected to any load in the netlist, if you believe such dangling logic is relevant to your findings. May be omitted or empty if not applicable. |

### Notes on grading

- Every instance name you list anywhere in the report (in
  `suspect_instances`, `driver_instance`, or `orphaned_logic`) must be an
  actual instance name that exists in `inputs/controller_netlist.v`.
  Made-up or paraphrased instance names will not be credited.
- `compromised_net` and `driver_instance` (when required) must exactly
  match the real net and instance names in the netlist, not just a
  description of them.
- Field values for `verdict` are matched case-insensitively, but instance
  and net names are matched exactly as they appear in the netlist.

### Example (schema illustration only — not a hint about the correct verdict or names)

```json
{
  "verdict": "trojan_detected",
  "suspect_instances": ["U_EXAMPLE_INSTANCE"],
  "compromised_net": "example_net",
  "driver_instance": "U_EXAMPLE_INSTANCE",
  "rationale": "Explain the structural evidence here.",
  "orphaned_logic": ["u_example_dead_cell"]
}
```

## Rules

- Do not modify any file under `inputs/`. Your submission consists solely
  of `submission/trojan_report.json`.
- Do not add other files under `submission/`; only
  `submission/trojan_report.json` is graded.
- Base every claim in your report on evidence you can point to in
  `controller_netlist.v` (driver of a net, cell type, fan-out, etc.), not on
  speculation about the design brief alone.