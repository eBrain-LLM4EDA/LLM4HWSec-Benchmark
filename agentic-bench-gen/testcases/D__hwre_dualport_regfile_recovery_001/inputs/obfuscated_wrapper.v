// ---------------------------------------------------------------------------
// obfuscated_wrapper.v
//
// Thin pass-through shell around the flattened gate-level netlist
// (gate_netlist_regfile, defined in gate_netlist.v). This wrapper performs
// no functional transformation of its own -- it simply re-labels every
// internal wire with a meaningless name before handing it to the gate-level
// instance, matching how this block's boundary appears once embedded in a
// larger flattened design. The true word-level structure and timing must be
// inferred from simulated behavior, not from any of these names.
// ---------------------------------------------------------------------------

`timescale 1ns/1ps

module obfuscated_wrapper (
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

    wire        _n42;
    wire        sig_a3;
    wire        tmp_x7;
    wire [1:0]  wire_b12;
    wire [7:0]  tmp_x8;
    wire [1:0]  sig_c4;
    wire [1:0]  sig_c5;
    wire [7:0]  _n99;
    wire [7:0]  _n100;

    assign _n42     = clk;
    assign sig_a3    = rst;
    assign tmp_x7    = we;
    assign wire_b12   = waddr;
    assign tmp_x8    = wdata;
    assign sig_c4    = raddr0;
    assign sig_c5    = raddr1;
    assign rdata0    = _n99;
    assign rdata1    = _n100;

    gate_netlist_regfile core_blk_u1 (
        .clk    (_n42),
        .rst    (sig_a3),
        .we     (tmp_x7),
        .waddr  (wire_b12),
        .wdata  (tmp_x8),
        .raddr0 (sig_c4),
        .raddr1 (sig_c5),
        .rdata0 (_n99),
        .rdata1 (_n100)
    );

endmodule