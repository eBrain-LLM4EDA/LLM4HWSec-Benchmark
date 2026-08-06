// ---------------------------------------------------------------------------
// recovered_rtl.v
//
// Starter answer (placeholder). Replace this with a real recovered
// implementation of the storage block described in inputs/design_brief.md.
// ---------------------------------------------------------------------------

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

    assign rdata0 = 8'h00;
    assign rdata1 = 8'h00;

endmodule