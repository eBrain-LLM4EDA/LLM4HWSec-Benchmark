# Reverse Engineering Challenge: Synchronous FIFO Controller

## Objective

You are given a flattened gate-level Verilog netlist (`inputs/fifo_netlist.v`) that implements a synchronous FIFO (First-In, First-Out) buffer. Your task is to reverse-engineer the netlist and produce a readable, synthesizable RTL description of the same design.

The FIFO has the following known characteristics:
- **Depth:** 4 entries
- **Width:** 8 bits per entry
- **Reset:** Synchronous, active-high
- **Output timing:** All outputs are Moore-type (functions of registered state only)

## Input Artifact

- `inputs/fifo_netlist.v` – A flattened gate-level netlist using only DFFs, multiplexers, and basic gates (AND, OR, NOT, XOR). The module name is `fifo_controller` and it contains no hierarchy.

## Submission

Place your reconstructed RTL in a single Verilog file at:

```
submission/recovered_rtl.v
```

The file must contain a module named `fifo_controller` with the exact port list specified below. No external dependencies are allowed; the file must be self-contained and synthesizable.

## Module Interface

```verilog
module fifo_controller (
    input         clk,
    input         rst,          // synchronous, active-high
    input  [7:0]  write_data,
    input         write_en,
    input         read_en,
    output [7:0]  read_data,
    output        full,
    output        empty
);
```

## Timing Contract

The design follows a strict cycle-accurate timing contract. Your submission must match this behavior exactly.

- **Reset:** When `rst` is high at a rising clock edge, the FIFO is cleared. On the **next** rising edge after `rst` is released (i.e., `rst` is low), `empty` is high, `full` is low, and `read_data` holds 0.
- **Read latency:** When a read is accepted (`read_en` high and `empty` low at a rising edge), the oldest stored data appears on `read_data` on the **next** rising edge of `clk` (1 cycle latency).
- **Full flag:** Asserts on the rising edge **following** the cycle in which the fourth write is accepted (occupancy transitions from 3 to 4). Deasserts on the rising edge **following** the cycle in which a read is accepted while full.
- **Empty flag:** Asserts on the rising edge **following** the cycle in which the last entry is read (occupancy transitions from 1 to 0). Deasserts on the rising edge **following** the cycle in which a write is accepted while empty.
- All outputs are Moore-type: they depend only on the current registered state, not directly on the current inputs.

## Functional Requirements

Your RTL must implement the following behavior:

1. **FR1 – Write when empty:** When `empty` is high and `write_en` is high at a rising edge, the FIFO accepts `write_data` and `empty` deasserts on the next rising edge.
2. **FR2 – Read when full:** When `full` is high and `read_en` is high at a rising edge, the FIFO presents the oldest stored data on `read_data` on the next rising edge, and `full` deasserts on that same next rising edge.
3. **FR3 – Simultaneous read/write:** When `write_en` and `read_en` are both high and the FIFO is neither full nor empty, both operations complete: new data is stored, the oldest data is output on `read_data` on the next rising edge, and occupancy remains unchanged.
4. **FR4 – Overflow/Underflow protection:** A `write_en` when `full` is high, or a `read_en` when `empty` is high, must not alter the FIFO state or output; `read_data` retains its previous value.

## Constraints

- Single Verilog file with no external dependencies.
- The module must be synthesizable (compatible with standard RTL synthesis tools).
- The port list and module name must match exactly as specified above.

## Evaluation

Your submission will be evaluated by cycle-accurate simulation against a reference model. The primary metric is **functional equivalence** – a binary pass/fail indicating whether your design's outputs match the reference cycle-by-cycle over a comprehensive testbench.