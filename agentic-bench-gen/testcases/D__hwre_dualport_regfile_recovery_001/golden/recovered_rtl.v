// ---------------------------------------------------------------------------
// recovered_rtl.v
//
// Word-level recovery of the flattened 4-entry x 8-bit dual-read register
// file described in design_brief.md / gate_netlist.v / obfuscated_wrapper.v.
//
// - Single synchronous write port: on posedge clk, if rst is asserted the
//   entire array clears to 0 (synchronous, active-high, takes priority over
//   we); else if we is asserted, mem[waddr] is loaded with wdata. Exactly
//   one entry updates per qualifying edge; the other three hold.
// - Two fully independent, purely combinational read ports: rdata0/rdata1
//   are direct, zero-latency reflections of mem[raddr0]/mem[raddr1]. No
//   extra pipeline register and no explicit bypass mux are needed: because
//   the read is combinational on the same register array that the clocked
//   write updates, the read output naturally shows the old value up to the
//   edge and the new value from that same edge onward (write-forwarding is
//   inherent, not synthesized separately).
// ---------------------------------------------------------------------------

`timescale 1ns/1ps

module reg_file_recovered (
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

    reg [7:0] mem [0:3];

    integer i;

    always @(posedge clk) begin
        if (rst) begin
            for (i = 0; i < 4; i = i + 1) begin
                mem[i] <= 8'h00;
            end
        end
        else if (we) begin
            mem[waddr] <= wdata;
        end
    end

    assign rdata0 = mem[raddr0];
    assign rdata1 = mem[raddr1];

endmodule