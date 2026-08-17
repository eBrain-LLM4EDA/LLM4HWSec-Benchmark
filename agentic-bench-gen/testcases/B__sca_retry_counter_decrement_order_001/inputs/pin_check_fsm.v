//----------------------------------------------------------------------------
// pin_check_fsm.v
//
// Legacy PIN-check authentication controller.
//
// Protocol summary:
//   - Present an 8-bit candidate on pin_in and pulse pin_valid for one
//     cycle to request a comparison against the stored secret PIN.
//   - The controller performs the comparison, records the outcome, and
//     updates the retry counter (attempts_left) bookkeeping.
//   - On a correct match (and if not locked out), auth_ok pulses for
//     exactly one cycle, two cycles after the pin_valid strobe.
//   - After three consecutive failed attempts, the controller enters a
//     permanent lockout state (locked_out stays asserted) until the
//     next reset.
//
// This module is intended for a simple embedded access-control device
// with a small, fixed retry budget.
//----------------------------------------------------------------------------

module pin_check_fsm(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  pin_in,
    input  wire        pin_valid,
    output reg         auth_ok,
    output reg         locked_out,
    output reg  [3:0]  attempts_left
);

    // Stored secret PIN (fixed for this device revision).
    localparam [7:0] SECRET_PIN = 8'hA5;

    // FSM state encoding.
    localparam [1:0] IDLE       = 2'd0;
    localparam [1:0] COMPARE    = 2'd1;
    localparam [1:0] CHECK_DONE = 2'd2;
    localparam [1:0] LOCKOUT    = 2'd3;

    reg [1:0] state, next_state;

    // Latched result of the comparison performed in COMPARE.
    reg match_reg;

    //------------------------------------------------------------------
    // State register
    //------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n)
            state <= IDLE;
        else
            state <= next_state;
    end

    //------------------------------------------------------------------
    // Next-state logic
    //------------------------------------------------------------------
    always @(*) begin
        next_state = state;
        case (state)
            IDLE: begin
                if (pin_valid)
                    next_state = COMPARE;
                else
                    next_state = IDLE;
            end

            COMPARE: begin
                // One cycle to let the comparison settle before the
                // bookkeeping state evaluates it.
                next_state = CHECK_DONE;
            end

            CHECK_DONE: begin
                if (match_reg)
                    next_state = IDLE;
                else if (attempts_left == 4'd1)
                    // This failed attempt will exhaust the last retry.
                    next_state = LOCKOUT;
                else
                    next_state = IDLE;
            end

            LOCKOUT: begin
                // Permanent until reset.
                next_state = LOCKOUT;
            end

            default: next_state = IDLE;
        endcase
    end

    //------------------------------------------------------------------
    // Comparison latch: evaluated combinationally while in COMPARE,
    // captured into match_reg on the clock edge leaving COMPARE.
    //------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n)
            match_reg <= 1'b0;
        else if (state == COMPARE)
            match_reg <= (pin_in == SECRET_PIN);
    end

    //------------------------------------------------------------------
    // Retry counter bookkeeping.
    //
    // The counter is only touched in CHECK_DONE, after the comparison
    // result (match_reg) has already been latched: a failed comparison
    // consumes one retry; a successful comparison leaves the counter
    // untouched.
    //------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            attempts_left <= 4'd3;
        end else if (state == CHECK_DONE) begin
            if (!match_reg && attempts_left != 4'd0)
                attempts_left <= attempts_left - 4'd1;
        end
    end

    //------------------------------------------------------------------
    // locked_out: asserted the cycle after the retry counter is
    // exhausted by a failed comparison, and held until reset.
    //------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n)
            locked_out <= 1'b0;
        else if (state == CHECK_DONE && !match_reg && attempts_left == 4'd1)
            locked_out <= 1'b1;
    end

    //------------------------------------------------------------------
    // auth_ok: one-cycle pulse in CHECK_DONE when the comparison
    // succeeded (and the device was not already locked out).
    //------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n)
            auth_ok <= 1'b0;
        else if (state == CHECK_DONE && match_reg && !locked_out)
            auth_ok <= 1'b1;
        else
            auth_ok <= 1'b0;
    end

endmodule