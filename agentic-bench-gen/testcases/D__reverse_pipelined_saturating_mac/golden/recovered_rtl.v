// Golden behavioral RTL for mac_top
// Implements sat20(acc + signed(a)*signed(b)) with exact two-cycle latency
// Asynchronous active-low reset, registered outputs (Moore)

module mac_top (
    input clk,
    input rst_n,                    // asynchronous active-low reset
    input signed [7:0] a,
    input signed [7:0] b,
    input valid_in,
    output reg signed [19:0] result,
    output reg result_valid
);

    // Internal pipeline registers
    reg signed [15:0] product_stage1;   // 8-bit * 8-bit = 16-bit product
    reg valid_stage1;
    reg signed [19:0] acc_stage1;       // accumulator value at stage1

    // Stage 2 registers
    reg signed [19:0] sum_stage2;       // acc + product (before saturation)
    reg valid_stage2;

    // Internal accumulator (20-bit signed)
    reg signed [19:0] accumulator;

    // Asynchronous reset logic
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // Reset all registers
            accumulator <= 20'd0;
            product_stage1 <= 16'd0;
            valid_stage1 <= 1'b0;
            acc_stage1 <= 20'd0;
            sum_stage2 <= 20'd0;
            valid_stage2 <= 1'b0;
            result <= 20'd0;
            result_valid <= 1'b0;
        end else begin
            // Stage 1: compute product and capture accumulator
            if (valid_in) begin
                product_stage1 <= a * b;
                acc_stage1 <= accumulator;
                valid_stage1 <= 1'b1;
                // Update accumulator with saturated sum (will be computed in stage2)
                // We need to compute the new accumulator value here for next cycle
                // The sum will be available in stage2, but we need it now for the accumulator update.
                // So we compute the sum combinationally here.
                // Note: This is a behavioral model; synthesis tools will handle it.
                // For correctness, we compute the sum and saturation in this cycle.
                reg signed [20:0] temp_sum; // extra bit for overflow detection
                temp_sum = accumulator + a * b;
                // Saturation logic
                if (temp_sum > 20'h7FFFF)
                    accumulator <= 20'h7FFFF;
                else if (temp_sum < -20'sh80000)
                    accumulator <= 20'h80000;
                else
                    accumulator <= temp_sum[19:0];
            end else begin
                valid_stage1 <= 1'b0;
            end

            // Stage 2: apply saturation to the captured sum and drive outputs
            valid_stage2 <= valid_stage1;
            if (valid_stage1) begin
                // Compute sum from stage1 captured values
                reg signed [20:0] temp_sum2;
                temp_sum2 = acc_stage1 + product_stage1;
                // Saturation
                if (temp_sum2 > 20'h7FFFF)
                    sum_stage2 <= 20'h7FFFF;
                else if (temp_sum2 < -20'sh80000)
                    sum_stage2 <= 20'h80000;
                else
                    sum_stage2 <= temp_sum2[19:0];
            end

            // Output registers (Moore)
            result_valid <= valid_stage2;
            if (valid_stage2)
                result <= sum_stage2;
            else
                result <= 20'd0; // keep result at 0 when not valid
        end
    end

endmodule