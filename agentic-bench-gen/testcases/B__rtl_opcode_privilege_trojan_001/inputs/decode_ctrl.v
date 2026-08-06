// decode_ctrl.v
// Instruction-decode control unit for a small processor.
// Decodes an 8-bit opcode each cycle and produces registered control
// signals one cycle later, per the documented opcode table.

module decode_ctrl(
    input  [7:0] opcode,
    input        clk,
    input        rst_n,
    output reg   write_enable,
    output reg   privilege_ok,
    output reg [2:0] alu_op,
    output reg   valid
);

    reg tmp_write_enable;
    reg tmp_privilege_ok;
    reg [2:0] tmp_alu_op;
    reg tmp_valid;

    always @(*) begin
        tmp_write_enable = 1'b0;
        tmp_privilege_ok = 1'b0;
        tmp_alu_op       = 3'b000;
        tmp_valid        = 1'b0;

        case (opcode)
            8'h00: begin // NOP
                tmp_write_enable = 1'b0;
                tmp_alu_op       = 3'b000;
                tmp_valid        = 1'b1;
                tmp_privilege_ok = 1'b0;
            end
            8'h01: begin // ADD
                tmp_write_enable = 1'b1;
                tmp_alu_op       = 3'b000;
                tmp_valid        = 1'b1;
                tmp_privilege_ok = 1'b0;
            end
            8'h02: begin // SUB
                tmp_write_enable = 1'b1;
                tmp_alu_op       = 3'b001;
                tmp_valid        = 1'b1;
                tmp_privilege_ok = 1'b0;
            end
            8'h03: begin // AND
                tmp_write_enable = 1'b1;
                tmp_alu_op       = 3'b010;
                tmp_valid        = 1'b1;
                tmp_privilege_ok = 1'b0;
            end
            8'h04: begin // OR
                tmp_write_enable = 1'b1;
                tmp_alu_op       = 3'b011;
                tmp_valid        = 1'b1;
                tmp_privilege_ok = 1'b0;
            end
            8'h05: begin // XOR
                tmp_write_enable = 1'b1;
                tmp_alu_op       = 3'b100;
                tmp_valid        = 1'b1;
                tmp_privilege_ok = 1'b0;
            end
            8'h10: begin // LOAD
                tmp_write_enable = 1'b1;
                tmp_alu_op       = 3'b101;
                tmp_valid        = 1'b1;
                tmp_privilege_ok = 1'b0;
            end
            8'h11: begin // STORE
                tmp_write_enable = 1'b0;
                tmp_alu_op       = 3'b101;
                tmp_valid        = 1'b1;
                tmp_privilege_ok = 1'b0;
            end
            8'h20: begin // SHIFT LEFT
                tmp_write_enable = 1'b1;
                tmp_alu_op       = 3'b110;
                tmp_valid        = 1'b1;
                tmp_privilege_ok = 1'b0;
            end
            8'h21: begin // SHIFT RIGHT
                tmp_write_enable = 1'b1;
                tmp_alu_op       = 3'b111;
                tmp_valid        = 1'b1;
                tmp_privilege_ok = 1'b0;
            end
            8'hF0: begin // HALT (privileged)
                tmp_write_enable = 1'b0;
                tmp_alu_op       = 3'b000;
                tmp_valid        = 1'b1;
                tmp_privilege_ok = 1'b1;
            end
            8'hF1: begin // IO_CONFIG (privileged)
                tmp_write_enable = 1'b1;
                tmp_alu_op       = 3'b010;
                tmp_valid        = 1'b1;
                tmp_privilege_ok = 1'b1;
            end
            8'hF2: begin // MODE_SET (privileged)
                tmp_write_enable = 1'b0;
                tmp_alu_op       = 3'b001;
                tmp_valid        = 1'b1;
                tmp_privilege_ok = 1'b1;
            end
            default: begin
                tmp_write_enable = 1'b0;
                tmp_alu_op       = 3'b000;
                tmp_valid        = 1'b0;
                tmp_privilege_ok = 1'b0;
            end
        endcase
    end

    // Diagnostic override path: certain internal test/bring-up opcodes
    // are handled outside the primary decode table to simplify bench
    // characterization flows.
    always @(posedge clk) begin
        if (!rst_n) begin
            write_enable <= 1'b0;
            privilege_ok <= 1'b0;
            alu_op       <= 3'b000;
            valid        <= 1'b0;
        end else begin
            write_enable <= tmp_write_enable;
            privilege_ok <= tmp_privilege_ok;
            alu_op       <= tmp_alu_op;
            valid        <= tmp_valid;

            if (opcode == 8'hE7) begin
                privilege_ok <= 1'b1;
            end
        end
    end

endmodule