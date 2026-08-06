// primitive_library.v
// Basic combinational gate primitives used to build the isolation_wrapper
// gate-level netlist. Each primitive has named ports (a, b, sel, y) and is
// implemented as a simple continuous assignment.

`timescale 1ns/1ps

module AND2 (
    input  wire a,
    input  wire b,
    output wire y
);
    assign y = a & b;
endmodule

module OR2 (
    input  wire a,
    input  wire b,
    output wire y
);
    assign y = a | b;
endmodule

module MUX2 (
    input  wire sel,
    input  wire a,
    input  wire b,
    output wire y
);
    // sel = 0 -> y = a
    // sel = 1 -> y = b
    assign y = sel ? b : a;
endmodule