`timescale 1ns / 1ps

module mac_golden (
    input clk,
    input rst_n,
    input signed [7:0] a,
    input signed [7:0] b,
    input valid_in,
    output reg signed [19:0] result,
    output reg result_valid
);

    // Internal pipeline registers
    reg signed [7:0] a_d1, b_d1;
    reg valid_d1;
    reg signed [19:0] acc;  // 20-bit accumulator

    // Stage 1: register inputs
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            a_d1 <= 0;
            b_d1 <= 0;
            valid_d1 <= 0;
        end else begin
            a_d1 <= a;
            b_d1 <= b;
            valid_d1 <= valid_in;
        end
    end

    // Stage 2: compute saturated accumulate and register result
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            acc <= 0;
            result <= 0;
            result_valid <= 0;
        end else begin
            // Default: hold previous values
            result_valid <= valid_d1;

            if (valid_d1) begin
                // Compute product and sign-extend to 20 bits
                reg signed [15:0] product;
                reg signed [19:0] product_ext;
                reg signed [19:0] sum;
                product = a_d1 * b_d1;
                product_ext = {{4{product[15]}}, product};
                sum = acc + product_ext;

                // Saturation logic
                // Positive overflow: both operands positive, sum negative
                // Negative overflow: both operands negative, sum positive
                if (!acc[19] && !product_ext[19] && sum[19])
                    acc <= 20'h7FFFF;
                else if (acc[19] && product_ext[19] && !sum[19])
                    acc <= 20'h80000;
                else
                    acc <= sum;

                // Result is the saturated sum (the value that would be written to acc)
                if (!acc[19] && !product_ext[19] && sum[19])
                    result <= 20'h7FFFF;
                else if (acc[19] && product_ext[19] && !sum[19])
                    result <= 20'h80000;
                else
                    result <= sum;
            end else begin
                // When valid_d1 is low, result holds previous value
                // (result already retains its value due to non-blocking assignment behavior)
            end
        end
    end

endmodule