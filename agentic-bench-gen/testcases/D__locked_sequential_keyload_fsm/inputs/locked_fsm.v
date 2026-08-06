module top (
    input  wire clk,
    input  wire rst_n,
    input  wire key_in,
    input  wire data_in,
    output wire data_out
);

    // State encoding
    localparam [1:0] IDLE       = 2'b00,
                     LOADING    = 2'b01,
                     DECOY      = 2'b10,
                     FUNCTIONAL = 2'b11;

    reg [1:0] state, next_state;
    reg [3:0] lock_reg;
    reg [1:0] load_cnt;  // counts 0..3 loading cycles

    // Asynchronous reset, synchronous state and counter update
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state    <= IDLE;
            lock_reg <= 4'b0000;
            load_cnt <= 2'b00;
        end else begin
            state    <= next_state;
            if (state == LOADING) begin
                lock_reg <= {lock_reg[2:0], key_in};
                load_cnt <= load_cnt + 1;
            end
        end
    end

    // Next-state logic
    always @(*) begin
        next_state = state;
        case (state)
            IDLE: begin
                // After reset de-assertion, start loading
                next_state = LOADING;
            end
            LOADING: begin
                if (load_cnt == 2'b11) begin
                    // After 4 bits loaded, check the pattern
                    // Pattern: lock_reg[3]==0, lock_reg[2]==1, lock_reg[1]==1, lock_reg[0]==0
                    if (!lock_reg[3] && lock_reg[2] && lock_reg[1] && !lock_reg[0])
                        next_state = FUNCTIONAL;
                    else
                        next_state = DECOY;
                end
            end
            DECOY:       next_state = DECOY;
            FUNCTIONAL:  next_state = FUNCTIONAL;
            default:     next_state = IDLE;
        endcase
    end

    // Output logic
    assign data_out = (state == FUNCTIONAL) ? data_in : ~data_in;

endmodule