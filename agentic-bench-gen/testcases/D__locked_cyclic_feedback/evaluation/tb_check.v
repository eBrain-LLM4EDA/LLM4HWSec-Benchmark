// Auto-generated testbench for FR3
`timescale 1ns/1ps

module tb_check;
    reg a, b, c;
    wire [1:0] key;
    wire locked_out, oracle_out;

    assign key = 2'b{key_val};

    locked_netlist dut (
        .a(a), .b(b), .c(c),
        .key(key),
        .out(locked_out)
    );

    oracle ref (
        .a(a), .b(b), .c(c),
        .out(oracle_out)
    );

    integer i;
    reg [2:0] pattern;
    reg mismatch;

    initial begin
        mismatch = 0;
        for (i = 0; i < 8; i = i + 1) begin
            pattern = i;
            a = pattern[2];
            b = pattern[1];
            c = pattern[0];
            #1;
            if (locked_out !== oracle_out) begin
                $display("[TEST] FAIL: FR3: mismatch at a=%b b=%b c=%b: locked=%b oracle=%b",
                         a, b, c, locked_out, oracle_out);
                mismatch = 1;
            end
        end
        if (!mismatch) begin
            $display("[TEST] PASS: FR3");
        end
        $finish;
    end
endmodule