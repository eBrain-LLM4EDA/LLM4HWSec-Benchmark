// testbench_stub.v
// Standalone functional testbench for access_ctrl_top.
// Generates clock/reset, drives a small sweep of stimulus vectors,
// and records internal/external signals for observation.

`timescale 1ns/1ps

module testbench_stub;

    reg        clk;
    reg        rst_n;
    reg  [7:0] key_in;
    reg        req_valid;
    wire       grant_out;

    // Internal net exposed for observation via hierarchical reference.
    wire       grant_pre_probe;

    access_ctrl_top dut (
        .clk       (clk),
        .rst_n     (rst_n),
        .key_in    (key_in),
        .req_valid (req_valid),
        .grant_out (grant_out)
    );

    assign grant_pre_probe = dut.grant_pre;

    // Clock generation: 10ns period.
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Reset pulse and stimulus sequencing.
    initial begin
        rst_n     = 1'b0;
        req_valid = 1'b0;
        key_in    = 8'h00;

        // Hold reset for a couple of cycles.
        #12 rst_n = 1'b1;

        // Vector 1: non-matching key, request asserted.
        @(negedge clk);
        key_in    = 8'h00;
        req_valid = 1'b1;

        // Vector 2: matching key (matches internal reference), request asserted.
        @(negedge clk);
        key_in    = 8'hA5;
        req_valid = 1'b1;

        // Vector 3: matching key, request deasserted.
        @(negedge clk);
        key_in    = 8'hA5;
        req_valid = 1'b0;

        // Vector 4: non-matching key, request asserted.
        @(negedge clk);
        key_in    = 8'h5A;
        req_valid = 1'b1;

        // Vector 5: matching key, request asserted again.
        @(negedge clk);
        key_in    = 8'hA5;
        req_valid = 1'b1;

        // Let the pipeline settle for a few more cycles.
        @(negedge clk);
        @(negedge clk);
        @(negedge clk);
        @(negedge clk);
        @(negedge clk);

        $finish;
    end

    // Waveform dump for post-processing / cross-checking.
    initial begin
        $dumpfile("access_ctrl_tb.vcd");
        $dumpvars(0, testbench_stub);
    end

    // Textual trace for quick inspection.
    initial begin
        $monitor("t=%0t clk=%b rst_n=%b key_in=%h req_valid=%b grant_pre=%b grant_out=%b",
                  $time, clk, rst_n, key_in, req_valid, grant_pre_probe, grant_out);
    end

endmodule