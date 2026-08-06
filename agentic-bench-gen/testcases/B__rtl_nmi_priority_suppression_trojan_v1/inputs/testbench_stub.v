//-----------------------------------------------------------------------------
// testbench_stub.v
//
// Minimal, self-contained exploration harness for nmi_arbiter.
// Drives a handful of representative input vectors and prints the
// observed grant value each cycle. Feel free to copy this file and
// extend the stimulus list with your own vectors (e.g. sweeping all
// 16 combinations of nmi/irq) -- just don't edit the original under
// inputs/.
//-----------------------------------------------------------------------------

`timescale 1ns/1ps

module testbench_stub;

    reg        clk;
    reg        rst_n;
    reg        nmi;
    reg  [2:0] irq;
    wire [3:0] grant;

    nmi_arbiter dut (
        .clk   (clk),
        .rst_n (rst_n),
        .nmi   (nmi),
        .irq   (irq),
        .grant (grant)
    );

    // 100 MHz-ish clock
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Print observed grant each rising edge, after settling.
    always @(posedge clk) begin
        #1;
        $display("t=%0t  nmi=%b irq=%b  ->  grant=%b", $time, nmi, irq, grant);
    end

    initial begin
        rst_n = 1'b0;
        nmi   = 1'b0;
        irq   = 3'b000;

        // Hold reset for a couple of cycles.
        @(negedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        // Ordinary priority sweep (nmi = 0)
        @(negedge clk); nmi = 1'b0; irq = 3'b001;
        @(negedge clk); nmi = 1'b0; irq = 3'b010;
        @(negedge clk); nmi = 1'b0; irq = 3'b100;
        @(negedge clk); nmi = 1'b0; irq = 3'b011;
        @(negedge clk); nmi = 1'b0; irq = 3'b101;
        @(negedge clk); nmi = 1'b0; irq = 3'b110;
        @(negedge clk); nmi = 1'b0; irq = 3'b000;

        // NMI asserted with a few different irq patterns
        @(negedge clk); nmi = 1'b1; irq = 3'b000;
        @(negedge clk); nmi = 1'b1; irq = 3'b001;
        @(negedge clk); nmi = 1'b1; irq = 3'b010;
        @(negedge clk); nmi = 1'b1; irq = 3'b100;
        @(negedge clk); nmi = 1'b1; irq = 3'b011;
        @(negedge clk); nmi = 1'b1; irq = 3'b110;
        @(negedge clk); nmi = 1'b1; irq = 3'b101;
        @(negedge clk); nmi = 1'b1; irq = 3'b111;

        // A couple more cycles to observe the registered response
        @(negedge clk); nmi = 1'b0; irq = 3'b000;
        @(negedge clk);
        @(negedge clk);

        $finish;
    end

endmodule