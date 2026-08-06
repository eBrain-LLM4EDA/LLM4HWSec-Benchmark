// Gate-level netlist: scan_controller
// This module implements a simple scan-chain controller with a documented test_mode input.
// It uses only primitive gates (AND, OR, NOT, NAND, NOR, XOR, XNOR, BUF) and DFFs.
// The design includes scan multiplexers and scan_enable logic that exhibits naturally low
// switching activity under functional mode (test_mode=0).

module scan_controller (
    input  wire clk,
    input  wire rst_n,
    input  wire test_mode,
    input  wire scan_in,
    input  wire [3:0] data_in,
    output wire [3:0] data_out,
    output wire scan_out
);

    // Internal wires
    wire scan_enable;
    wire [3:0] scan_mux_out;
    wire [3:0] dff_q;
    wire [3:0] dff_d;
    wire [3:0] next_scan_chain;
    wire [3:0] scan_chain;

    // Scan enable generation: scan_enable = test_mode
    BUF u_scan_en_buf (.I(test_mode), .O(scan_enable));

    // Scan multiplexers: for each bit, select between data_in and scan chain input
    // Bit 0
    MUX2 u_mux0 (.A(data_in[0]), .B(scan_in), .S(scan_enable), .Y(scan_mux_out[0]));
    // Bits 1-3: scan chain input comes from previous DFF output
    MUX2 u_mux1 (.A(data_in[1]), .B(dff_q[0]), .S(scan_enable), .Y(scan_mux_out[1]));
    MUX2 u_mux2 (.A(data_in[2]), .B(dff_q[1]), .S(scan_enable), .Y(scan_mux_out[2]));
    MUX2 u_mux3 (.A(data_in[3]), .B(dff_q[2]), .S(scan_enable), .Y(scan_mux_out[3]));

    // D-type flip-flops with asynchronous reset (active low)
    DFF u_dff0 (.D(scan_mux_out[0]), .CLK(clk), .RST_N(rst_n), .Q(dff_q[0]));
    DFF u_dff1 (.D(scan_mux_out[1]), .CLK(clk), .RST_N(rst_n), .Q(dff_q[1]));
    DFF u_dff2 (.D(scan_mux_out[2]), .CLK(clk), .RST_N(rst_n), .Q(dff_q[2]));
    DFF u_dff3 (.D(scan_mux_out[3]), .CLK(clk), .RST_N(rst_n), .Q(dff_q[3]));

    // Output assignment: data_out = dff_q
    BUF u_out0 (.I(dff_q[0]), .O(data_out[0]));
    BUF u_out1 (.I(dff_q[1]), .O(data_out[1]));
    BUF u_out2 (.I(dff_q[2]), .O(data_out[2]));
    BUF u_out3 (.I(dff_q[3]), .O(data_out[3]));

    // Scan out: last DFF output
    BUF u_scan_out (.I(dff_q[3]), .O(scan_out));

endmodule

// Primitive gate models (behavioral, for simulation only)
// These are not part of the netlist but are required for iverilog to elaborate.
// In a real gate-level netlist, these would be replaced by standard cell instances.

module BUF (input I, output O);
    assign O = I;
endmodule

module NOT (input I, output O);
    assign O = ~I;
endmodule

module AND2 (input A, B, output O);
    assign O = A & B;
endmodule

module OR2 (input A, B, output O);
    assign O = A | B;
endmodule

module NAND2 (input A, B, output O);
    assign O = ~(A & B);
endmodule

module NOR2 (input A, B, output O);
    assign O = ~(A | B);
endmodule

module XOR2 (input A, B, output O);
    assign O = A ^ B;
endmodule

module XNOR2 (input A, B, output O);
    assign O = ~(A ^ B);
endmodule

module MUX2 (input A, B, S, output O);
    assign O = S ? B : A;
endmodule

module DFF (input D, CLK, RST_N, output reg Q);
    always @(posedge CLK or negedge RST_N) begin
        if (!RST_N)
            Q <= 1'b0;
        else
            Q <= D;
    end
endmodule