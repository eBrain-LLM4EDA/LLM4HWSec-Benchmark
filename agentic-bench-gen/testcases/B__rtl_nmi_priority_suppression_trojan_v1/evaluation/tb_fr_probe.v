//-----------------------------------------------------------------------------
// evaluation/tb_fr_probe.v
//
// Minimal interface probe testbench for nmi_arbiter. Confirms the module
// compiles/elaborates cleanly with the exact pinned port names/widths:
//   module nmi_arbiter (clk, rst_n, nmi, irq[2:0], grant[3:0]);
//
// Drives one reset cycle plus two arbitrary vectors and prints
// 'PROBE_OK <grant>' after each sampled clock edge. Does not check policy
// correctness -- that is the job of tb_policy_sweep.v (FR2/FR3). This
// probe is used internally by evaluate.py only to sanity-check the
// harness's own ground-truth machinery; it does not gate FR1's
// pass/fail directly (FR1 grades the submission JSON's syntax).
//-----------------------------------------------------------------------------

`timescale 1ns/1ps

module tb_fr_probe;

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

    initial clk = 1'b0;
    always #5 clk = ~clk;

    initial begin
        rst_n = 1'b0;
        nmi   = 1'b0;
        irq   = 3'b000;

        // Hold reset for two cycles.
        @(negedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        // Arbitrary vector 1
        @(negedge clk);
        nmi = 1'b0;
        irq = 3'b101;

        @(posedge clk);
        #1;
        $display("PROBE_OK %b", grant);

        // Arbitrary vector 2
        @(negedge clk);
        nmi = 1'b1;
        irq = 3'b010;

        @(posedge clk);
        #1;
        $display("PROBE_OK %b", grant);

        @(negedge clk);
        $finish;
    end

endmodule