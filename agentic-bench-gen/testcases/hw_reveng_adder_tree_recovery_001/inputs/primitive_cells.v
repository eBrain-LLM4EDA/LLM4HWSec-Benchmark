// -----------------------------------------------------------------------------
// primitive_cells.v
//
// Basic combinational primitive cell library used to build
// inputs/flattened_netlist.v. Each cell is a small, purely combinational
// gate or compound gate expressed with a single continuous assignment.
//
// This file is provided as reference material only, so that participants
// can understand what each primitive instance in the flattened netlist
// computes. Do NOT instantiate these primitives directly in your
// submission (submission/recovered_rtl.v) — your recovered design must be
// expressed as word-level RTL, not as a rewiring of this primitive
// library.
// -----------------------------------------------------------------------------

`timescale 1ns/1ps

// 2-input AND gate
module AND2 (
    input  a,
    input  b,
    output y
);
    assign y = a & b;
endmodule

// 2-input OR gate
module OR2 (
    input  a,
    input  b,
    output y
);
    assign y = a | b;
endmodule

// 2-input XOR gate
module XOR2 (
    input  a,
    input  b,
    output y
);
    assign y = a ^ b;
endmodule

// Single-input inverter
module NOT1 (
    input  a,
    output y
);
    assign y = ~a;
endmodule

// 3-input AND gate (used for some carry combinations)
module AND3 (
    input  a,
    input  b,
    input  c,
    output y
);
    assign y = a & b & c;
endmodule

// 3-input OR gate (used for some carry combinations)
module OR3 (
    input  a,
    input  b,
    input  c,
    output y
);
    assign y = a | b | c;
endmodule

// 1-bit full adder cell.
//
// Ports (fixed order, matches instantiations in flattened_netlist.v):
//   a, b   - the two primary bits to add
//   cin    - carry-in bit
//   sum    - sum output bit  (a ^ b ^ cin)
//   cout   - carry-out output bit ( majority(a,b,cin) )
module FA1 (
    input  a,
    input  b,
    input  cin,
    output sum,
    output cout
);
    assign sum  = a ^ b ^ cin;
    assign cout = (a & b) | (b & cin) | (a & cin);
endmodule