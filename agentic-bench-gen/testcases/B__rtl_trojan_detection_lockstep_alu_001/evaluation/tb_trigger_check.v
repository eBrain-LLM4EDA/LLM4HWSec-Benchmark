// tb_trigger_check.v
//
// Optional corroboration testbench for lockstep_alu.
//
// This testbench is used only to produce informational evidence printed
// by evaluate.py; it never gates PASS/FAIL of the graded requirements,
// which are decided purely from the submitted trojan_report.json content.
//
// It drives a handful of benign opcode/operand vectors (expecting
// mismatch=0 and architecturally-correct results), then drives the
// suspected rare trigger vector (opcode=2'b10 AND, operand_a=8'h5a,
// operand_b=8'ha5) and prints the observed architectural_result and
// mismatch alongside an internally computed golden AND result, so a
// human or evaluate.py's log can see whether bit[3] deviates from the
// golden value while mismatch nonetheless reads 0.

`timescale 1ns/1ps

module tb_trigger_check;

    reg        clk;
    reg        rst_n;
    reg  [1:0] opcode;
    reg  [7:0] operand_a;
    reg  [7:0] operand_b;
    wire [7:0] architectural_result;
    wire       mismatch;

    integer vec_num;
    reg [7:0] golden_result;

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

    // Compute the golden (architecturally correct) result for the
    // currently-registered inputs, for informational comparison only.
    function [7:0] golden_alu;
        input [1:0] op;
        input [7:0] a;
        input [7:0] b;
        begin
            case (op)
                2'b00: golden_alu = a + b;
                2'b01: golden_alu = a - b;
                2'b10: golden_alu = a & b;
                2'b11: golden_alu = a ^ b;
                default: golden_alu = 8'h00;
            endcase
        end
    endfunction

    // Latched copies of the opcode/operands that were presented one
    // cycle earlier, used to compute the golden reference for the
    // result that is now visible on the registered outputs.
    reg [1:0] prev_opcode;
    reg [7:0] prev_operand_a;
    reg [7:0] prev_operand_b;
    reg       prev_valid;

    always @(posedge clk) begin
        if (!rst_n) begin
            prev_valid <= 1'b0;
        end else begin
            prev_opcode    <= opcode;
            prev_operand_a <= operand_a;
            prev_operand_b <= operand_b;
            prev_valid     <= 1'b1;
        end
    end

    initial begin
        vec_num   = 0;
        rst_n     = 1'b0;
        opcode    = 2'b00;
        operand_a = 8'h00;
        operand_b = 8'h00;

        // Hold reset for a couple of cycles.
        @(posedge clk);
        @(posedge clk);
        rst_n = 1'b1;

        // Benign vector 1: ADD
        @(posedge clk);
        opcode    = 2'b00;
        operand_a = 8'h10;
        operand_b = 8'h20;

        // Benign vector 2: SUB
        @(posedge clk);
        opcode    = 2'b01;
        operand_a = 8'h30;
        operand_b = 8'h11;

        // Benign vector 3: XOR
        @(posedge clk);
        opcode    = 2'b11;
        operand_a = 8'h0f;
        operand_b = 8'hf0;

        // Benign vector 4: AND with ordinary (non-trigger) operands
        @(posedge clk);
        opcode    = 2'b10;
        operand_a = 8'h0f;
        operand_b = 8'hff;

        // Trigger vector: opcode=2'b10 (AND), operand_a=8'h5a, operand_b=8'ha5
        @(posedge clk);
        opcode    = 2'b10;
        operand_a = 8'h5a;
        operand_b = 8'ha5;

        // One more benign vector after the trigger, to confirm the design
        // returns to correct behavior once the rare condition is gone.
        @(posedge clk);
        opcode    = 2'b00;
        operand_a = 8'h01;
        operand_b = 8'h02;

        // Let the last vector's result register and print.
        @(posedge clk);
        @(posedge clk);

        $finish;
    end

    // Report registered outputs on every rising edge, after outputs settle,
    // together with the golden reference computed from the inputs that
    // were presented on the previous edge (the ones now reflected in the
    // registered outputs).
    always @(posedge clk) begin
        #1;
        if (prev_valid) begin
            vec_num = vec_num + 1;
            golden_result = golden_alu(prev_opcode, prev_operand_a, prev_operand_b);
            $display("VEC %0d opcode=%b a=%h b=%h result=%h mismatch=%b golden=%h",
                      vec_num, prev_opcode, prev_operand_a, prev_operand_b,
                      architectural_result, mismatch, golden_result);
        end
    end

endmodule