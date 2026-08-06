// tb_isolation.v
// Exhaustive testbench for isolation_wrapper: drives all 32 combinations
// of (secure_data[3:0], power_down), toggles clk (unused by the
// combinational design, present only for interface uniformity), and
// prints one machine-parseable line per vector for evaluate.py to parse.

`timescale 1ns/1ps

module tb_isolation;

    reg [3:0] secure_data;
    reg       power_down;
    reg       clk;
    wire [3:0] public_out;

    integer i;

    isolation_wrapper dut (
        .secure_data(secure_data),
        .power_down(power_down),
        .clk(clk),
        .public_out(public_out)
    );

    // free-running clock, unused by combinational logic but toggled for
    // interface uniformity
    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    initial begin
        secure_data = 4'b0000;
        power_down  = 1'b0;

        for (i = 0; i < 32; i = i + 1) begin
            secure_data = i[3:0];
            power_down  = i[4];
            #10;
            $display("VEC secure_data=%b power_down=%b public_out=%b",
                      secure_data, power_down, public_out);
        end

        $finish;
    end

endmodule