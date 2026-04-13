module fsm_counter (
    input clk,
    input rst_n,
    input en,
    output reg [1:0] state,
    output reg [3:0] count
);
    localparam IDLE = 2'b00;
    localparam RUN  = 2'b01;
    localparam HOLD = 2'b10;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            count <= 4'd0;
        end else begin
            case (state)
                IDLE: begin
                    if (en) state <= RUN;
                end
                RUN: begin
                    count <= count + 4'd1;
                    if (!en) state <= HOLD;
                end
                HOLD: begin
                    if (en) state <= RUN;
                    else state <= IDLE;
                end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
