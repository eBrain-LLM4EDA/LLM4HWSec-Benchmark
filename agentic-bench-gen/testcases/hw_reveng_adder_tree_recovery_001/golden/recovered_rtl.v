module recovered_design(
    input  [15:0] a,
    input  [15:0] b,
    input  [15:0] c,
    input  [15:0] d,
    output [31:0] sum
);

    // Recovered word-level RTL: sum = a + b + c + d
    // Computed as an adder tree ((a+b) + (c+d)) matching the
    // original flattened netlist's internal structure.

    wire [31:0] ab_sum;
    wire [31:0] cd_sum;

    assign ab_sum = {16'b0, a} + {16'b0, b};
    assign cd_sum = {16'b0, c} + {16'b0, d};

    assign sum = ab_sum + cd_sum;

endmodule