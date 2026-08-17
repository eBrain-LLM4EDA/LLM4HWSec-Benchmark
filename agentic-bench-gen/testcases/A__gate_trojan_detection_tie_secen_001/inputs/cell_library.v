// cell_library.v
//
// Minimal structural gate/cell library used by controller_netlist.v.
// All cells are purely combinational or simple synchronous-reset
// flip-flops with zero delay modeling (functional models only, no
// timing information).
//
// Module / port order conventions (must match instantiations exactly):
//   AND2(o, a, b)        - o = a & b
//   OR2 (o, a, b)        - o = a | b
//   INV (o, a)           - o = ~a
//   BUF (o, a)           - o = a
//   DFF (q, d, clk, rst) - synchronous-reset flop, active-high reset
//   TIEHI(o)             - o = 1'b1 (constant driver)
//   TIELO(o)             - o = 1'b0 (constant driver)
//   MUX2(o, a, b, sel)   - o = sel ? b : a

`timescale 1ns/1ps

module AND2 (
    output o,
    input  a,
    input  b
);
    assign o = a & b;
endmodule

module OR2 (
    output o,
    input  a,
    input  b
);
    assign o = a | b;
endmodule

module INV (
    output o,
    input  a
);
    assign o = ~a;
endmodule

module BUF (
    output o,
    input  a
);
    assign o = a;
endmodule

module DFF (
    output reg q,
    input      d,
    input      clk,
    input      rst
);
    always @(posedge clk) begin
        if (rst)
            q <= 1'b0;
        else
            q <= d;
    end
endmodule

module TIEHI (
    output o
);
    assign o = 1'b1;
endmodule

module TIELO (
    output o
);
    assign o = 1'b0;
endmodule

module MUX2 (
    output o,
    input  a,
    input  b,
    input  sel
);
    assign o = sel ? b : a;
endmodule