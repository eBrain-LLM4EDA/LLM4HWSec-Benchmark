// testbench_timing.v
// Exercises scratchpad_lookup with representative index values and reports
// the number of clock cycles from the start pulse to the valid pulse,
// along with the resulting data_out value.

`timescale 1ns/1ps

module testbench_timing;

    reg        clk;
    reg        rst_n;
    reg        start;
    reg [7:0]  index;
    wire [15:0] data_out;
    wire        valid;

    integer cycle_count;
    integer test_idx;
    reg [7:0] test_values [0:1];

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

            $display("index=0x%02h index7=%0d cycles_start_to_valid=%0d data_out=%0d",
                      idx, idx[7], cycle_count + 1, data_out);

            @(negedge clk);
        end
    endtask

    initial begin
        test_values[0] = 8'h00;
        test_values[1] = 8'h80;

        rst_n = 1'b0;
        start = 1'b0;
        index = 8'h00;
        cycle_count = 0;

        repeat (2) @(posedge clk);
        rst_n = 1'b1;
        @(negedge clk);

        for (test_idx = 0; test_idx < 2; test_idx = test_idx + 1) begin
            run_lookup(test_values[test_idx]);
            repeat (2) @(posedge clk);
        end

        $finish;
    end

endmodule