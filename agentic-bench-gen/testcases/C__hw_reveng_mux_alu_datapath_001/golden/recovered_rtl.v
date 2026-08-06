module recovered_datapath(
    input  [7:0] a,
    input  [7:0] b,
    input  [1:0] sel,
    output [7:0] y
);

    reg [7:0] y_r;

    always @* begin
        case (sel)
            2'b00: y_r = a + b;
            2'b01: y_r = a - b;
            2'b10: y_r = a & b;
            2'b11: y_r = a | b;
            default: y_r = 8'b0;
        endcase
    end

    assign y = y_r;

endmodule