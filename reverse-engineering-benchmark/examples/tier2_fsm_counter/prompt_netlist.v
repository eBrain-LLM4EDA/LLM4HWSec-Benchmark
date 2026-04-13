module fsm_counter (
    input clk,
    input rst_n,
    input en,
    output [1:0] state,
    output [3:0] count
);
    reg s0, s1;
    reg [3:0] c;

    assign state[0] = s0;
    assign state[1] = s1;
    assign count = c;

    wire idle = ~s1 & ~s0;
    wire run  = ~s1 & s0;
    wire hold = s1 & ~s0;

    wire next_s0 = (idle & en) | (run & en) | (hold & en);
    wire next_s1 = (run & ~en);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            s0 <= 1'b0;
            s1 <= 1'b0;
            c <= 4'd0;
        end else begin
            s0 <= next_s0;
            s1 <= next_s1;
            if (run) c <= c + 4'd1;
        end
    end
endmodule
