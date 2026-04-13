module adder8 (
    input a_0,
    input a_1,
    input a_2,
    input a_3,
    input a_4,
    input a_5,
    input a_6,
    input a_7,
    input b_0,
    input b_1,
    input b_2,
    input b_3,
    input b_4,
    input b_5,
    input b_6,
    input b_7,
    output sum_0,
    output sum_1,
    output sum_2,
    output sum_3,
    output sum_4,
    output sum_5,
    output sum_6,
    output sum_7
);
    wire [8:0] carry;
    assign carry[0] = 1'b0;
    assign {carry[1], sum_0} = a_0 + b_0 + carry[0];
    assign {carry[2], sum_1} = a_1 + b_1 + carry[1];
    assign {carry[3], sum_2} = a_2 + b_2 + carry[2];
    assign {carry[4], sum_3} = a_3 + b_3 + carry[3];
    assign {carry[5], sum_4} = a_4 + b_4 + carry[4];
    assign {carry[6], sum_5} = a_5 + b_5 + carry[5];
    assign {carry[7], sum_6} = a_6 + b_6 + carry[6];
    assign {carry[8], sum_7} = a_7 + b_7 + carry[7];
endmodule
