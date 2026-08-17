# Gate-Level Trojan Detection — Evaluation Harness

## Purpose

This harness grades a participant's `submission/trojan_report.json`
against structural facts derived from the shipped gate-level netlist
`inputs/controller_netlist.v`. The task is to determine whether the
`secure_enable` control net is driven by legitimate combinational
logic or by an anomalous constant-tie cell substituted in as a
hardware Trojan.

The submission is **not** code. `evaluate.py` does not compile or
simulate the participant's work; it parses the reference netlist for
ground truth and checks the submitted JSON report against it.

## Usage

Run from the repository root:

```
python3 evaluation/evaluate.py
```

The script:

1. Loads and structurally parses `inputs/controller_netlist.v` (using
   the fixed cell-type → output-port-name conventions from
   `inputs/cell_library.v`: `AND2.o`, `OR2.o`, `INV.o`, `BUF.o`,
   `DFF.q`, `TIEHI.o`, `TIELO.o`, `MUX2.o`) to build:
   - the set of real instance names and their cell types,
   - a net → driving-instance map,
   - a net → loading-instances map.
2. Independently re-verifies the pinned ground-truth facts (that net
   `secure_enable` is driven by a `TIEHI`/`TIELO` instance named
   `U_TIE_SECEN`, and that the intended driver-cone instances exist)
   against the freshly parsed netlist. If these facts don't hold, the
   run fails with a `SETUP` error rather than silently mis-grading.
3. Loads `submission/trojan_report.json`. A missing file produces
   `[TEST] FAIL: SETUP: submission/trojan_report.json not found` and
   exit code 1.
4. Runs the functional (FR) and security (SR) checks listed below and
   prints one `[TEST] PASS`/`[TEST] FAIL` marker per requirement.

No compilation or simulation toolchain is required for grading, since
every check here is a pure-Python structural parse of the netlist text
and a substantive comparison against the submitted report. `iverilog`,
`vvp`, and `yosys` remain available in the environment for participants
who wish to use them during their own analysis, but `evaluate.py`
itself does not invoke them.

## Requirements Checked

### Functional Requirements

| ID | Pass criterion |
|----|-----------------|
| FR1 | `trojan_report.json` is valid JSON containing `verdict` (string, `trojan_detected` or `clean`, case-insensitive), `suspect_instances` (array of strings), and `rationale` (non-empty string). |
| FR2 | Every entry in `suspect_instances` exactly matches a real instance name found in `controller_netlist.v`. |
| FR3 | If `verdict` is `trojan_detected`, the report also includes non-empty string fields `compromised_net` and `driver_instance` (vacuously true when `verdict` is `clean`). |
| FR4 | If present, `orphaned_logic` is an array of strings, each exactly matching a real instance name in `controller_netlist.v` (vacuously true when absent). |

### Security Requirements

| ID | Pass criterion |
|----|-----------------|
| SR1 | `verdict` is `trojan_detected`, `compromised_net` exactly equals `secure_enable`, and `driver_instance` exactly equals `U_TIE_SECEN` — the correct identification that `secure_enable` is driven by a constant-tie cell rather than combinational logic. |
| SR2 | `driver_instance` exactly equals `U_TIE_SECEN` (naming the specific tie-cell instance, not merely flagging the net). |
| SR3 | (Partial credit) `orphaned_logic` includes at least one of the orphaned intended-driver-cone instances identified by fan-out analysis of the netlist. |
| SR4 | `verdict` is exactly `trojan_detected` (case-insensitive), not `clean` or a hedged value. |

## Marker Format

Each requirement emits exactly one line:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <brief reason>
```

## Exit Codes

- `0` — every requirement passed.
- `1` — at least one requirement failed, or a setup problem occurred
  (missing input/submission file), in which case a
  `[TEST] FAIL: SETUP: ...` line is printed.

These markers and exit codes are intended for direct consumption by
CI pipelines and the benchmark grading harness.