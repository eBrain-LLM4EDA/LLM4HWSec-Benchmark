# Timing Leakage Analysis of an Iterative Divider

## Objective

You are given the RTL of a small iterative unsigned divider (`divider.v`) and a set of timing traces (`timing_traces.txt`). The divider computes `dividend / divisor` using a shift‑subtract algorithm and signals completion via a `done` output.

Your task is to **analyze the provided artifacts** and determine whether the divider’s execution latency varies with the operand values. If you find a variable‑latency source, you must identify the root cause in the RTL and propose a concrete design change that makes the latency fixed.

## Input Artifacts

All input files are located in the `inputs/` directory:

- **`divider.v`** – Verilog‑2001 RTL of the iterative unsigned divider. The module has the following ports:
  - `clk`, `rst_n`
  - `start` (input)
  - `dividend[WIDTH-1:0]`, `divisor[WIDTH-1:0]` (inputs)
  - `done` (output)
  - `quotient[WIDTH-1:0]`, `remainder[WIDTH-1:0]` (outputs)
  - Parameter `WIDTH` is set to 8.

- **`timing_traces.txt`** – A plain‑text file that describes the timing measurement model (cycle count from `start` assertion to `done` assertion) and provides a table of representative operand pairs with their observed cycle counts.

## Submission

You must submit a single file:

```
submission/vulnerability_report.json
```

The file must be a valid JSON object with exactly three top‑level keys:

| Key                    | Type    | Description |
|------------------------|---------|-------------|
| `vulnerability_found`  | boolean | `true` if you identified a variable‑latency source, `false` otherwise. |
| `vulnerable_component` | string  | If `vulnerability_found` is `true`, a string that identifies the specific signal or block in `divider.v` responsible for the variable latency. If `false`, this field must still be present but may be an empty string. |
| `recommended_fix`      | string  | If `vulnerability_found` is `true`, a non‑empty string describing a concrete RTL modification that would make the latency fixed. If `false`, this field must still be present but may be an empty string. |

### Functional Requirements

1. The submitted file must be valid JSON.
2. The `vulnerability_found` field must be a boolean.
3. The `vulnerable_component` field must be a string.
4. The `recommended_fix` field must be a string.

Your analysis must be based **solely** on the provided artifacts.

## Constraints

- The provided RTL is a small iterative unsigned divider with `start`, `done`, `quotient`, and an internal iteration counter.
- The `timing_traces.txt` file contains a timing observation model and traces for operands with different leading‑zero counts.
- You may not modify the input artifacts; only the submission file is evaluated.