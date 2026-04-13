module alu_control8 (
    input [7:0] a,
    input [7:0] b,
    input op0,
    input op1,
    output [7:0] y,
    output zero
);
    wire [7:0] y_add = a + b;
    wire [7:0] y_sub = a - b;
    wire [7:0] y_xor = a ^ b;
    wire [7:0] y_and = a & b;

    wire sel_add = ~op1 & ~op0;
    wire sel_sub = ~op1 & op0;
    wire sel_xor = op1 & ~op0;

    assign y = ({8{sel_add}} & y_add)
             | ({8{sel_sub}} & y_sub)
             | ({8{sel_xor}} & y_xor)
             | ({8{~(sel_add | sel_sub | sel_xor)}} & y_and);

    assign zero = ~|y;
endmodule
