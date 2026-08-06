// recovered_rtl.v
// Naive baseline submission: compiles but fails functional simulation.
// Participants must replace this with a correct behavioral implementation.

module mac_top (
    input clk,
    input rst_n,
    input signed [7:0] a,
    input signed [7:0] b,
    input valid_in,
    output reg signed [19:0] result,
    output reg result_valid
);

    // Trivially incorrect: always outputs zero, no pipeline, no accumulation.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            result <= 20'd0;
            result_valid <= 1'b0;
        end else begin
            result <= 20'd0;
            result_valid <= 1'b0;
        end
    end

endmodule