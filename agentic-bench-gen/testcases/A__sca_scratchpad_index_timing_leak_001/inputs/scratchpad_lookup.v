// scratchpad_lookup.v
// Dual-bank scratchpad memory lookup unit.
//
// On a `start` pulse, latches the requested index and fetches the
// corresponding 16-bit word from one of two internal banks. Bank
// selection is determined by index[7]; the offset within the selected
// bank is index[6:0]. `valid` is asserted for exactly one cycle once
// data_out is ready.

module scratchpad_lookup (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    input  wire [7:0]  index,
    output reg  [15:0] data_out,
    output reg         valid
);

    localparam S_IDLE        = 3'd0;
    localparam S_FAST_WAIT   = 3'd1;
    localparam S_SLOW_WAIT1  = 3'd2;
    localparam S_SLOW_WAIT2  = 3'd3;
    localparam S_SLOW_WAIT3  = 3'd4;
    localparam S_DONE        = 3'd5;

    reg [2:0] state;
    reg [7:0] index_latched;

    reg [15:0] fast_bank [0:127];
    reg [15:0] slow_bank [0:127];

    integer i;
    initial begin
        for (i = 0; i < 128; i = i + 1) begin
            fast_bank[i] = i * 3 + 1;
            slow_bank[i] = i * 5 + 2;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state         <= S_IDLE;
            data_out      <= 16'd0;
            valid         <= 1'b0;
            index_latched <= 8'd0;
        end else begin
            case (state)
                S_IDLE: begin
                    valid <= 1'b0;
                    if (start) begin
                        index_latched <= index;
                        case (index[7])
                            1'b0: state <= S_FAST_WAIT;
                            1'b1: state <= S_SLOW_WAIT1;
                        endcase
                    end
                end

                S_FAST_WAIT: begin
                    data_out <= fast_bank[index_latched[6:0]];
                    valid    <= 1'b1;
                    state    <= S_DONE;
                end

                S_SLOW_WAIT1: begin
                    state <= S_SLOW_WAIT2;
                end

                S_SLOW_WAIT2: begin
                    state <= S_SLOW_WAIT3;
                end

                S_SLOW_WAIT3: begin
                    data_out <= slow_bank[index_latched[6:0]];
                    valid    <= 1'b1;
                    state    <= S_DONE;
                end

                S_DONE: begin
                    valid <= 1'b0;
                    if (start) begin
                        index_latched <= index;
                        case (index[7])
                            1'b0: state <= S_FAST_WAIT;
                            1'b1: state <= S_SLOW_WAIT1;
                        endcase
                    end else begin
                        state <= S_IDLE;
                    end
                end

                default: begin
                    state <= S_IDLE;
                end
            endcase
        end
    end

endmodule