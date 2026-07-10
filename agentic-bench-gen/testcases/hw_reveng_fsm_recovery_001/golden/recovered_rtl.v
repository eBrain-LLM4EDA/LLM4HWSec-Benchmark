module recovered_fsm(
    input  clk,
    input  rst,
    input  in,
    output out
);

    localparam S0 = 2'd0; // idle / searching for first '1'
    localparam S1 = 2'd1; // saw '1'
    localparam S2 = 2'd2; // saw '10'
    localparam S3 = 2'd3; // saw '101'

    reg [1:0] state;
    reg [1:0] next_state;
    reg       match_pulse;

    always @(*) begin
        case (state)
            S0: next_state = in ? S1 : S0;
            S1: next_state = in ? S1 : S2;
            S2: next_state = in ? S3 : S0;
            default: next_state = in ? S1 : S0; // S3: pattern completed, non-overlapping restart
        endcase
    end

    always @(*) begin
        // Pulses when the FSM is in S3 (having just consumed the final '1'
        // of the '1011' sequence) — this is the cycle after the pattern
        // completes, matching the Moore output timing of the original netlist.
        match_pulse = (state == S3);
    end

    always @(posedge clk) begin
        if (rst)
            state <= S0;
        else
            state <= next_state;
    end

    assign out = match_pulse;

endmodule