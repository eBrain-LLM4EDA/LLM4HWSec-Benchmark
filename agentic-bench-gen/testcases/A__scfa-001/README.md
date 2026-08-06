# Side-Channel Analysis: Masked S-Box Leakage Detection

## Objective

You are given a Verilog RTL implementation of a first-order masked AES S-box and a description of the power leakage model. The design uses two random shares to protect a sensitive intermediate value during the S-box computation. However, at one point in the pipeline the two shares are recombined in a single cycle, creating a first-order switching leakage point.

Your task is to analyze the provided artifacts and identify:

1. The exact hierarchical net where the two shares are recombined.
2. The exact hierarchical register that captures the recombined value.
3. A brief description of the leakage mechanism.

## Input Artifacts

All input files are located in the `inputs/` directory:

- `masked_sbox.v` – Synthesizable Verilog RTL of the masked S-box. The design contains registered pipeline stages, separate share registers, and a recombination stage.
- `leakage_model.txt` – Description of the power leakage model used for the analysis (Hamming-distance based).

## Output

You must produce a single JSON file at `submission/vulnerability_report.json` with the following structure:

```json
{
  "recombination_net": "<hierarchical net name>",
  "recombination_register": "<hierarchical register name>",
  "leakage_type": "<brief description of leakage mechanism>"
}
```

All three fields are required and must contain non-empty string values. The net and register names must be valid hierarchical identifiers present in the provided RTL netlist.

## Constraints

- The RTL implements a first-order masked S-box with two random shares and registered nonlinear processing.
- The leakage model is Hamming-distance based: power consumption is proportional to the Hamming distance between successive register values or the Hamming weight of glitch-prone combinatorial nets.
- Your analysis should focus on identifying the exact point where the two individually masked shares are recombined, not on isolated share registers.

## Submission

Place your completed `vulnerability_report.json` in the `submission/` directory. The file will be evaluated against the ground truth for correctness of the identified net, register, and leakage type.