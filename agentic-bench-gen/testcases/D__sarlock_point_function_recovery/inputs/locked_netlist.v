// locked_netlist.v
// SARLock-style point-function locked circuit
// Functional logic: 8-bit adder (two 4-bit operands -> 5-bit sum)
// Lock: 6-bit key comparator corrupts sum[0] on a single input pattern

module locked_netlist (
    input  [3:0] a,
    input  [3:0] b,
    output [4:0] result
);

    // Internal nets for functional adder
    wire [4:0] sum;
    wire       cout;

    // 4-bit ripple-carry adder
    wire c0, c1, c2;
    wire s0, s1, s2, s3;

    // Bit 0
    xor (s0, a[0], b[0]);
    and (c0, a[0], b[0]);

    // Bit 1
    xor (s1, a[1], b[1]);
    and (c1, a[1], b[1]);

    // Bit 2
    xor (s2, a[2], b[2]);
    and (c2, a[2], b[2]);

    // Bit 3
    xor (s3, a[3], b[3]);
    and (cout, a[3], b[3]);

    assign sum = {cout, s3, s2, s1, s0};

    // Key comparator module
    wire lock_out;
    lock_comp comp (
        .in({a, b}),   // 8-bit input to comparator
        .out(lock_out)
    );

    // Corruption: XOR lock output with sum[0]
    xor (result[0], sum[0], lock_out);

    // Pass through remaining sum bits
    assign result[4:1] = sum[4:1];

endmodule

// 6-bit key comparator: XNOR + AND tree
module lock_comp (
    input  [7:0] in,
    output       out
);

    // Key bits (hidden): 101101
    // Comparator nets
    wire xor_0, xor_1, xor_2, xor_3, xor_4, xor_5;
    wire and_stage1_0, and_stage1_1;
    wire and_stage2;
    wire corrupt_xor;

    // XNOR gates: compare each selected input bit against key bit
    // Key = 101101, mapping: in[0] vs 1, in[1] vs 0, in[2] vs 1, in[3] vs 1, in[4] vs 0, in[5] vs 1
    // XNOR = (in ^ key)'
    // For key bit 1: XNOR = in
    // For key bit 0: XNOR = ~in

    // in[0] vs key[0]=1 -> XNOR = in[0]
    buf (xor_0, in[0]);

    // in[1] vs key[1]=0 -> XNOR = ~in[1]
    not (xor_1, in[1]);

    // in[2] vs key[2]=1 -> XNOR = in[2]
    buf (xor_2, in[2]);

    // in[3] vs key[3]=1 -> XNOR = in[3]
    buf (xor_3, in[3]);

    // in[4] vs key[4]=0 -> XNOR = ~in[4]
    not (xor_4, in[4]);

    // in[5] vs key[5]=1 -> XNOR = in[5]
    buf (xor_5, in[5]);

    // AND tree: first stage
    and (and_stage1_0, xor_0, xor_1, xor_2);
    and (and_stage1_1, xor_3, xor_4, xor_5);

    // Second stage
    and (and_stage2, and_stage1_0, and_stage1_1);

    // Final corruption XOR (output of comparator)
    // This net is the lock output
    buf (corrupt_xor, and_stage2);

    assign out = corrupt_xor;

endmodule