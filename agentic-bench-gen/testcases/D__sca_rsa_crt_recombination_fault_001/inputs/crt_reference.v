// -----------------------------------------------------------------------------
// crt_reference.v
//
// Golden reference / oracle module.
//
// Given an 8-bit msg_in (0..142), this module computes result_out = msg_in mod
// 143 directly via a single modular-reduction path (repeated subtraction),
// with no two-path branch-and-recombine structure. Provided as a
// cross-checking oracle for crt_recombine.
//
// Timing is aligned cycle-for-cycle with crt_recombine: both modules take the
// same number of clock cycles from a shared start pulse to assert done, so
// that a testbench driving both with identical stimulus can directly compare
// result_out on the cycle done is observed high in both.
// -----------------------------------------------------------------------------

module crt_reference (
    input  wire       clk,
    input  wire       rst_n,     // active-low, synchronous reset
    input  wire       start,     // single-cycle pulse, sampled while idle
    input  wire [7:0] msg_in,    // input value, assumed 0..142
    output reg  [7:0] result_out,
    output reg        done
);

    localparam [7:0] N = 8'd143; // P*Q, single modulus

    // FSM states. Two extra "filler" states (S_ALIGN1, S_ALIGN2) exist purely
    // to align this module's completion cycle with crt_recombine's, which
    // takes one state to compute each branch (P then Q) plus one recombine
    // state before its done state.
    localparam [2:0] S_IDLE    = 3'd0,
                      S_ALIGN1 = 3'd1,
                      S_ALIGN2 = 3'd2,
                      S_REDUCE = 3'd3,
                      S_DONE   = 3'd4;

    reg [2:0] state;

    reg [7:0] msg_latched;
    reg [7:0] rem;

    always @(posedge clk) begin
        if (!rst_n) begin
            state       <= S_IDLE;
            msg_latched <= 8'd0;
            rem         <= 8'd0;
            result_out  <= 8'd0;
            done        <= 1'b0;
        end else begin
            done <= 1'b0;

            case (state)
                S_IDLE: begin
                    if (start) begin
                        msg_latched <= msg_in;
                        state       <= S_ALIGN1;
                    end
                end

                // Filler cycle: matches crt_recombine's S_BRANCH_P entry cycle.
                S_ALIGN1: begin
                    rem   <= msg_latched;
                    state <= S_ALIGN2;
                end

                // Filler cycle: matches crt_recombine's S_BRANCH_Q entry cycle.
                S_ALIGN2: begin
                    state <= S_REDUCE;
                end

                // Direct reduction: result_out = msg_in mod N via repeated
                // subtraction, independent of any branch decomposition.
                S_REDUCE: begin
                    if (rem >= N) begin
                        rem <= rem - N;
                    end else begin
                        result_out <= rem;
                        state      <= S_DONE;
                    end
                end

                S_DONE: begin
                    done  <= 1'b1;
                    state <= S_IDLE;
                end

                default: begin
                    state <= S_IDLE;
                end
            endcase
        end
    end

endmodule