// gate_library.v
//
// Structural primitive gate wrapper library used by decoder_netlist.v.
// Each wrapper is a thin structural shim around a native Verilog gate
// primitive (or, in the case of GATE_DFF_EN, a simple synchronous register
// description). No behavioral decode logic lives in this file; it exists
// purely to give the netlist named, reusable cell instances with clear
// port names.
//
// Compiles standalone with: iverilog -g2012 gate_library.v

`timescale 1ns/1ps

// 2-input AND gate
module GATE_AND2 (
    input  wire a,
    input  wire b,
    output wire y
);
    and (y, a, b);
endmodule

// 3-input AND gate
module GATE_AND3 (
    input  wire a,
    input  wire b,
    input  wire c,
    output wire y
);
    and (y, a, b, c);
endmodule

// 2-input OR gate
module GATE_OR2 (
    input  wire a,
    input  wire b,
    output wire y
);
    or (y, a, b);
endmodule

// 3-input OR gate
module GATE_OR3 (
    input  wire a,
    input  wire b,
    input  wire c,
    output wire y
);
    or (y, a, b, c);
endmodule

// Inverter
module GATE_NOT (
    input  wire a,
    output wire y
);
    not (y, a);
endmodule

// D flip-flop with synchronous enable and synchronous active-high reset.
// q is updated on the rising edge of clk:
//   - if rst is high, q <= 0
//   - else if en is high, q <= d
//   - else q holds its previous value
module GATE_DFF_EN (
    input  wire d,
    input  wire clk,
    input  wire en,
    input  wire rst,
    output reg  q
);
    always @(posedge clk) begin
        if (rst)
            q <= 1'b0;
        else if (en)
            q <= d;
        else
            q <= q;
    end
endmodule