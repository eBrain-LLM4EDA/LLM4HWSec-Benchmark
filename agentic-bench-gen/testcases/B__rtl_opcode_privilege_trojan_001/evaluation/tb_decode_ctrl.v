`timescale 1ns/1ps
//
// tb_decode_ctrl.v
//
// Verilog-2001 testbench for evaluation of inputs/decode_ctrl.v.
//
// Instantiates decode_ctrl exactly per the pinned public interface:
//   decode_ctrl(input [7:0] opcode, input clk, input rst_n,
//               output write_enable, output privilege_ok,
//               output [2:0] alu_op, output valid)
//
// Applies a synchronous active-low reset for 2 clock cycles, then sweeps
// every opcode value 0x00-0xFF (ascending), presenting each opcode and
// waiting exactly one additional posedge for the registered outputs to
// capture the decode of that opcode (1-cycle latency per design_brief.md).
// Prints exactly one "OPCRES <opcode-hex> <we> <priv> <alu-bin> <valid>"
// line per opcode, for a total of 256 lines, which evaluate.py parses.
//

module tb_decode_ctrl;

    reg  [7:0] opcode;
    reg        clk;
    reg        rst_n;

    wire       write_enable;
    wire       privilege_ok;
    wire [2:0] alu_op;
    wire       valid;

    integer i;
    reg [7:0] tested_opcode;

    decode_ctrl dut (
        .opcode       (opcode),
        .clk          (clk),
        .rst_n        (rst_n),
        .write_enable (write_enable),
        .privilege_ok (privilege_ok),
        .alu_op       (alu_op),
        .valid        (valid)
    );

    // Free-running clock, 10ns period.
    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    initial begin
        // Initialize inputs and assert synchronous active-low reset.
        opcode = 8'h00;
        rst_n  = 1'b0;

        // Hold reset across 2 clock cycles.
        @(posedge clk);
        @(posedge clk);
        #1;
        rst_n = 1'b1;

        // Sweep all 256 possible opcode values, ascending, using a 32-bit
        // loop variable to avoid the 8-bit wraparound that an 8-bit index
        // would hit at 256.
        for (i = 0; i < 256; i = i + 1) begin
            @(posedge clk);
            #1;
            opcode        = i[7:0];
            tested_opcode = i[7:0];

            // Wait exactly one more posedge for the registered outputs to
            // capture the combinational decode of this opcode value
            // (1-cycle latency per the module's documented timing).
            @(posedge clk);
            #1;

            $display("OPCRES %02h %b %b %b %b",
                      tested_opcode, write_enable, privilege_ok, alu_op, valid);
        end

        #10;
        $finish;
    end

endmodule