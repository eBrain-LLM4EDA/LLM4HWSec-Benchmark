`timescale 1ns/1ps

//
// primitive_cells.v
//
// Small behavioral standard-cell library used by inputs/netlist.v.
// Each cell is a pure combinational primitive with a fixed pinout:
//   - single-input cells expose ports .A, .Y
//   - two-input cells expose ports .A, .B, .Y
//
// These models are purely functional (behavioral) and are not meant to
// represent any particular physical library; they exist only so that
// inputs/netlist.v can be elaborated and simulated standalone with
// iverilog/vvp.
//

module BUF1 (
    input  A,
    output Y
);
    assign Y = A;
endmodule

module INV1 (
    input  A,
    output Y
);
    assign Y = ~A;
endmodule

module AND2 (
    input  A,
    input  B,
    output Y
);
    assign Y = A & B;
endmodule

module OR2 (
    input  A,
    input  B,
    output Y
);
    assign Y = A | B;
endmodule

module XOR2 (
    input  A,
    input  B,
    output Y
);
    assign Y = A ^ B;
endmodule

module XNOR2 (
    input  A,
    input  B,
    output Y
);
    assign Y = A ^ ~B;
endmodule

module NAND2 (
    input  A,
    input  B,
    output Y
);
    assign Y = ~(A & B);
endmodule

module NOR2 (
    input  A,
    input  B,
    output Y
);
    assign Y = ~(A | B);
endmodule