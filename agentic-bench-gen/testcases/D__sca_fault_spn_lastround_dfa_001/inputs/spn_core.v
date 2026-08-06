// spn_core.v
// 16-bit, 4-round substitution-permutation network (SPN) cipher core.
//
// Round structure (rounds 0..2, i.e. the first three rounds):
//   1. XOR state with round key
//   2. Apply 4-bit S-box independently to each of the 4 nibbles
//   3. Apply fixed bit permutation across the 16-bit state
//
// Final round (round 3):
//   1. XOR state with round key
//   2. Apply 4-bit S-box independently to each of the 4 nibbles
//   3. (no permutation)
//   4. XOR with final_key to produce ciphertext
//
// state_q is the only multi-cycle architectural register: it holds the
// round state carried across clock edges between rounds.

module spn_core (
    input  wire        clk,
    input  wire         rst,
    input  wire         start,
    input  wire [15:0]  plaintext,
    input  wire [15:0]  key,
    output reg  [15:0]  ciphertext,
    output reg          done
);

    // ------------------------------------------------------------------
    // Fixed 4-bit -> 4-bit S-box (nonlinear substitution table).
    // Applied identically to every nibble, every round.
    // ------------------------------------------------------------------
    function [3:0] sbox4;
        input [3:0] x;
        begin
            case (x)
                4'h0: sbox4 = 4'hE;
                4'h1: sbox4 = 4'h4;
                4'h2: sbox4 = 4'hD;
                4'h3: sbox4 = 4'h1;
                4'h4: sbox4 = 4'h2;
                4'h5: sbox4 = 4'hF;
                4'h6: sbox4 = 4'hB;
                4'h7: sbox4 = 4'h8;
                4'h8: sbox4 = 4'h3;
                4'h9: sbox4 = 4'hA;
                4'hA: sbox4 = 4'h6;
                4'hB: sbox4 = 4'hC;
                4'hC: sbox4 = 4'h5;
                4'hD: sbox4 = 4'h9;
                4'hE: sbox4 = 4'h0;
                4'hF: sbox4 = 4'h7;
                default: sbox4 = 4'h0;
            endcase
        end
    endfunction

    // Apply S-box independently to each of the four nibbles of a 16-bit word.
    function [15:0] sbox_layer;
        input [15:0] w;
        begin
            sbox_layer = { sbox4(w[15:12]), sbox4(w[11:8]), sbox4(w[7:4]), sbox4(w[3:0]) };
        end
    endfunction

    // Fixed bit-level permutation applied between rounds (not in final round).
    // Maps output bit position i from input bit position perm_src(i).
    function [15:0] permute;
        input [15:0] w;
        reg   [15:0] p;
        begin
            p[0]  = w[8];
            p[1]  = w[12];
            p[2]  = w[0];
            p[3]  = w[4];
            p[4]  = w[9];
            p[5]  = w[13];
            p[6]  = w[1];
            p[7]  = w[5];
            p[8]  = w[10];
            p[9]  = w[14];
            p[10] = w[2];
            p[11] = w[6];
            p[12] = w[11];
            p[13] = w[15];
            p[14] = w[3];
            p[15] = w[7];
            permute = p;
        end
    endfunction

    // ------------------------------------------------------------------
    // Round-key schedule: round key for round r is key XOR round_const[r].
    // Round constants are fixed, key-independent localparams.
    // ------------------------------------------------------------------
    localparam [15:0] RC0 = 16'h1234;
    localparam [15:0] RC1 = 16'h5A5A;
    localparam [15:0] RC2 = 16'hA5A5;
    localparam [15:0] RC3 = 16'hC3C3;

    wire [15:0] round_key0 = key ^ RC0;
    wire [15:0] round_key1 = key ^ RC1;
    wire [15:0] round_key2 = key ^ RC2;
    wire [15:0] final_key  = key ^ RC3;

    // ------------------------------------------------------------------
    // Pipelined round-state register.
    // ------------------------------------------------------------------
    reg [15:0] state_q;
    reg [2:0]  round_cnt;
    reg        running;

    always @(posedge clk) begin
        if (rst) begin
            state_q    <= 16'h0000;
            round_cnt  <= 3'd0;
            running    <= 1'b0;
            ciphertext <= 16'h0000;
            done       <= 1'b0;
        end else begin
            done <= 1'b0;

            if (start && !running) begin
                // Round 0: mix with round_key0, substitute, permute.
                state_q   <= permute(sbox_layer(plaintext ^ round_key0));
                round_cnt <= 3'd1;
                running   <= 1'b1;
            end else if (running) begin
                case (round_cnt)
                    3'd1: begin
                        // Round 1
                        state_q   <= permute(sbox_layer(state_q ^ round_key1));
                        round_cnt <= 3'd2;
                    end
                    3'd2: begin
                        // Round 2
                        state_q   <= permute(sbox_layer(state_q ^ round_key2));
                        round_cnt <= 3'd3;
                    end
                    3'd3: begin
                        // Final round: substitute, no permute, then XOR final_key.
                        ciphertext <= sbox_layer(state_q) ^ final_key;
                        done       <= 1'b1;
                        running    <= 1'b0;
                        round_cnt  <= 3'd0;
                    end
                    default: begin
                        running   <= 1'b0;
                        round_cnt <= 3'd0;
                    end
                endcase
            end
        end
    end

endmodule