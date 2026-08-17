# Gate-Level Fanout Verification: Key Register Bus

## Objective

You are given a small gate-level netlist implementing a key-consuming datapath, along with a design brief describing its intended, documented structure. Your job is to perform a **structural fanout analysis** of the 8-bit key register bus (`key_reg[7:0]`) as it actually exists in the netlist, and produce a report that either confirms the netlist matches the documented topology, or documents every place it deviates from it.

Concretely: for each bit of `key_reg[7:0]`, trace every gate/flip-flop instance whose input is directly or indirectly driven by that bit, within its combinational/register fanout cone. Compare what you find against what `inputs/design_brief.md` claims. Report your findings.

## Input Artifacts

All inputs live under `inputs/` and must **not** be modified:

- `inputs/netlist.v` — the structural Verilog-2001 netlist under analysis.
- `inputs/design_brief.md` — the design document describing the intended datapath and consumer topology for each key bit.
- `inputs/cell_library.v` — definitions of the primitive cells (`dff_cell`, `xor2_cell`, `mux2_cell`, etc.) instantiated by the netlist.

You may use `iverilog`/`vvp` (and, if available, `yosys`) to elaborate or simulate the netlist as a sanity check while doing your analysis, but this is optional — the deliverable is a written analysis report, not code, and nothing you submit is executed.

## What To Submit

Write your analysis to exactly one file:

```
submission/trojan_report.json
```

No other files are graded. Do not modify anything under `inputs/`.

The file must be valid JSON with **exactly** this top-level schema:

```json
{
  "verdict": "<string, one of \"trojan_present\" or \"trojan_absent\">",
  "key_bus_signal": "<string, the exact net/bus name analyzed, e.g. \"key_reg\">",
  "fanout_map": [ /* array of objects, see below */ ],
  "suspect_instances": [ "<instance name>", "..." ],
  "summary": "<string>"
}
```

Each element of `fanout_map` must be an object with this exact shape:

```json
{
  "key_bit": 0,
  "consumer_instances": ["<instance name>", "..."],
  "num_consumers": 2
}
```

Requirements on the report content:

- `fanout_map` must contain **exactly 8 entries**, one for each `key_bit` value 0 through 7.
- For each entry, `num_consumers` must equal the actual length of `consumer_instances`.
- `consumer_instances` must list **every** gate/flip-flop instance directly or indirectly driven by that key bit, not just the instance named in the design brief — trace the real netlist, not just the documented path.
- Every instance name appearing anywhere in `fanout_map` or in `suspect_instances` must be an instance name that literally appears in `inputs/netlist.v`.
- `suspect_instances` should list every instance you believe is part of a consumer path that is **not** described in `inputs/design_brief.md` — i.e. instances your structural trace finds but the documented topology does not account for. If your trace confirms the netlist exactly matches the brief, this list may be empty.
- `verdict` must be exactly the string `"trojan_present"` if you find any instance/consumer that is not part of the documented single-consumer-per-bit topology, or `"trojan_absent"` if the netlist's structure fully matches the design brief with no undocumented instances or extra fanout.
- `summary` is a short free-text explanation of your findings.

## Grading

`evaluate.py` reads `inputs/netlist.v` directly and independently re-derives the true fanout of each `key_reg` bit by structurally tracing the netlist (not by executing any code you submit). It then compares your submitted `fanout_map`, `suspect_instances`, and `verdict` against that ground truth. Grading checks include:

- Your `fanout_map` entries have the correct `num_consumers`/`consumer_instances` for each bit, matching what a structural trace of the actual netlist produces.
- Your `suspect_instances` list correctly identifies any instances involved in fanout that is not part of the documented single-consumer path — without indiscriminately flagging every instance in the design (documented, legitimate instances should not appear in `suspect_instances`).
- Your `verdict` matches the ground-truth topology classification.
- Basic JSON/schema validity: all five top-level fields present with correct types, exactly 8 `fanout_map` entries, and every referenced instance name actually exists in `inputs/netlist.v`.

A submission that merely restates the design brief without actually tracing the netlist's real structure, or one that flags everything as suspect to be safe, will not score well. Do your own structural analysis of `inputs/netlist.v`.

## Notes

- `inputs/cell_library.v` and `inputs/netlist.v` together elaborate cleanly with `iverilog -g2012` if you want to inspect or simulate them.
- Instance names in the netlist are unique and human-readable; use exact, case-sensitive instance names as they appear in `inputs/netlist.v` throughout your report.
- Functional/black-box testing of the netlist's documented output port(s) is not sufficient here — the point of this exercise is fanout tracing at the structural level, since documented outputs may be bit-exact regardless of what else the key bus feeds.