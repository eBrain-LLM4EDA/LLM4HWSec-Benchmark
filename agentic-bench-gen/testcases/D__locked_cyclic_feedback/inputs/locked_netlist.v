// Cyclically locked gate-level netlist
// Function: out = (a & b) | c
// Key width: 2 bits (key[1:0])
// Correct key: 10 (key[1]=1, key[0]=0) selects forward paths and breaks all cycles

module locked_netlist (
    input  wire a, b, c,
    input  wire [1:0] key,
    output wire out
);

    // Internal nets
    wire and_out;
    wire or_out;
    wire fb1_out, fb2_out;
    wire mux1_out, mux2_out;

    // Forward logic
    and g_and (and_out, a, b);
    or  g_or  (or_out, and_out, c);

    // Feedback MUX 1: controlled by key[0]
    // When key[0]=0, selects feedback path (fb1_out) creating a cycle
    // When key[0]=1, selects forward path (or_out) breaking the cycle
    mux2_1 mux_fb1 (
        .in0(fb1_out),
        .in1(or_out),
        .sel(key[0]),
        .out(mux1_out)
    );

    // Feedback MUX 2: controlled by key[1]
    // When key[1]=0, selects feedback path (fb2_out) creating a cycle
    // When key[1]=1, selects forward path (mux1_out) breaking the cycle
    mux2_1 mux_fb2 (
        .in0(fb2_out),
        .in1(mux1_out),
        .sel(key[1]),
        .out(mux2_out)
    );

    // Feedback loops
    // fb1_out is the output of mux_fb2, creating a cycle when key[0]=0
    assign fb1_out = mux2_out;

    // fb2_out is the output of mux_fb1, creating a cycle when key[1]=0
    assign fb2_out = mux1_out;

    // Final output
    assign out = mux2_out;

endmodule

// Simple 2-to-1 multiplexer primitive
module mux2_1 (
    input  wire in0, in1, sel,
    output wire out
);
    assign out = sel ? in1 : in0;
endmodule