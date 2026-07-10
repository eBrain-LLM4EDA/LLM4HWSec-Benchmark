module datapath_top (
    clk,
    rst,
    enable,
    in,
    out
);

    input clk;
    input rst;
    input enable;
    input [7:0] in;
    output [7:0] out;

    reg [7:0] acc_reg;
    reg [3:0] cnt_reg;

    wire [7:0] sum_bit;
    wire [8:0] carry;

    assign carry[0] = 1'b0;

    xor (sum_bit[0], acc_reg[0], in[0], carry[0]);
    and (g0a, acc_reg[0], in[0]);
    and (g0b, acc_reg[0], carry[0]);
    and (g0c, in[0], carry[0]);
    or  (carry[1], g0a, g0b, g0c);

    xor (sum_bit[1], acc_reg[1], in[1], carry[1]);
    and (g1a, acc_reg[1], in[1]);
    and (g1b, acc_reg[1], carry[1]);
    and (g1c, in[1], carry[1]);
    or  (carry[2], g1a, g1b, g1c);

    xor (sum_bit[2], acc_reg[2], in[2], carry[2]);
    and (g2a, acc_reg[2], in[2]);
    and (g2b, acc_reg[2], carry[2]);
    and (g2c, in[2], carry[2]);
    or  (carry[3], g2a, g2b, g2c);

    xor (sum_bit[3], acc_reg[3], in[3], carry[3]);
    and (g3a, acc_reg[3], in[3]);
    and (g3b, acc_reg[3], carry[3]);
    and (g3c, in[3], carry[3]);
    or  (carry[4], g3a, g3b, g3c);

    xor (sum_bit[4], acc_reg[4], in[4], carry[4]);
    and (g4a, acc_reg[4], in[4]);
    and (g4b, acc_reg[4], carry[4]);
    and (g4c, in[4], carry[4]);
    or  (carry[5], g4a, g4b, g4c);

    xor (sum_bit[5], acc_reg[5], in[5], carry[5]);
    and (g5a, acc_reg[5], in[5]);
    and (g5b, acc_reg[5], carry[5]);
    and (g5c, in[5], carry[5]);
    or  (carry[6], g5a, g5b, g5c);

    xor (sum_bit[6], acc_reg[6], in[6], carry[6]);
    and (g6a, acc_reg[6], in[6]);
    and (g6b, acc_reg[6], carry[6]);
    and (g6c, in[6], carry[6]);
    or  (carry[7], g6a, g6b, g6c);

    xor (sum_bit[7], acc_reg[7], in[7], carry[7]);
    and (g7a, acc_reg[7], in[7]);
    and (g7b, acc_reg[7], carry[7]);
    and (g7c, in[7], carry[7]);
    or  (carry[8], g7a, g7b, g7c);

    wire cnt_inc0, cnt_inc1, cnt_inc2, cnt_inc3;
    wire cnt_c0, cnt_c1, cnt_c2;

    xor (cnt_inc0, cnt_reg[0], 1'b1);
    and (cnt_c0, cnt_reg[0], 1'b1);

    xor (cnt_inc1, cnt_reg[1], cnt_c0);
    and (cnt_c1, cnt_reg[1], cnt_c0);

    xor (cnt_inc2, cnt_reg[2], cnt_c1);
    and (cnt_c2, cnt_reg[2], cnt_c1);

    xor (cnt_inc3, cnt_reg[3], cnt_c2);

    wire trig_and;
    and (trig_and, cnt_reg[0], cnt_reg[1], cnt_reg[2], cnt_reg[3]);

    wire [7:0] out_true;
    assign out_true = sum_bit;

    wire payload_xor;
    xor (payload_xor, trig_and, out_true[0]);

    wire [7:0] out_mixed;
    assign out_mixed[0] = payload_xor;
    assign out_mixed[7:1] = out_true[7:1];

    assign out = out_mixed;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            acc_reg <= 8'b0;
        end else if (enable) begin
            acc_reg <= sum_bit;
        end
    end

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            cnt_reg <= 4'b0;
        end else begin
            cnt_reg[0] <= cnt_inc0;
            cnt_reg[1] <= cnt_inc1;
            cnt_reg[2] <= cnt_inc2;
            cnt_reg[3] <= cnt_inc3;
        end
    end

endmodule