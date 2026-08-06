# Gate-Level Trojan Detection: Clean DFT Netlist with Rare Scan Controls

## Objective

Analyze the provided gate-level netlist (`scan_controller.v`) and determine whether it contains any hardware Trojan logic. Submit a structured JSON report identifying any suspect trigger or payload nodes, or declare the netlist clean.

## Input Artifacts

All input files are located under the `inputs/` directory:

- `scan_controller.v` – Gate-level Verilog netlist of a scan-chain controller.
- `design_brief.md` – Functional description of the scan controller module.

## Expected Output

You must produce a single answer file at the following path:

```
submission/trojan_report.json
```

## Report Format

The report must be valid JSON with the following schema:

```json
{
  "infected": <boolean>,
  "trigger_nodes": [<string>, ...],
  "payload_nodes": [<string>, ...]
}
```

- `infected` – `true` if you believe the netlist contains a Trojan, `false` otherwise.
- `trigger_nodes` – Array of node names (strings) that act as Trojan triggers. Must be an empty array if `infected` is `false`.
- `payload_nodes` – Array of node names (strings) that act as Trojan payloads. Must be an empty array if `infected` is `false`.

If `infected` is `true`, both `trigger_nodes` and `payload_nodes` must contain at least one node name each. All node names must be exact hierarchical instance paths or wire names as they appear in the netlist.

## Constraints

- The netlist uses only primitive gates (AND, OR, NOT, NAND, NOR, XOR, XNOR, BUF) and D-type flip-flops (DFF).
- The design includes scan multiplexers and a documented `test_mode` input with naturally low switching activity.
- You must not modify the input artifacts; only the report file is submitted.

## Evaluation

Your submission will be graded on:

- **Detection rate** – Correctly identifying the presence or absence of a Trojan.
- **False positive rate** – Incorrectly flagging clean logic as infected.
- **Inference latency** – Wall-clock time taken to produce the report.

Good luck!