# Hardware Reverse Engineering: Pipelined Saturating MAC

## Objective

You are given an obfuscated gate-level netlist (`inputs/obfuscated_mac_netlist.v`) that implements a signed multiply-accumulate (MAC) unit with saturation and a fixed pipeline latency. Your task is to reverse-engineer the netlist and produce a **behavioral RTL description** that is functionally equivalent to the original design.

Submit your recovered RTL as a single SystemVerilog file named `recovered_rtl.v` in the `submission/` directory.

## Input Artifact

- `inputs/obfuscated_mac_netlist.v` – A structural Verilog netlist composed of basic gates (AND, OR, XOR, MUX, DFF) and obfuscated wire/instance names. The netlist contains no behavioral constructs (`always`, `case`, `if`). It instantiates the module `mac_top` with the exact interface described below.

## Required Module Interface

Your `recovered_rtl.v` must define a module named `mac_top` with the following ports:

| Port          | Direction | Width   | Description                                      |
|---------------|-----------|---------|--------------------------------------------------|
| `clk`         | input     | 1       | Clock signal (all sampling on rising edge)       |
| `rst_n`       | input     | 1       | Active-low asynchronous reset                    |
| `a`           | input     | 8       | Signed operand A                                 |
| `b`           | input     | 8       | Signed operand B                                 |
| `valid_in`    | input     | 1       | High when `a` and `b` are valid for a new transaction |
| `result`      | output    | 20      | Signed accumulated result (registered)           |
| `result_valid`| output    | 1       | High for exactly one cycle when `result` is valid |

All ports must be declared as `signed` where applicable.

## Timing and Behavior Contract

Your recovered RTL must adhere to the following cycle-accurate behavior:

1. **Reset**  
   - `rst_n` is active-low and asynchronous.  
   - While `rst_n` is low, `result` must be forced to `20'd0` and `result_valid` to `1'b0` on the next rising edge of `clk`.  
   - After `rst_n` goes high, normal operation begins on the following rising edge.

2. **Input Sampling**  
   - `a`, `b`, and `valid_in` are sampled on the rising edge of `clk`.  
   - A transaction occurs when `valid_in` is high on a rising edge.

3. **Output Latency**  
   - `result` and `result_valid` appear **exactly two rising edges** after the rising edge on which the corresponding `a`, `b`, and `valid_in` were sampled.  
   - `result_valid` is high for exactly one cycle per accepted input.

4. **Arithmetic**  
   - The design computes a running accumulation: `acc = acc + signed(a) * signed(b)`.  
   - The internal accumulator is 20 bits wide.  
   - The result saturates on overflow:  
     - Positive overflow → `result` saturates to `20'h7FFFF` (maximum positive).  
     - Negative overflow → `result` saturates to `20'h80000` (minimum negative).  
   - No wrapping is allowed.

## Example Scenarios

The following examples illustrate the expected behavior. They are not exhaustive and are provided only to clarify the timing and arithmetic.

**Scenario 1: Basic accumulation**  
- Cycle 0: `rst_n` goes high.  
- Cycle 1: `a=8'd5`, `b=8'd3`, `valid_in=1`.  
- Cycle 3: `result=20'd15`, `result_valid=1`.  
- Cycle 4: `a=8'd10`, `b=8'd2`, `valid_in=1`.  
- Cycle 6: `result=20'd35` (15 + 20), `result_valid=1`.

**Scenario 2: Positive saturation**  
- After reset, apply repeated transactions with `a=8'd127`, `b=8'd127`.  
- The accumulator grows until it reaches `20'h7FFFF`.  
- Subsequent transactions keep `result` at `20'h7FFFF` (no wrap to negative).

**Scenario 3: Negative saturation**  
- After reset, apply transactions that drive the accumulator negative (e.g., `a=8'd-128`, `b=8'd127` repeatedly).  
- The accumulator saturates at `20'h80000` and does not wrap to positive.

## Submission

Place your recovered behavioral RTL in `submission/recovered_rtl.v`. The file must compile without errors when analyzed with `iverilog -g2012` together with a testbench that instantiates `mac_top`. Your submission will be evaluated by cycle-accurate simulation against a golden reference model.

Good luck!