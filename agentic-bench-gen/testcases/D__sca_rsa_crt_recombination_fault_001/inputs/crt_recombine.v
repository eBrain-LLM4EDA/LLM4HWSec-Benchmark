// -----------------------------------------------------------------------------
// crt_recombine.v
//
// Two-path modular recombination datapath.
//
// Given an 8-bit msg_in (0..142), this module computes result_out = msg_in mod
// 143 by:
//   1. computing branch-1 partial result  sig_p_reg = msg_in mod p   (p = 11)
//   2. computing branch-2 partial result  sig_q_reg = msg_in mod q   (q = 13)
//   3. recombining sig_p_reg and sig_q_reg via a fixed CRT-style weighted-sum
//      formula, mod (p*q) = 143, to produce result_out.
//
// The recombination step consumes sig_p_reg and sig_q_reg directly as stored,
// with no independent recomputation or cross-check of either branch value
// before result_out is latched and done is asserted.
// -----------------------------------------------------------------------------

module crt_recombine (
    input  wire       clk,
    input  wire       rst_n,     // active-low, synchronous reset
    input  wire       start,     // single-cycle pulse, sampled while idle
    input  wire [7:0] msg_in,    // input value, assumed 0..142
    output reg  [7:0] result_out,
    output reg        done
);

    // Fixed demonstration moduli.
    localparam [7:0] P = 8'd11;
    localparam [7:0] Q = 8'd13;
    localparam [15:0] N = 16'd143; // P*Q

    // CRT recombination weights, precomputed for the fixed moduli above:
    //   result = ( sig_p_reg * Q * (Q^-1 mod P) + sig_q_reg * P * (P^-1 mod Q) ) mod N
    // Q^-1 mod P: 13 mod 11 = 2, 2^-1 mod 11 = 6   -> weight_p_const = Q * 6  = 78
    // P^-1 mod Q: 11 mod 13 = 11, 11^-1 mod 13 = 6 -> weight_q_const = P * 6  = 66
    localparam [15:0] WEIGHT_P = 16'd78; // = Q * (Q^-1 mod P), used to scale sig_p_reg
    localparam [15:0] WEIGHT_Q = 16'd66; // = P * (P^-1 mod Q), used to scale sig_q_reg

    // FSM states.
    localparam [2:0] S_IDLE      = 3'd0,
                      S_BRANCH_P  = 3'd1,
                      S_BRANCH_Q  = 3'd2,
                      S_RECOMBINE = 3'd3,
                      S_DONE      = 3'd4;

    reg [2:0] state;

    reg [7:0] msg_latched;

    // Branch registers: each holds an intermediate partial result that is
    // later consumed, as-is, by the recombination arithmetic below.
    reg [7:0] sig_p_reg;   // branch-1 partial result register: msg_in mod P
    reg [7:0] sig_q_reg;   // branch-2 partial result register: msg_in mod Q

    // Scratch registers used while computing each branch's modular reduction
    // via simple repeated subtraction (small moduli, few iterations).
    reg [7:0] rem_p;
    reg [7:0] rem_q;

    always @(posedge clk) begin
        if (!rst_n) begin
            state       <= S_IDLE;
            msg_latched <= 8'd0;
            sig_p_reg   <= 8'd0;
            sig_q_reg   <= 8'd0;
            rem_p       <= 8'd0;
            rem_q       <= 8'd0;
            result_out  <= 8'd0;
            done        <= 1'b0;
        end else begin
            done <= 1'b0;

            case (state)
                S_IDLE: begin
                    if (start) begin
                        msg_latched <= msg_in;
                        rem_p       <= msg_in;
                        state       <= S_BRANCH_P;
                    end
                end

                // Compute sig_p_reg = msg_in mod P via repeated subtraction.
                S_BRANCH_P: begin
                    if (rem_p >= P) begin
                        rem_p <= rem_p - P;
                    end else begin
                        sig_p_reg <= rem_p;
                        rem_q     <= msg_latched;
                        state     <= S_BRANCH_Q;
                    end
                end

                // Compute sig_q_reg = msg_in mod Q via repeated subtraction.
                S_BRANCH_Q: begin
                    if (rem_q >= Q) begin
                        rem_q <= rem_q - Q;
                    end else begin
                        sig_q_reg <= rem_q;
                        state     <= S_RECOMBINE;
                    end
                end

                // Recombine the two branch registers directly, with no
                // re-verification of either sig_p_reg or sig_q_reg against an
                // independent recomputation before producing result_out.
                S_RECOMBINE: begin
                    result_out <= ((sig_p_reg * WEIGHT_P) + (sig_q_reg * WEIGHT_Q)) % N;
                    state      <= S_DONE;
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