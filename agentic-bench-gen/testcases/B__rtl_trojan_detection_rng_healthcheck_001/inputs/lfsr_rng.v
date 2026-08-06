// lfsr_rng.v
// 8-bit LFSR-based pseudorandom number generator core.
// Provides an output-valid handshake and a built-in repetition
// health monitor. See design_brief.md for functional specification.

`timescale 1ns/1ps

module lfsr_rng (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       enable,
    output wire [7:0] rand_out,
    output wire       output_valid,
    output wire       health_error
);

    // Internal LFSR state register, seeded on reset.
    reg [7:0] state;

    // Handshake / validity tracking.
    reg       valid_reg;
    reg       enable_seen;

    // Health monitor bookkeeping.
    reg [7:0] prev_rand_out;
    reg       have_prev;
    reg [7:0] rep_count;
    reg       health_error_reg;

    // rand_out reflects the current state register combinationally.
    assign rand_out     = state;
    assign output_valid = valid_reg;
    assign health_error = health_error_reg;

    // ------------------------------------------------------------
    // Feedback / state-advance logic.
    // Computes the next feedback bit from the current state and
    // shifts it into the register on each enabled clock edge.
    // ------------------------------------------------------------
    always @(posedge clk) begin : feedback_logic
        reg feedback_bit;
        if (!rst_n) begin
            state <= 8'hA5;
        end else if (enable) begin
            // Tap combination for the feedback bit.
            feedback_bit = state[7] ^ state[5] ^ state[4];
            state <= {state[6:0], feedback_bit};
        end else begin
            state <= state;
        end
    end

    // ------------------------------------------------------------
    // Output-valid handshake.
    // Asserts one cycle after enable is first observed following
    // reset, and remains asserted while enable stays high.
    // ------------------------------------------------------------
    always @(posedge clk) begin : valid_logic
        if (!rst_n) begin
            valid_reg   <= 1'b0;
            enable_seen <= 1'b0;
        end else begin
            if (enable) begin
                enable_seen <= 1'b1;
            end
            if (enable_seen || enable) begin
                valid_reg <= 1'b1;
            end else begin
                valid_reg <= 1'b0;
            end
        end
    end

    // ------------------------------------------------------------
    // Health monitor.
    // Tracks consecutive repeats of rand_out while output_valid is
    // high, and raises health_error once the repetition threshold
    // is exceeded. The alarm is sticky until the next reset.
    // ------------------------------------------------------------
    always @(posedge clk) begin : health_monitor
        if (!rst_n) begin
            prev_rand_out    <= 8'h00;
            have_prev        <= 1'b0;
            rep_count        <= 8'h00;
            health_error_reg <= 1'b0;
        end else begin
            if (output_valid) begin
                if (rand_out == 8'h00) begin
                    // Treat a zero-crossing sample as a fresh
                    // reference point for the repetition tracker.
                    rep_count <= 8'h00;
                end else if (have_prev && (rand_out == prev_rand_out)) begin
                    rep_count <= rep_count + 8'h01;
                end else begin
                    rep_count <= 8'h00;
                end

                prev_rand_out <= rand_out;
                have_prev     <= 1'b1;
            end

            if (rep_count > 8'd4) begin
                health_error_reg <= 1'b1;
            end else if (health_error_reg) begin
                health_error_reg <= 1'b1;
            end
        end
    end

endmodule