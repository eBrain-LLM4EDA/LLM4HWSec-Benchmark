// evaluation/fault_sim_tb.v
// Auxiliary fault-injection testbench used only by evaluate.py's optional
// empirical cross-check for SR4. Instantiates tmr_top (per design_brief.md
// port list: a, b, c inputs; voted_out output), optionally forces
// dut.net_repa_out to a fixed stuck-at value, drives a small fixed set of
// input vectors, and prints one line per vector in the form:
//   VOTED a=<b> b=<b> c=<b> out=<b>
// so evaluate.py can textually diff a golden (FAULT_REPLICA=0) run against a
// faulted (FAULT_REPLICA=1) run to look for a divergence in voted_out.

`timescale 1ns/1ps

module fault_harness_sim;

    // FAULT_REPLICA: 0 = no fault injected, 1 = force replica_a's output
    // net (dut.net_repa_out) to FAULT_VALUE. Only replica_a is modeled here
    // since that is the only fault case the empirical cross-check needs.
    parameter FAULT_REPLICA = 0;
    parameter FAULT_VALUE   = 1'b0;

    reg a, b, c;
    wire voted_out;

    tmr_top dut (
        .a         (a),
        .b         (b),
        .c         (c),
        .voted_out (voted_out)
    );

    // Apply the stuck-at fault (if requested) after a short settle delay.
    initial begin
        #1;
        if (FAULT_REPLICA == 1) begin
            force dut.net_repa_out = FAULT_VALUE;
        end
    end

    // Fixed, deterministic stimulus: exhaustive 3-bit vector sweep (8
    // vectors), well within the 20-line stimulus budget.
    initial begin
        a = 1'b0; b = 1'b0; c = 1'b0; #5;
        $display("VOTED a=%b b=%b c=%b out=%b", a, b, c, voted_out);

        a = 1'b0; b = 1'b0; c = 1'b1; #5;
        $display("VOTED a=%b b=%b c=%b out=%b", a, b, c, voted_out);

        a = 1'b0; b = 1'b1; c = 1'b0; #5;
        $display("VOTED a=%b b=%b c=%b out=%b", a, b, c, voted_out);

        a = 1'b0; b = 1'b1; c = 1'b1; #5;
        $display("VOTED a=%b b=%b c=%b out=%b", a, b, c, voted_out);

        a = 1'b1; b = 1'b0; c = 1'b0; #5;
        $display("VOTED a=%b b=%b c=%b out=%b", a, b, c, voted_out);

        a = 1'b1; b = 1'b0; c = 1'b1; #5;
        $display("VOTED a=%b b=%b c=%b out=%b", a, b, c, voted_out);

        a = 1'b1; b = 1'b1; c = 1'b0; #5;
        $display("VOTED a=%b b=%b c=%b out=%b", a, b, c, voted_out);

        a = 1'b1; b = 1'b1; c = 1'b1; #5;
        $display("VOTED a=%b b=%b c=%b out=%b", a, b, c, voted_out);

        $finish;
    end

endmodule