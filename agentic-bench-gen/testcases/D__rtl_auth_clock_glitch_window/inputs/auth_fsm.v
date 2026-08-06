module auth_fsm (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  password,
    output reg         access_granted
);

    // State encoding
    localparam IDLE    = 3'd0;
    localparam COMPARE = 3'd1;
    localparam DECIDE  = 3'd2;
    localparam GRANT   = 3'd3;
    localparam DENY    = 3'd4;

    // Stored password (hardcoded for simplicity)
    localparam [7:0] STORED_PASSWORD = 8'hA5;

    // Registers
    reg [2:0] state_q;
    reg       auth_result_q;

    // Next-state logic
    reg [2:0] state_next;
    reg       auth_result_next;

    always @* begin
        // Defaults
        state_next = state_q;
        auth_result_next = auth_result_q;

        case (state_q)
            IDLE: begin
                state_next = COMPARE;
                auth_result_next = 1'b0;
            end

            COMPARE: begin
                if (password == STORED_PASSWORD)
                    auth_result_next = 1'b1;
                else
                    auth_result_next = 1'b0;
                state_next = DECIDE;
            end

            DECIDE: begin
                if (auth_result_q)
                    state_next = GRANT;
                else
                    state_next = DENY;
                // auth_result_next is not updated here; it retains its value
            end

            GRANT: begin
                state_next = IDLE;
                auth_result_next = 1'b0;
            end

            DENY: begin
                state_next = IDLE;
                auth_result_next = 1'b0;
            end

            default: begin
                state_next = IDLE;
                auth_result_next = 1'b0;
            end
        endcase
    end

    // Sequential update
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_q <= IDLE;
            auth_result_q <= 1'b0;
        end else begin
            state_q <= state_next;
            auth_result_q <= auth_result_next;
        end
    end

    // Output assignment
    always @* begin
        access_granted = (state_q == GRANT);
    end

endmodule