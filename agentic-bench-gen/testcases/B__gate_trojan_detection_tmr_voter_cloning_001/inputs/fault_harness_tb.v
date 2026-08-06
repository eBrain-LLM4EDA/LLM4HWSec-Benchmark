// fault_harness_tb.v
// Compact single-stuck-at-fault harness for tmr_top.
//
// Drives a handful of representative input vectors through the design and
// reports the voted output for each. A single stuck-at fault can be
// injected into one replica under test at a time by selecting FAULT_REPLICA
// (0 = none, 1 = replica A, 2 = replica B, 3 = replica C) and FAULT_VALUE
// (the stuck-at logic value to force). The fault is applied via a
// hierarchical force on the replica's output net for the duration of the
// run, emulating a single stuck-at defect in that replica's logic cone.

`timescale 1ns/1ps

module fault_harness_tb;

    // Select which replica under test receives the injected fault, and to
    // what stuck-at value. 0 = no fault injected.
    parameter FAULT_REPLICA = 0;
    parameter FAULT_VALUE   = 1'b0;

    reg a, b, c;
    wire voted_out;

    integer i;
    reg [2:0] vec;

    tmr_top dut (
        .a         (a),
        .b         (b),
        .c         (c),
        .voted_out (voted_out)
    );

    // Apply the stuck-at fault (if any) to the selected replica's output
    // net under test. This mimics a single hardware fault local to one
    // replica's logic cone.
    initial begin
        #1;
        if (FAULT_REPLICA == 1)
            force dut.net_repa_out = FAULT_VALUE;
        else if (FAULT_REPLICA == 2)
            force dut.net_repb_out = FAULT_VALUE;
        else if (FAULT_REPLICA == 3)
            force dut.net_repc_out = FAULT_VALUE;
    end

    initial begin
        $display("FAULT_REPLICA=%0d FAULT_VALUE=%b", FAULT_REPLICA, FAULT_VALUE);
        $display(" a b c | voted_out");

        for (i = 0; i < 8; i = i + 1) begin
            vec = i[2:0];
            a = vec[2];
            b = vec[1];
            c = vec[0];
            #5;
            $display(" %b %b %b |    %b", a, b, c, voted_out);
        end

        $finish;
    end

endmodule