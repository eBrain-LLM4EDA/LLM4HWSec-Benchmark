// testbench_stub.v
// Minimal, non-self-checking testbench skeleton for lfsr_rng.
// Extend a copy of this file (outside inputs/) to independently
// observe rand_out, output_valid, and health_error behavior over
// time using iverilog/vvp. This stub makes no claims about the
// expected sequence period or alarm timing.

`timescale 1ns/1ps

module testbench_stub;

    reg        clk;
    reg        rst_n;
    reg        enable;
    wire [7:0] rand_out;
    wire       output_valid;
    wire       health_error;

    integer    cycle_count;

    // Device under test.
    lfsr_rng dut (
        .clk          (clk),
        .rst_n        (rst_n),
        .enable       (enable),
        .rand_out     (rand_out),
        .output_valid (output_valid),
        .health_error (health_error)
    );

    // 10ns period clock.
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Waveform dump for optional inspection with a viewer.
    initial begin
        $dumpfile("lfsr_rng_stub.vcd");
        $dumpvars(0, testbench_stub);
    end

    // Stimulus: hold reset briefly, then enable and let it run.
    initial begin
        cycle_count = 0;
        rst_n  = 1'b0;
        enable = 1'b0;

        repeat (3) @(posedge clk);
        rst_n = 1'b1;
        @(posedge clk);
        enable = 1'b1;

        // Let the design run for several hundred cycles so its
        // steady-state behavior can be observed.
        repeat (500) @(posedge clk);

        $finish;
    end

    // Plain per-cycle trace; extend as needed for your own analysis.
    always @(posedge clk) begin
        cycle_count = cycle_count + 1;
        $display("t=%0t cycle=%0d rand_out=%02h output_valid=%b health_error=%b",
                  $time, cycle_count, rand_out, output_valid, health_error);
    end

endmodule