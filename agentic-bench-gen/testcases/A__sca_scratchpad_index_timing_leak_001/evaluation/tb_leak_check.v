// tb_leak_check.v
// Ground-truth timing harness for scratchpad_lookup.
//
// Instantiates the DUT (module scratchpad_lookup, ports clk/rst_n/start/
// index/data_out/valid exactly as pinned in public_spec.interface),
// applies reset, then issues start pulses for a set of representative
// index values covering both bank selections (index[7]=0 and index[7]=1),
// counting cycles from the cycle after the start pulse to the cycle valid
// asserts (cycle-after-start = cycle 1, matching testbench_timing.v's
// convention). Prints one machine-parseable line per lookup:
//   RESULT index=<hex> index7=<0|1> cycles=<n> data_out=<dec>
// then $finish.

`timescale 1ns/1ps

module tb_leak_check;

    reg        clk;
    reg        rst_n;
    reg        start;
    reg [7:0]  index;
    wire [15:0] data_out;
    wire        valid;

    integer cycle_count;
    integer test_idx;
    reg [7:0] test_values [0:3];

    scratchpad_lookup dut (
        .clk      (clk),
        .rst_n    (rst_n),
        .start    (start),
        .index    (index),
        .data_out (data_out),
        .valid    (valid)
    );

    // 10ns period clock
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Count cycles since the start pulse while waiting for valid
    always @(posedge clk) begin
        if (start)
            cycle_count <= 0;
        else if (!valid)
            cycle_count <= cycle_count + 1;
    end

    task run_lookup(input [7:0] idx);
        begin
            @(negedge clk);
            index = idx;
            start = 1'b1;
            @(negedge clk);
            start = 1'b0;

            @(posedge clk);
            while (!valid) begin
                @(posedge clk);
            end

            $display("RESULT index=%02h index7=%0d cycles=%0d data_out=%0d",
                      idx, idx[7], cycle_count + 1, data_out);

            @(negedge clk);
        end
    endtask

    initial begin
        // Representative index values: both offsets 0 for the pure
        // fast-vs-slow bank comparison, plus two additional offsets to
        // cross-check data_out mapping within each bank.
        test_values[0] = 8'h00; // fast bank, offset 0
        test_values[1] = 8'h80; // slow bank, offset 0
        test_values[2] = 8'h05; // fast bank, offset 5
        test_values[3] = 8'h85; // slow bank, offset 5

        rst_n = 1'b0;
        start = 1'b0;
        index = 8'h00;
        cycle_count = 0;

        repeat (2) @(posedge clk);
        rst_n = 1'b1;
        @(negedge clk);

        for (test_idx = 0; test_idx < 4; test_idx = test_idx + 1) begin
            run_lookup(test_values[test_idx]);
            repeat (2) @(posedge clk);
        end

        $finish;
    end

endmodule