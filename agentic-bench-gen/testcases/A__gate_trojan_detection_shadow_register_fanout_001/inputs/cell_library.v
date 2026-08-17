// cell_library.v
// Basic structural cell library: D flip-flop, 2-input XOR, 2:1 multiplexer.

`timescale 1ns/1ps

module dff_cell (
    input  wire clk,
    input  wire rst_n,
    input  wire d,
    output reg  q
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q <= 1'b0;
        else
            q <= d;
    end
endmodule

module xor2_cell (
    input  wire a,
    input  wire b,
    output wire y
);
    assign y = a ^ b;
endmodule

module mux2_cell (
    input  wire sel,
    input  wire a,
    input  wire b,
    output wire y
);
    assign y = sel ? b : a;
endmodule