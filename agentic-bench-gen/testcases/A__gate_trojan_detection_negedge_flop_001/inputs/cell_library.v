// cell_library.v
// Reusable standard-cell style primitive library.
// Provides basic sequential and combinational building blocks used
// throughout the access-control design and its testbenches.

`timescale 1ns/1ps

// -----------------------------------------------------------------------
// Sequential primitives
// -----------------------------------------------------------------------

// Positive-edge triggered D flip-flop with asynchronous active-low reset.
module DFF_POSEDGE (
    input  wire clk,
    input  wire d,
    output reg  q,
    input  wire rst_n
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q <= 1'b0;
        else
            q <= d;
    end
endmodule

// Negative-edge triggered D flip-flop with asynchronous active-low reset.
module DFF_NEGEDGE (
    input  wire clk,
    input  wire d,
    output reg  q,
    input  wire rst_n
);
    always @(negedge clk or negedge rst_n) begin
        if (!rst_n)
            q <= 1'b0;
        else
            q <= d;
    end
endmodule

// -----------------------------------------------------------------------
// Combinational primitives
// -----------------------------------------------------------------------

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

module NAND2 (
    input  wire a,
    input  wire b,
    output wire y
);
    assign y = ~(a & b);
endmodule

module NOR2 (
    input  wire a,
    input  wire b,
    output wire y
);
    assign y = ~(a | b);
endmodule

module XOR2 (
    input  wire a,
    input  wire b,
    output wire y
);
    assign y = a ^ b;
endmodule

module INV (
    input  wire a,
    output wire y
);
    assign y = ~a;
endmodule

module MUX2 (
    input  wire a,
    input  wire b,
    input  wire sel,
    output wire y
);
    assign y = sel ? b : a;
endmodule