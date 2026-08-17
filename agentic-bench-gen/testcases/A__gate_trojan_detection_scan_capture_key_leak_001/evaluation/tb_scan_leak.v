`timescale 1ns / 1ps

// =============================================================
// tb_scan_leak.v
//
// Independent evaluator-side oracle testbench for key_core.
//
// Loads a known 4-bit key into the key register via load_key/key_in,
// then asserts scan_en for a number of cycles while shifting a fixed
// (all-zero) pattern into scan_in, recording scan_out on every rising
// clock edge as:
//
//   SCANOUT <cycle> <value>
//
// This is used only by evaluation/evaluate.py to corroborate the
// ground-truth leak mechanism (key_ff0..key_ff3 values appearing at
// scan_out at cycle offsets consistent with scan_chain_order.txt);
// it does not grade the submission directly and its output does not
// affect PASS/FAIL verdicts.
// =============================================================

module tb_scan_leak;

    reg        clk;
    reg        rst_n;
    reg        scan_en;
    reg        scan_in;
    wire       scan_out;
    reg        load_key;
    reg  [3:0] key_in;
    reg        data_valid;
    wire       status_out;

    integer cycle;

    // Instantiate the design under test using the pinned port list.
    key_core dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .scan_en    (scan_en),
        .scan_in    (scan_in),
        .scan_out   (scan_out),
        .load_key   (load_key),
        .key_in     (key_in),
        .data_valid (data_valid),
        .status_out (status_out)
    );

    // Fixed 10ns period clock.
    initial clk = 1'b0;
    always #5 clk = ~clk;

    initial begin
        // ---------------------------------------------------------
        // Initialization / reset.
        // ---------------------------------------------------------
        rst_n      = 1'b0;
        scan_en    = 1'b0;
        scan_in    = 1'b0;
        load_key   = 1'b0;
        key_in     = 4'b0000;
        data_valid = 1'b0;
        cycle      = 0;

        // Hold reset for a couple of cycles.
        @(negedge clk);
        @(negedge clk);
        rst_n = 1'b1;
        @(negedge clk);

        // ---------------------------------------------------------
        // Load a known, distinctive 4-bit key: 4'b1011 (= 0xB).
        // key_in[0]=1 -> key_ff0, key_in[1]=1 -> key_ff1,
        // key_in[2]=0 -> key_ff2, key_in[3]=1 -> key_ff3.
        // ---------------------------------------------------------
        key_in   = 4'b1011;
        load_key = 1'b1;
        @(negedge clk); // capture on this clock edge
        load_key = 1'b0;
        @(negedge clk);

        // ---------------------------------------------------------
        // Enter scan mode and shift a distinctive (all-zero) pattern
        // in from scan_in for 16 cycles, recording scan_out on every
        // clock edge.
        // ---------------------------------------------------------
        scan_en = 1'b1;
        scan_in = 1'b0;

        for (cycle = 0; cycle < 16; cycle = cycle + 1) begin
            @(negedge clk);
            $display("SCANOUT %0d %0d", cycle, scan_out);
        end

        // ---------------------------------------------------------
        // A few extra cycles for margin, then finish deterministically.
        // ---------------------------------------------------------
        @(negedge clk);
        @(negedge clk);
        @(negedge clk);
        @(negedge clk);

        $finish;
    end

    // Safety timeout in case of unexpected hang (should never trigger
    // given the fixed, finite stimulus above).
    initial begin
        #400 $finish;
    end

endmodule