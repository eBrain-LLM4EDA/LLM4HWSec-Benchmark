// testbench_stub.v
//
// Minimal, non-exhaustive simulation scaffold for lockstep_alu.
//
// This testbench is intentionally small: it instantiates the DUT, provides
// a clock and a synchronous reset sequence, and drives a handful of
// ordinary opcode/operand combinations while printing the registered
// outputs after each rising edge. It is meant as a starting point for
// further investigation, not as a complete or exhaustive functional test.
// Extend the `vectors` stimulus below (or add your own always-blocks) to
// explore additional opcode/operand combinations of interest.

`timescale 1ns/1ps

module testbench_stub;

    reg        clk;
    reg        rst_n;
    reg  [1:0] opcode;
    reg  [7:0] operand_a;
    reg  [7:0] operand_b;
    wire [7:0] architectural_result;
    wire       mismatch;

    // Device under test.
    lockstep_alu dut (
        .clk                  (clk),
        .rst_n                (rst_n),
        .opcode               (opcode),
        .operand_a            (operand_a),
        .operand_b            (operand_b),
        .architectural_result (architectural_result),
        .mismatch             (mismatch)
    );

    // 10ns period clock.
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Simple stimulus: synchronous reset, then a small handful of benign
    // opcode/operand combinations covering ADD, SUB, and XOR with ordinary
    // (non-edge-case) operands. Not exhaustive; feel free to add more
    // vectors, boundary cases, or your own opcode coverage.
    initial begin
        rst_n     = 1'b0;
        opcode    = 2'b00;
        operand_a = 8'h00;
        operand_b = 8'h00;

        // Hold reset for a couple of cycles.
        @(posedge clk);
        @(posedge clk);
        rst_n = 1'b1;

        // Vector 1: ADD
        @(posedge clk);
        opcode    = 2'b00;
        operand_a = 8'h10;
        operand_b = 8'h20;

        // Vector 2: SUB
        @(posedge clk);
        opcode    = 2'b01;
        operand_a = 8'h30;
        operand_b = 8'h11;

        // Vector 3: XOR
        @(posedge clk);
        opcode    = 2'b11;
        operand_a = 8'h0f;
        operand_b = 8'hf0;

        // Vector 4: ADD with different operands
        @(posedge clk);
        opcode    = 2'b00;
        operand_a = 8'h7f;
        operand_b = 8'h01;

        // Let the last vector's result register and print.
        @(posedge clk);
        @(posedge clk);

        $finish;
    end

    // Report registered outputs on every rising edge, after outputs settle.
    always @(posedge clk) begin
        #1;
        $display("t=%0t opcode=%b operand_a=%h operand_b=%h | architectural_result=%h mismatch=%b",
                  $time, opcode, operand_a, operand_b, architectural_result, mismatch);
    end

endmodule