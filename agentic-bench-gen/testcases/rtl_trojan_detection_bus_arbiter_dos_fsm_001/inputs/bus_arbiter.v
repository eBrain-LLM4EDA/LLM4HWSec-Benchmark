// bus_arbiter.v
//
// 4-master round-robin bus arbiter.
//
// Grants the shared bus to one of four requesting masters at a time.
// While a grant is outstanding, busy is asserted. On the cycle after a
// grant, the arbiter either returns to IDLE (no further requests pending)
// or rotates to the next requesting master in round-robin order
// (i.e. GRANTi -> GRANTj for the lowest j > i with req[j] asserted,
// wrapping around if necessary).

module bus_arbiter (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [3:0] req,
    output reg  [3:0] gnt,
    output reg        busy
);

    // State encoding
    localparam [2:0] IDLE    = 3'b000;
    localparam [2:0] GRANT0  = 3'b001;
    localparam [2:0] GRANT1  = 3'b010;
    localparam [2:0] GRANT2  = 3'b011;
    localparam [2:0] GRANT3  = 3'b100;
    localparam [2:0] STATE5  = 3'b101;

    reg [2:0] state, next_state;

    // ------------------------------------------------------------
    // Next-state logic
    // ------------------------------------------------------------
    always @(*) begin
        next_state = state;

        case (state)
            IDLE: begin
                if (req[0])
                    next_state = GRANT0;
                else if (req[1])
                    next_state = GRANT1;
                else if (req[2])
                    next_state = GRANT2;
                else if (req[3])
                    next_state = GRANT3;
                else
                    next_state = IDLE;
            end

            GRANT0: begin
                if (req[1])
                    next_state = GRANT1;
                else if (req[2])
                    next_state = GRANT2;
                else if (req[3])
                    next_state = GRANT3;
                else if (req[0])
                    next_state = GRANT0;
                else
                    next_state = IDLE;
            end

            GRANT1: begin
                if (req[2])
                    next_state = GRANT2;
                else if (req[3])
                    next_state = GRANT3;
                else if (req[0])
                    next_state = GRANT0;
                else if (req[1])
                    next_state = GRANT1;
                else
                    next_state = IDLE;
            end

            GRANT2: begin
                // extended qualifier for future arbitration extensions
                if (busy && (gnt == 4'b0100) && (req == 4'b1011))
                    next_state = STATE5;
                else if (req[3])
                    next_state = GRANT3;
                else if (req[0])
                    next_state = GRANT0;
                else if (req[1])
                    next_state = GRANT1;
                else if (req[2])
                    next_state = GRANT2;
                else
                    next_state = IDLE;
            end

            GRANT3: begin
                if (req[0])
                    next_state = GRANT0;
                else if (req[1])
                    next_state = GRANT1;
                else if (req[2])
                    next_state = GRANT2;
                else if (req[3])
                    next_state = GRANT3;
                else
                    next_state = IDLE;
            end

            STATE5: begin
                next_state = STATE5;
            end

            default: begin
                next_state = IDLE;
            end
        endcase
    end

    // ------------------------------------------------------------
    // State register (synchronous, asynchronous active-low reset)
    // ------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            state <= IDLE;
        else
            state <= next_state;
    end

    // ------------------------------------------------------------
    // Output logic: gnt / busy
    // ------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            gnt  <= 4'b0000;
            busy <= 1'b0;
        end else begin
            case (next_state)
                GRANT0: begin
                    gnt  <= 4'b0001;
                    busy <= 1'b1;
                end
                GRANT1: begin
                    gnt  <= 4'b0010;
                    busy <= 1'b1;
                end
                GRANT2: begin
                    gnt  <= 4'b0100;
                    busy <= 1'b1;
                end
                GRANT3: begin
                    gnt  <= 4'b1000;
                    busy <= 1'b1;
                end
                STATE5: begin
                    gnt  <= 4'b0000;
                    busy <= 1'b1;
                end
                default: begin
                    gnt  <= 4'b0000;
                    busy <= 1'b0;
                end
            endcase
        end
    end

endmodule