// =============================================================================
// recovered_rtl.v
//
// Recovered word-level implementation of the undocumented quadrature decoder
// block, derived from quadrature_netlist.v (quad_decoder_gates) and
// quadrature_wrapper.v. Implements the pinned `quad_decoder` interface.
// =============================================================================

module quad_decoder (
    input  wire              clk,
    input  wire              rst,
    input  wire              a,
    input  wire              b,
    output reg  signed [7:0] pos,
    output reg               dir,
    output reg               invalid
);

    // cur holds S(N-1): the {a,b} pattern sampled at the D-inputs of the
    // state register on the PREVIOUS active edge (i.e. the value in effect
    // going into this cycle, before this edge's new sample is captured).
    // prev is retained for structural fidelity with the netlist's
    // previous-state register pair, though only `cur` (as S(N-1)) and the
    // newly sampled {a,b} (S(N)) are needed for the comparison below.
    reg [1:0] cur;
    reg [1:0] prev;

    wire [1:0] new_sample = {a, b};

    always @(posedge clk) begin
        if (rst) begin
            pos     <= 8'sd0;
            dir     <= 1'b0;
            invalid <= 1'b0;
            cur     <= 2'b00;
            prev    <= 2'b00;
        end else begin
            // Compare OLD cur (S(N-1)) against the newly sampled pattern
            // (S(N)) BEFORE updating cur/prev, matching the pinned
            // Moore-output, 1-cycle-latency semantics.
            if (new_sample == cur) begin
                // No change: hold pos and dir, clear invalid.
                invalid <= 1'b0;
            end else if ((cur == 2'b00 && new_sample == 2'b01) ||
                         (cur == 2'b01 && new_sample == 2'b11) ||
                         (cur == 2'b11 && new_sample == 2'b10) ||
                         (cur == 2'b10 && new_sample == 2'b00)) begin
                // Legal forward Gray step: 00->01->11->10->00
                pos     <= pos + 8'sd1;
                dir     <= 1'b1;
                invalid <= 1'b0;
            end else if ((cur == 2'b00 && new_sample == 2'b10) ||
                         (cur == 2'b10 && new_sample == 2'b11) ||
                         (cur == 2'b11 && new_sample == 2'b01) ||
                         (cur == 2'b01 && new_sample == 2'b00)) begin
                // Legal reverse Gray step: 00->10->11->01->00
                pos     <= pos - 8'sd1;
                dir     <= 1'b0;
                invalid <= 1'b0;
            end else begin
                // Illegal two-bit jump (00<->11 or 01<->10): hold pos/dir,
                // pulse invalid for exactly this one cycle.
                invalid <= 1'b1;
            end

            // Advance the state history registers.
            prev <= cur;
            cur  <= new_sample;
        end
    end

endmodule