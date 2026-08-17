// -----------------------------------------------------------------------------
// tb_crt_recombine.v
//
// Basic nominal-condition testbench: drives crt_recombine and crt_reference
// with identical stimulus (shared clk/rst_n/start/msg_in) across a few
// unfaulted input vectors, and confirms both modules agree on result_out on
// the cycle each asserts done. Establishes baseline functional correctness
// with no fault injection.
// -----------------------------------------------------------------------------

`timescale 1ns/1ps

module tb_crt_recombine;

    reg        clk;
    reg        rst_n;
    reg        start;
    reg  [7:0] msg_in;

    wire [7:0] result_out_dut;
    wire       done_dut;

    wire [7:0] result_out_ref;
    wire       done_ref;

    integer errors;
    integer i;

    reg [7:0] test_vectors [0:2];

    crt_recombine dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .start      (start),
        .msg_in     (msg_in),
        .result_out (result_out_dut),
        .done       (done_dut)
    );

    crt_reference ref_mod (
        .clk        (clk),
        .rst_n      (rst_n),
        .start      (start),
        .msg_in     (msg_in),
        .result_out (result_out_ref),
        .done       (done_ref)
    );

    // Clock generation.
    initial clk = 1'b0;
    always #5 clk = ~clk;

    initial begin
        errors = 0;

        test_vectors[0] = 8'd5;
        test_vectors[1] = 8'd77;
        test_vectors[2] = 8'd142;

        rst_n  = 1'b0;
        start  = 1'b0;
        msg_in = 8'd0;

        repeat (3) @(posedge clk);
        rst_n = 1'b1;
        @(posedge clk);

        for (i = 0; i < 3; i = i + 1) begin
            msg_in = test_vectors[i];

            @(posedge clk);
            start = 1'b1;
            @(posedge clk);
            start = 1'b0;

            // Wait for both modules to assert done (they are cycle-aligned).
            wait (done_dut === 1'b1);

            if (done_ref !== 1'b1) begin
                $display("ERROR: msg_in=%0d - crt_reference did not assert done when crt_recombine did", msg_in);
                errors = errors + 1;
            end else if (result_out_dut !== result_out_ref) begin
                $display("ERROR: msg_in=%0d - result_out mismatch: crt_recombine=%0d crt_reference=%0d",
                          msg_in, result_out_dut, result_out_ref);
                errors = errors + 1;
            end else begin
                $display("OK:    msg_in=%0d - crt_recombine=%0d crt_reference=%0d (match)",
                          msg_in, result_out_dut, result_out_ref);
            end

            @(posedge clk);
        end

        if (errors == 0)
            $display("SUMMARY: PASS - all %0d nominal vectors matched", 3);
        else
            $display("SUMMARY: FAIL - %0d mismatch(es) detected", errors);

        $finish;
    end

endmodule