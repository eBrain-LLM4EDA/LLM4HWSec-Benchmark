// tb_cross_check.v
// Standalone cross-check testbench used only by evaluation/evaluate.py's
// SR5 simulation cross-check step. Instantiates access_ctrl_top from
// inputs/access_ctrl_netlist.v (compiled alongside inputs/cell_library.v)
// and prints a fixed, machine-parseable trace of the internal grant_pre
// net alongside u_grant_ff's registered output (grant_q) so the grader
// can detect a half-cycle sampling discrepancy between a negedge-triggered
// flop and the comparator's settled value.
//
// This file does not modify or duplicate any file under inputs/.

`timescale 1ns/1ps

module tb_cross_check;

    reg        clk;
    reg        rst_n;
    reg  [7:0] key_in;
    reg        req_valid;
    wire       grant_out;

    access_ctrl_top dut (
        .clk       (clk),
        .rst_n     (rst_n),
        .key_in    (key_in),
        .req_valid (req_valid),
        .grant_out (grant_out)
    );

    // Hierarchical probes into the DUT's internal comparator output and
    // the registered output of the anomalous instance under investigation.
    wire grant_pre_probe;
    wire grant_q_probe;

    assign grant_pre_probe = dut.grant_pre;
    assign grant_q_probe   = dut.grant_q;

    // Clock generation: 10ns period (5ns high, 5ns low).
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Reset pulse and stimulus sequencing.
    initial begin
        rst_n     = 1'b0;
        req_valid = 1'b0;
        key_in    = 8'h00;

        // Hold reset for a couple of cycles.
        #12 rst_n = 1'b1;

        // Sweep through non-matching and matching key values with
        // req_valid asserted, aligning stimulus changes to negedge so
        // that both posedge- and negedge-sampling behavior around the
        // comparator's settling window can be observed on subsequent
        // edges.
        @(negedge clk);
        key_in    = 8'h00;
        req_valid = 1'b1;

        @(negedge clk);
        key_in    = 8'hA5;
        req_valid = 1'b1;

        @(negedge clk);
        key_in    = 8'h5A;
        req_valid = 1'b1;

        @(negedge clk);
        key_in    = 8'hA5;
        req_valid = 1'b1;

        @(negedge clk);
        key_in    = 8'h00;
        req_valid = 1'b1;

        @(negedge clk);
        key_in    = 8'hA5;
        req_valid = 1'b1;

        // Let the pipeline settle for a few more cycles.
        @(negedge clk);
        @(negedge clk);
        @(negedge clk);
        @(negedge clk);

        $finish;
    end

    // Fixed, machine-parseable trace printed at every clock edge (both
    // posedge and negedge) so the grader can observe grant_pre and
    // grant_q values at half-cycle granularity.
    always @(posedge clk) begin
        $display("TB t=%0d grant_pre=%b grant_q=%b", $time, grant_pre_probe, grant_q_probe);
    end

    always @(negedge clk) begin
        $display("TB t=%0d grant_pre=%b grant_q=%b", $time, grant_pre_probe, grant_q_probe);
    end

endmodule