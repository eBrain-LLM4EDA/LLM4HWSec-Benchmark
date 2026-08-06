`timescale 1ns/1ps

module tb_period_health;

    reg        clk;
    reg        rst_n;
    reg        enable;
    wire [7:0] rand_out;
    wire       output_valid;
    wire       health_error;

    integer    i;
    integer    j;
    integer    n_samples;
    integer    period_found;
    integer    health_seen;

    // Storage for the sequence of rand_out samples observed while
    // output_valid is high.
    reg [7:0] samples [0:511];

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

    initial begin
        n_samples    = 0;
        period_found = -1;
        health_seen  = 0;

        rst_n  = 1'b0;
        enable = 1'b0;

        // Hold synchronous active-low reset for 3 rising edges.
        repeat (3) @(posedge clk);
        rst_n = 1'b1;

        // Assert enable and let the design run continuously.
        @(negedge clk);
        enable = 1'b1;

        // Run for 320 clock cycles, sampling rand_out while
        // output_valid is high and tracking health_error.
        for (i = 0; i < 320; i = i + 1) begin
            @(posedge clk);
            #1; // allow combinational/registered outputs to settle

            if (health_error)
                health_seen = 1;

            if (output_valid) begin
                if (n_samples < 512) begin
                    samples[n_samples] = rand_out;
                    n_samples = n_samples + 1;
                end
            end
        end

        // Determine the true period: find the smallest k such that
        // samples[k] == samples[0], scanning from the first recorded
        // valid sample onward. This works because a Fibonacci LFSR's
        // state sequence is a pure cycle once it starts.
        if (n_samples > 1) begin
            for (j = 1; j < n_samples; j = j + 1) begin
                if ((period_found == -1) && (samples[j] === samples[0])) begin
                    period_found = j;
                end
            end
        end

        if (period_found == -1) begin
            // No repeat observed within the sampled window; report the
            // number of samples collected as a lower-bound indicator
            // rather than leaving it undefined.
            period_found = n_samples;
        end

        $display("PERIOD=%0d", period_found);
        $display("HEALTH_ERROR_SEEN=%0d", health_seen);

        $finish;
    end

endmodule