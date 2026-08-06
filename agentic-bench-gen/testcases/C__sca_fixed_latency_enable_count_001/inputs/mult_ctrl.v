// mult_ctrl.v
//
// Fixed-latency shift-add multiplier controller.
//
// Multiplies secret_operand (multiplicand) by public_operand (multiplier)
// using a straightforward 8-cycle shift-add sequence. A transaction always
// takes exactly 8 cycles from the sampled 'start' pulse to the 'done'
// pulse, regardless of operand values.
//
// Ports:
//   clk            - system clock
//   rst_n          - synchronous active-low reset
//   start          - 1-cycle pulse; begins a transaction when idle
//   secret_operand - 8-bit multiplicand
//   public_operand - 8-bit multiplier
//   done           - 1-cycle Moore output pulse, asserted exactly 8 cycles
//                    after the cycle in which start was sampled while idle
//   product        - 16-bit result, valid and held from the cycle done is
//                    asserted until the next start
//   mul_en         - internal accumulate-enable strobe, exposed for
//                    observability/debug

module mult_ctrl (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    input  wire [7:0]  secret_operand,
    input  wire [7:0]  public_operand,
    output reg         done,
    output reg  [15:0] product,
    output wire        mul_en
);

    localparam [3:0] ST_IDLE = 4'd0;
    localparam [3:0] ST_C1   = 4'd1;
    localparam [3:0] ST_C2   = 4'd2;
    localparam [3:0] ST_C3   = 4'd3;
    localparam [3:0] ST_C4   = 4'd4;
    localparam [3:0] ST_C5   = 4'd5;
    localparam [3:0] ST_C6   = 4'd6;
    localparam [3:0] ST_C7   = 4'd7;
    localparam [3:0] ST_C8   = 4'd8;

    reg [3:0] state;
    reg [7:0] operand_latched;
    reg [7:0] multiplier_latched;
    reg [15:0] accum;

    // Cycle index k (1..8) corresponding to the current active state.
    // Used to pick which secret_operand bit gates accumulation this cycle.
    function [3:0] cycle_index;
        input [3:0] st;
        begin
            case (st)
                ST_C1: cycle_index = 4'd1;
                ST_C2: cycle_index = 4'd2;
                ST_C3: cycle_index = 4'd3;
                ST_C4: cycle_index = 4'd4;
                ST_C5: cycle_index = 4'd5;
                ST_C6: cycle_index = 4'd6;
                ST_C7: cycle_index = 4'd7;
                ST_C8: cycle_index = 4'd8;
                default: cycle_index = 4'd0;
            endcase
        end
    endfunction

    wire [3:0] cur_cycle = cycle_index(state);
    wire [3:0] bit_pos   = 8 - cur_cycle;
    wire       active    = (state != ST_IDLE);

    // mul_en is combinationally derived from FSM state and the operand bit
    // corresponding to the current cycle in the MSB-first scan.
    assign mul_en = active && operand_latched[bit_pos];

    always @(posedge clk) begin
        if (!rst_n) begin
            state               <= ST_IDLE;
            done                <= 1'b0;
            product             <= 16'd0;
            accum               <= 16'd0;
            operand_latched     <= 8'd0;
            multiplier_latched  <= 8'd0;
        end else begin
            done <= 1'b0;

            case (state)
                ST_IDLE: begin
                    if (start) begin
                        operand_latched    <= secret_operand;
                        multiplier_latched <= public_operand;
                        accum              <= 16'd0;
                        state              <= ST_C1;
                    end
                end

                ST_C1, ST_C2, ST_C3, ST_C4,
                ST_C5, ST_C6, ST_C7, ST_C8: begin
                    if (mul_en)
                        accum <= accum + ({8'd0, multiplier_latched} << (8 - cur_cycle));
                    // else hold accumulator value unchanged

                    if (state == ST_C8) begin
                        product <= accum + (mul_en ? ({8'd0, multiplier_latched} << 0) : 16'd0);
                        done    <= 1'b1;
                        state   <= ST_IDLE;
                    end else begin
                        state <= state + 4'd1;
                    end
                end

                default: state <= ST_IDLE;
            endcase
        end
    end

endmodule