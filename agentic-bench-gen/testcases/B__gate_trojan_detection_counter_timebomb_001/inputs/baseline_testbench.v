`timescale 1ns/1ps

module baseline_testbench;

    reg clk;
    reg rst;
    reg enable;
    reg [7:0] in;
    wire [7:0] out;

    integer i;

    datapath_top dut (
        .clk    (clk),
        .rst    (rst),
        .enable (enable),
        .in     (in),
        .out    (out)
    );

    // Clock generation: 10ns period
    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    initial begin
        $display("time\tclk\trst\tenable\tin\t\tout");
        $monitor("%0t\t%b\t%b\t%b\t%h\t\t%h", $time, clk, rst, enable, in, out);
    end

    initial begin
        // Initialize inputs
        rst    = 1'b1;
        enable = 1'b0;
        in     = 8'h00;

        // Hold reset for a couple of cycles
        @(posedge clk);
        @(posedge clk);
        rst = 1'b0;

        // Begin enabled accumulation with a short stimulus sequence.
        // Only a handful of clock cycles are exercised here -- far fewer
        // than would be needed to observe any long-horizon, count-dependent
        // behavior in the design.
        @(posedge clk);
        enable = 1'b1;
        in     = 8'h01;

        for (i = 0; i < 5; i = i + 1) begin
            @(posedge clk);
        end

        in = 8'h02;
        for (i = 0; i < 5; i = i + 1) begin
            @(posedge clk);
        end

        in = 8'h03;
        for (i = 0; i < 5; i = i + 1) begin
            @(posedge clk);
        end

        in = 8'h00;
        enable = 1'b0;
        for (i = 0; i < 5; i = i + 1) begin
            @(posedge clk);
        end

        $finish;
    end

endmodule