// mode_sequencer.v
//
// Privilege-mode transition sequencer.
//
// Manages a 2-bit privilege register (priv_reg) through a fixed sequence of
// named states in response to req_demote / req_promote requests.
//
// priv_reg encoding:
//   2'b10 = supervisor (high privilege)
//   2'b00 = user       (low privilege)
//   2'b01, 2'b11       = reserved (unused by this design)
//
// State encoding (4-bit, Moore):
//   IDLE    = 4'd0
//   CHECK   = 4'd1
//   DEMOTE  = 4'd2
//   SETTLE  = 4'd3
//   DONE    = 4'd4
//   PCHECK  = 4'd5
//   PROMOTE = 4'd6
//   PSETTLE = 4'd7
//   PDONE   = 4'd8
//
// Demotion sequence (req_demote):
//   IDLE -> CHECK -> DEMOTE -> SETTLE -> DONE -> IDLE
//     priv_reg is written to 2'b00 only while in state DEMOTE.
//
// Promotion sequence (req_promote):
//   IDLE -> PCHECK -> PROMOTE -> PSETTLE -> PDONE -> IDLE
//     priv_reg is written to 2'b10 only while in state PROMOTE.
//
// done is asserted for exactly one clock cycle, while state == DONE or
// state == PDONE.
//
// Reset: rst_n is active-low, asynchronous. On reset, priv_reg = 2'b10
// (supervisor) and state = IDLE.

`timescale 1ns/1ps

module mode_sequencer (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       req_demote,
    input  wire       req_promote,
    output reg  [1:0] priv_reg,
    output reg  [3:0] state,
    output wire       done
);

    localparam [3:0]
        IDLE    = 4'd0,
        CHECK   = 4'd1,
        DEMOTE  = 4'd2,
        SETTLE  = 4'd3,
        DONE    = 4'd4,
        PCHECK  = 4'd5,
        PROMOTE = 4'd6,
        PSETTLE = 4'd7,
        PDONE   = 4'd8;

    reg [3:0] next_state;

    assign done = (state == DONE) || (state == PDONE);

    // Next-state logic (pure combinational sequencing; does not itself
    // write priv_reg).
    always @(*) begin
        case (state)
            IDLE: begin
                if (req_demote)
                    next_state = CHECK;
                else if (req_promote)
                    next_state = PCHECK;
                else
                    next_state = IDLE;
            end

            CHECK:   next_state = DEMOTE;
            DEMOTE:  next_state = SETTLE;
            SETTLE:  next_state = DONE;
            DONE:    next_state = IDLE;

            PCHECK:  next_state = PROMOTE;
            PROMOTE: next_state = PSETTLE;
            PSETTLE: next_state = PDONE;
            PDONE:   next_state = IDLE;

            default: next_state = IDLE;
        endcase
    end

    // State register and priv_reg write.
    //
    // priv_reg is written in exactly one state per sequence:
    //   - DEMOTE writes priv_reg <= 2'b00 during a demotion sequence.
    //   - PROMOTE writes priv_reg <= 2'b10 during a promotion sequence.
    // All other states perform no write to priv_reg; priv_reg simply
    // retains its previous value while the FSM advances through them.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state    <= IDLE;
            priv_reg <= 2'b10; // reset to supervisor
        end else begin
            state <= next_state;

            case (state)
                DEMOTE:  priv_reg <= 2'b00; // lower to user
                PROMOTE: priv_reg <= 2'b10; // raise to supervisor
                default: priv_reg <= priv_reg; // no change
            endcase
        end
    end

endmodule