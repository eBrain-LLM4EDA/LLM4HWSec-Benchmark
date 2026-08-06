// masked_datapath.v
// Two-share masked datapath with pipeline stages.
// Implements a masked AND operation: (a0^a1) & (b0^b1) = (q0^q1)
// where q0 = (a0&b0) ^ r, q1 = (a1&b1) ^ r, and r is fresh randomness.

module masked_datapath (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  share0_a,
    input  wire [7:0]  share1_a,
    input  wire [7:0]  share0_b,
    input  wire [7:0]  share1_b,
    input  wire [7:0]  randomness,
    output wire [7:0]  share0_q,
    output wire [7:0]  share1_q
);

    // Pipeline stage 1 registers
    reg [7:0] share0_a_stage1_q, share1_a_stage1_q;
    reg [7:0] share0_b_stage1_q, share1_b_stage1_q;
    reg [7:0] randomness_stage1_q;

    // Pipeline stage 2 registers
    reg [7:0] share0_stage2_q, share1_stage2_q;

    // Stage 1: register inputs
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            share0_a_stage1_q <= 8'd0;
            share1_a_stage1_q <= 8'd0;
            share0_b_stage1_q <= 8'd0;
            share1_b_stage1_q <= 8'd0;
            randomness_stage1_q <= 8'd0;
        end else begin
            share0_a_stage1_q <= share0_a;
            share1_a_stage1_q <= share1_a;
            share0_b_stage1_q <= share0_b;
            share1_b_stage1_q <= share1_b;
            randomness_stage1_q <= randomness;
        end
    end

    // Stage 2: compute masked AND and register results
    // Both share0_stage2_q and share1_stage2_q update in the same cycle,
    // using the same randomness value.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            share0_stage2_q <= 8'd0;
            share1_stage2_q <= 8'd0;
        end else begin
            share0_stage2_q <= (share0_a_stage1_q & share0_b_stage1_q) ^ randomness_stage1_q;
            share1_stage2_q <= (share1_a_stage1_q & share1_b_stage1_q) ^ randomness_stage1_q;
        end
    end

    assign share0_q = share0_stage2_q;
    assign share1_q = share1_stage2_q;

endmodule