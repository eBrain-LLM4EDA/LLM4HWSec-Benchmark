# Higher-Order Leakage Analysis of a Masked Datapath

## Objective

You are given a synthesizable Verilog RTL design (`masked_datapath.v`) that implements a two-share masked datapath with multiple pipeline stages. The design uses two independent shares (`share0` and `share1`) to protect a secret value. Your task is to analyze the RTL and identify a **pair of share registers** whose **combined transitions** leak information about the unmasked value, even though each register appears safe when analyzed individually.

## Input Artifacts

All input files are located in the `inputs/` directory:

- **`masked_datapath.v`** – The RTL design under analysis. It contains a two-share masked datapath with pipeline registers. The module hierarchy uses standard Verilog nested instances.
- **`leakage_models.json`** – Defines the leakage models to use during analysis:
  - `first_order_hamming_distance` – Models single-register transitions as the Hamming distance between consecutive values. Use this for individual first-order analysis.
  - `pairwise_hamming_distance` – Models joint transitions of register pairs as the sum of their individual Hamming distances. Use this for second-order analysis.

## Constraints

- The RTL contains a two-share masked datapath with multiple pipeline stages.
- The `leakage_models.json` file defines both first-order and pairwise Hamming-distance leakage models.
- Your analysis must consider the **temporal alignment** of register updates (i.e., whether two registers update in the same clock cycle).

## Submission

You must submit a single file named `vulnerability_report.json` in the `submission/` directory. The file must be valid JSON and conform to the schema described below.

### Report Schema

```json
{
  "leaking_register_pair": ["<hierarchical_signal_name_1>", "<hierarchical_signal_name_2>"],
  "alignment_condition": "<string describing the temporal condition>",
  "first_order_analysis": [
    {
      "register": "<hierarchical_signal_name>",
      "safe": true
    },
    {
      "register": "<hierarchical_signal_name>",
      "safe": true
    }
  ],
  "second_order_analysis": {
    "leaking": true,
    "explanation": "<string explaining why the joint transition leaks>"
  }
}
```

**Required fields:**

- **`leaking_register_pair`** – An array of exactly two strings. Each string must be the hierarchical signal name of a register present in the RTL (e.g., `"top.u_dut.share0_stage2_q"`).
- **`alignment_condition`** – A string describing the temporal condition under which the joint transition leaks (e.g., `"both registers update on the same clock cycle"`).
- **`first_order_analysis`** – An array of objects, each with:
  - `register` (string) – The hierarchical signal name of a register.
  - `safe` (boolean) – `true` if the register appears safe under individual first-order Hamming-distance analysis, `false` otherwise.
  The array must contain entries for at least the two registers in the leaking pair.
- **`second_order_analysis`** – An object with:
  - `leaking` (boolean) – `true` if the joint transition of the pair leaks information.
  - `explanation` (string) – A non-empty explanation of why the joint transition leaks.

## Getting Started

A starter `vulnerability_report.json` is provided in the `submission/` directory. Replace it with your analysis results. The starter file is intentionally incomplete and will not pass evaluation.