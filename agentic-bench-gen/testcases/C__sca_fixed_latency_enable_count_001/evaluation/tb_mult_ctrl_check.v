// tb_mult_ctrl_check.v
//
// Optional self-check testbench for mult_ctrl, used only as an independent
// cross-check of the ground truth derived from inputs/traces.csv. This
// testbench is NOT required for grading: evaluate.py's PASS/FAIL verdicts
// are always based on the submitted vulnerability_report.json content,
// cross-checked against traces.csv. If iverilog/vvp are unavailable or
// this simulation cannot be run, evaluate.py silently skips this
// cross-check and grading proceeds unaffected.
//
// This testbench drives a small fixed set of secret_operand values through
// mult_ctrl with public_operand held constant at 0xAA, pulses start once
// per operand, and prints one line per observed cycle in the form:
//
//   CYCLE <op> <cycle_index> <mul_en> <done>
//
// where <op> is the secret_operand value printed as a zero-padded 2-digit
// hex string (e.g. 3F), <cycle_index> is 0..9 relative to the cycle start
// was sampled, and <mul_en>/<done> are 0 or 1.

`timescale 1ns/1ps

module tb_mult_ctrl_check;

    reg        clk;
    reg        rst_n;
    reg        start;
    reg [7:0]  secret_operand;
    reg [7:0]  public_operand;
    wire       done;
    wire [15:0] product;
    wire       mul_en;

    integer    i;
    integer    cyc;

    // Fixed set of secret_operand values to exercise.
    reg [7:0] operands [0:5];

    mult_ctrl dut (
        .clk            (clk),
        .rst_n          (rst_n),
        .start          (start),
        .secret_operand (secret_operand),
        .public_operand (public_operand),
        .done           (done),
        .product        (product),
        .mul_en         (mul_en)
    );

    // Clock generation: 10ns period.
    initial clk = 1'b0;
    always #5 clk = ~clk;

    initial begin
        operands[0] = 8'h00;
        operands[1] = 8'h01;
        operands[2] = 8'h03;
        operands[3] = 8'hFF;
        operands[4] = 8'hAA;
        operands[5] = 8'h55;

        public_operand = 8'hAA;
        secret_operand  = 8'h00;
        start           = 1'b0;
        rst_n           = 1'b0;

        // Hold reset for a couple of cycles.
        @(negedge clk);
        @(negedge clk);
        rst_n = 1'b1;
        @(negedge clk);

        for (i = 0; i <= 5; i = i + 1) begin
            // Ensure controller is idle and reset cleanly before each trial
            // so trials are independent of one another, mirroring the
            // methodology described in fault_model.md.
            rst_n = 1'b0;
            start = 1'b0;
            @(negedge clk);
            @(negedge clk);
            rst_n = 1'b1;
            @(negedge clk);

            secret_operand = operands[i];

            // Pulse start for exactly one cycle, sampled on the next
            // posedge. cycle_index 0 corresponds to the cycle on which
            // start is sampled high.
            start = 1'b1;
            @(negedge clk);
            $display("CYCLE %02h 0 %0d %0d", secret_operand, mul_en, done);
            start = 1'b0;

            for (cyc = 1; cyc <= 9; cyc = cyc + 1) begin
                @(negedge clk);
                $display("CYCLE %02h %0d %0d %0d", secret_operand, cyc, mul_en, done);
            end
        end

        $finish;
    end

    // Safety timeout in case something hangs.
    initial begin
        #100000;
        $display("TIMEOUT");
        $finish;
    end

endmodule