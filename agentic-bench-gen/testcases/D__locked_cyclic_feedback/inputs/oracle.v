// Combinational oracle module
// Implements the correct function: out = (a & b) | c
// No key inputs, no cycles

module oracle (
    input  wire a, b, c,
    output wire out
);

    wire and_out;

    and g_and (and_out, a, b);
    or  g_or  (out, and_out, c);

endmodule