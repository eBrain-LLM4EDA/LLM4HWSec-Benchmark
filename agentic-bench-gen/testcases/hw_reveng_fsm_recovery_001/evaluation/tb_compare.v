// tb_compare.v
// Self-checking testbench: instantiates both the reference gate-level
// netlist (inputs/flattened_netlist.v) and the submitted recovered_fsm
// (submission/recovered_rtl.v), drives both with an identical (rst,in)
// sequence read from a vector file named via +VECFILE=<path>, and reports
// a single machine-parseable RESULT line for evaluate.py to parse.

`timescale 1ns/1ps

module tb_compare;

    reg clk;
    reg rst;
    reg in;

    wire out_ref;
    wire out_rec;

    integer fh;
    integer code;
    integer total;
    integer mismatches;

    reg [8*256:1] vecfile;

    // Reference gate-level netlist (built from primitives.v).
    flattened_netlist u_ref (
        .clk(clk),
        .rst(rst),
        .in(in),
        .out(out_ref)
    );

    // Submission under test.
    recovered_fsm u_rec (
        .clk(clk),
        .rst(rst),
        .in(in),
        .out(out_rec)
    );

    // Free-running clock, period 10ns.
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Safety watchdog in case the vector file is malformed and the read
    // loop never terminates naturally; keeps grading deterministic.
    initial begin
        #2000000;
        $display("RESULT total=%0d mismatches=%0d", total, (mismatches + 1));
        $finish;
    end

    initial begin
        total = 0;
        mismatches = 0;
        rst = 1'b0;
        in = 1'b0;

        if (!$value$plusargs("VECFILE=%s", vecfile)) begin
            $display("RESULT total=0 mismatches=1");
            $finish;
        end

        fh = $fopen(vecfile, "r");
        if (fh == 0) begin
            $display("RESULT total=0 mismatches=1");
            $finish;
        end

        while (!$feof(fh)) begin
            code = $fscanf(fh, "%d %d", rst, in);
            if (code == 2) begin
                // Apply the stimulus on the following rising edge, then
                // let the Moore output settle before comparing.
                @(posedge clk);
                #1;
                total = total + 1;
                if (out_ref !== out_rec) begin
                    mismatches = mismatches + 1;
                end
            end
        end

        $fclose(fh);
        $display("RESULT total=%0d mismatches=%0d", total, mismatches);
        $finish;
    end

endmodule