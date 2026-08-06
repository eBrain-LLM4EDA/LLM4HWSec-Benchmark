# Reverse CRC-16 Serial Generator

## Objective

You are given a flattened gate-level Verilog netlist (`inputs/crc16_netlist.v`) that implements a serial CRC-16 generator. Your task is to **reverse-engineer** the design and produce a functionally equivalent, synthesizable RTL description.

The netlist contains only XOR gates and D-type flip-flops with a synchronous reset. It reveals **nothing** about the polynomial, initial seed value, bit ordering, or output convention. You must deduce these properties from the gate-level connectivity and reproduce the exact cycle-accurate behavior in your own Verilog module.

## Deliverable

Place your solution in a single file:

```
submission/recovered_rtl.v
```

The file must contain a module with the **exact** name and port list shown below. No other files are accepted.

## Interface

```verilog
module crc16_serial (
    input  wire        clk,
    input  wire        rst_n,      // synchronous active-low reset
    input  wire        enable,
    input  wire        data_in,    // serial bit, MSB-first per message
    output wire [15:0] crc_out
);
```

## Timing Contract

Your module must obey the following cycle-accurate behaviour:

- **Reset:** `rst_n` is sampled on the rising edge of `clk`. When `rst_n` is low (reset asserted), the internal CRC state must return to the seed value **in the same cycle**, and `crc_out` must reflect that seed state on that same rising edge.
- **Update:** On a rising edge where `rst_n` is high and `enable` is high, `data_in` is sampled and the CRC state updates. `crc_out` reflects the **new** state on that same rising edge (Moore-type output — it is a registered output of the current state).
- **Hold:** On a rising edge where `rst_n` is high and `enable` is low, the state holds and `crc_out` remains stable.
- **Latency:** `crc_out` is always the current CRC state. There is no additional pipeline latency or handshake. The output changes exactly one cycle after the input that caused the transition.

## Functional Requirements

Your `crc16_serial` module must satisfy the following checks:

| ID  | Requirement |
|-----|-------------|
| FR1 | When reset (`rst_n = 0`) is sampled at a rising clock edge, `crc_out` must equal `16'hFFFF` in the same cycle. |
| FR2 | For the 8-bit message `0x31` (MSB-first, `8'b00110001`), after shifting in all 8 bits with `enable = 1` and then holding `enable = 0`, `crc_out` must equal `16'hC0A7`. |
| FR3 | For the 16-bit message `0x1234` (MSB-first), after shifting in all 16 bits with `enable = 1` and then holding `enable = 0`, `crc_out` must equal `16'hDFB3`. |
| FR4 | The module must compile without errors using `iverilog` and must be synthesizable (no simulation-only constructs such as `$display`, `initial`, `fork`, etc.). |

## Constraints

- Use only synthesizable Verilog constructs.
- The module must compile cleanly with `iverilog -g2012`.
- Do **not** instantiate the provided netlist; write your own RTL from scratch.
- The submitted file must be self-contained (no includes beyond standard Verilog).

## Hints

- Study the XOR/DFF connectivity in `crc16_netlist.v` to identify the feedback taps. These taps encode the CRC polynomial.
- Observe the reset value of each flip-flop to determine the seed.
- Trace the data path to understand whether the input bit is shifted in from the MSB or LSB side, and whether any bit reversal (reflection) is applied.
- The output `crc_out` is taken directly from the flip-flop outputs — there is no final XOR stage.

Good luck!