# Evaluation Harness for reverse_crc16_serial

## Overview

This directory contains the automated grading harness for the CRC-16 reverse-engineering task. The harness compiles the participant's submitted Verilog module together with a testbench, simulates it cycle-accurately, and checks the output against a reference model. All grading is behavioral — no static source-code pattern matching is used to award a PASS.

## Files

| File | Role |
|------|------|
| `evaluate.py` | Main entry point. Orchestrates compilation, simulation, and verdict reporting. |
| `tb_crc16.v` | Top-level Verilog testbench. Instantiates the DUT and a reference CRC-16 model, drives the interface, and prints `[TEST]` markers. |
| `private/tb_sr1_vectors.v` | Private test vectors (random bitstreams with expected CRC outputs) used exclusively for the security requirement SR1. Not visible to participants. |
| `README.md` | This file. |

## Simulation Flow

1. **Compilation**  
   `evaluate.py` invokes `iverilog -g2012 -o <tmpdir>/sim.vvp submission/recovered_rtl.v evaluation/tb_crc16.v`.  
   If compilation fails, all behaviorally-graded requirements (FR1–FR3, SR1) are marked `FAIL` with the compiler error summary, and FR4 is marked `FAIL` explicitly.

2. **Simulation**  
   The compiled simulation is run with `vvp <tmpdir>/sim.vvp`. The testbench prints one line per requirement probe to stdout.  
   If the simulation times out or crashes, the affected requirements are marked `FAIL`.

3. **Verdict**  
   `evaluate.py` parses the stdout lines, matches them to the requirement map, and re-emits a final `[TEST] PASS` or `[TEST] FAIL` line for each requirement. It exits with code 0 only when every requirement passes.

## Requirement Map

| ID  | Type       | Checked By          | Description |
|-----|------------|---------------------|-------------|
| FR1 | functional | `tb_crc16.v`        | Reset behavior: `crc_out` must equal `16'hFFFF` in the same cycle `rst_n` is sampled low. |
| FR2 | functional | `tb_crc16.v`        | Known-answer test for message `0x31` (MSB-first, 8 bits). After shifting and holding enable low, `crc_out` must be `16'hC0A7`. |
| FR3 | functional | `tb_crc16.v`        | Known-answer test for message `0x1234` (MSB-first, 16 bits). After shifting and holding enable low, `crc_out` must be `16'hDFB3`. |
| FR4 | functional | `evaluate.py`       | Synthesizability / compilability: the submitted `recovered_rtl.v` must compile with iverilog without errors. |
| SR1 | security   | `tb_crc16.v` + `private/tb_sr1_vectors.v` | Functional equivalence over all public and private test vectors. The DUT must match the reference CRC-16/CCITT-FALSE model cycle by cycle on every vector. |

## PASS / FAIL Marker Protocol

The testbench prints markers in the format:

```
[TEST] PASS: <requirement_id>
[TEST] FAIL: <requirement_id>: <brief reason>
```

`evaluate.py` reads these lines, maps them to the requirement IDs above, and re-emits them as the final grading output. If a marker for a requirement is missing (e.g., due to a simulation crash), `evaluate.py` emits a `FAIL` marker with an appropriate reason.

## Entry Point

Run grading with:

```
python3 evaluation/evaluate.py
```

All paths are relative to the repository root. The script expects `submission/recovered_rtl.v` to exist and `inputs/crc16_netlist.v` to be present (though the netlist is not used during grading — grading is purely behavioral against the reference model).