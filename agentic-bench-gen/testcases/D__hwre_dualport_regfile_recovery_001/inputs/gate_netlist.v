// ---------------------------------------------------------------------------
// gate_netlist.v
//
// Flattened gate-level rendition of a small 4-entry x 8-bit storage block.
// This is the output of a synthesis flattening pass: individual flip-flops,
// an address decoder, and read-side multiplexer trees, all expressed with
// primitive gates. No external cell library is required -- every primitive
// used here is declared locally in this file.
//
// Port list intentionally mirrors reg_file_recovered so that this netlist
// can be dropped in wherever the word-level block was expected.
// ---------------------------------------------------------------------------

`timescale 1ns/1ps

// ---------------------------------------------------------------------------
// Primitive gate models
// ---------------------------------------------------------------------------

module INV (input a, output y);
    assign y = ~a;
endmodule

module AND2 (input a, input b, output y);
    assign y = a & b;
endmodule

module OR2 (input a, input b, output y);
    assign y = a | b;
endmodule

module AND3 (input a, input b, input c, output y);
    assign y = a & b & c;
endmodule

// 2-to-1 mux, select s chooses b when s=1 else a
module MUX2 (input a, input b, input s, output y);
    assign y = s ? b : a;
endmodule

// Positive-edge triggered D flip-flop with synchronous, active-high
// clear input (clr takes priority over d).
module DFF_P (input clk, input clr, input d, output reg q);
    always @(posedge clk) begin
        if (clr)
            q <= 1'b0;
        else
            q <= d;
    end
endmodule

// ---------------------------------------------------------------------------
// Top-level flattened netlist
// ---------------------------------------------------------------------------

module gate_netlist_regfile (
    input        clk,
    input        rst,
    input        we,
    input  [1:0] waddr,
    input  [7:0] wdata,
    input  [1:0] raddr0,
    input  [1:0] raddr1,
    output [7:0] rdata0,
    output [7:0] rdata1
);

    // -----------------------------------------------------------------
    // 2-to-4 one-hot write address decoder, gated by write-enable.
    // sel[i] is high exactly when we=1 and waddr==i.
    // -----------------------------------------------------------------
    wire n_waddr0, n_waddr1;
    INV inv_wa0 (.a(waddr[0]), .y(n_waddr0));
    INV inv_wa1 (.a(waddr[1]), .y(n_waddr1));

    wire dec0, dec1, dec2, dec3;
    AND2 dec_and0 (.a(n_waddr1), .b(n_waddr0), .y(dec0)); // waddr == 00
    AND2 dec_and1 (.a(n_waddr1), .b(waddr[0]), .y(dec1)); // waddr == 01
    AND2 dec_and2 (.a(waddr[1]), .b(n_waddr0), .y(dec2)); // waddr == 10
    AND2 dec_and3 (.a(waddr[1]), .b(waddr[0]), .y(dec3)); // waddr == 11

    wire sel0, sel1, sel2, sel3;
    AND2 sel_and0 (.a(dec0), .b(we), .y(sel0));
    AND2 sel_and1 (.a(dec1), .b(we), .y(sel1));
    AND2 sel_and2 (.a(dec2), .b(we), .y(sel2));
    AND2 sel_and3 (.a(dec3), .b(we), .y(sel3));

    // -----------------------------------------------------------------
    // Per-entry D input selection: each entry's flip-flop input is
    // wdata[bit] when that entry is selected for write, else its own
    // current stored value (feedback), giving a hold-otherwise-load
    // behavior. Synchronous reset (clr) is wired straight into each
    // DFF_P and takes priority over the loaded value.
    // -----------------------------------------------------------------
    wire [7:0] q0, q1, q2, q3;
    wire [7:0] d0, d1, d2, d3;

    genvar gi;
    generate
        for (gi = 0; gi < 8; gi = gi + 1) begin : entry_bits
            MUX2 mux_d0 (.a(q0[gi]), .b(wdata[gi]), .s(sel0), .y(d0[gi]));
            MUX2 mux_d1 (.a(q1[gi]), .b(wdata[gi]), .s(sel1), .y(d1[gi]));
            MUX2 mux_d2 (.a(q2[gi]), .b(wdata[gi]), .s(sel2), .y(d2[gi]));
            MUX2 mux_d3 (.a(q3[gi]), .b(wdata[gi]), .s(sel3), .y(d3[gi]));

            DFF_P dff0 (.clk(clk), .clr(rst), .d(d0[gi]), .q(q0[gi]));
            DFF_P dff1 (.clk(clk), .clr(rst), .d(d1[gi]), .q(q1[gi]));
            DFF_P dff2 (.clk(clk), .clr(rst), .d(d2[gi]), .q(q2[gi]));
            DFF_P dff3 (.clk(clk), .clr(rst), .d(d3[gi]), .q(q3[gi]));
        end
    endgenerate

    // -----------------------------------------------------------------
    // Read port 0: 4-to-1, 8-bit-wide combinational multiplexer tree
    // built from 2-to-1 mux primitives, selecting on raddr0.
    // -----------------------------------------------------------------
    wire [7:0] r0_lo, r0_hi;
    generate
        for (gi = 0; gi < 8; gi = gi + 1) begin : rp0_bits
            MUX2 rp0_lo (.a(q0[gi]), .b(q1[gi]), .s(raddr0[0]), .y(r0_lo[gi]));
            MUX2 rp0_hi (.a(q2[gi]), .b(q3[gi]), .s(raddr0[0]), .y(r0_hi[gi]));
            MUX2 rp0_out(.a(r0_lo[gi]), .b(r0_hi[gi]), .s(raddr0[1]), .y(rdata0[gi]));
        end
    endgenerate

    // -----------------------------------------------------------------
    // Read port 1: identical 4-to-1, 8-bit-wide multiplexer tree,
    // fully independent of read port 0, selecting on raddr1.
    // -----------------------------------------------------------------
    wire [7:0] r1_lo, r1_hi;
    generate
        for (gi = 0; gi < 8; gi = gi + 1) begin : rp1_bits
            MUX2 rp1_lo (.a(q0[gi]), .b(q1[gi]), .s(raddr1[0]), .y(r1_lo[gi]));
            MUX2 rp1_hi (.a(q2[gi]), .b(q3[gi]), .s(raddr1[0]), .y(r1_hi[gi]));
            MUX2 rp1_out(.a(r1_lo[gi]), .b(r1_hi[gi]), .s(raddr1[1]), .y(rdata1[gi]));
        end
    endgenerate

endmodule