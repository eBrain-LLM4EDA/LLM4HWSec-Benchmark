// primitives.v
// Basic gate and flip-flop primitive library used by flattened_netlist.v.
// These modules model a minimal standard-cell-like library: two-input
// NAND/NOR/XOR gates, an inverter, and a synchronously-resettable D
// flip-flop. flattened_netlist.v is built purely out of instances of the
// modules defined here.

`timescale 1ns/1ps

module NAND2(
    input  a,
    input  b,
    output y
);
    assign y = ~(a & b);
endmodule

module NOR2(
    input  a,
    input  b,
    output y
);
    assign y = ~(a | b);
endmodule

module XOR2(
    input  a,
    input  b,
    output y
);
    assign y = a ^ b;
endmodule

module INV(
    input  a,
    output y
);
    assign y = ~a;
endmodule

module DFF(
    input clk,
    input d,
    input rst,
    output reg q
);
    always @(posedge clk) begin
        if (rst)
            q <= 1'b0;
        else
            q <= d;
    end
endmodule