module locked_netlist (
    input wire [1:0] a,
    input wire [1:0] b,
    input wire [3:0] key,
    output wire [1:0] y
);

    // Internal wires for functional core
    wire n1, n2, n3, n4;
    wire locked_n1, locked_n2, locked_n3, locked_n4;

    // Functional core: simple combinational logic
    // y[0] = (a[0] & b[0]) | (a[1] ^ b[1])
    // y[1] = (a[0] | b[0]) & (a[1] ^~ b[1])
    and (n1, a[0], b[0]);
    xor (n2, a[1], b[1]);
    or  (n3, a[0], b[0]);
    xnor(n4, a[1], b[1]);

    // Lock gate 0: XOR key gate (key[0]=0 restores signal)
    xor lock_gate_0 (locked_n1, n1, key[0]);

    // Lock gate 1: XNOR key gate (key[1]=1 restores signal)
    xnor lock_gate_1 (locked_n2, n2, key[1]);

    // Lock gate 2: MUX that passes through when key[2]=0
    // If key[2]=0, output = n3; else output = ~n3
    wire mux2_inv;
    not (mux2_inv, n3);
    assign locked_n3 = key[2] ? mux2_inv : n3;

    // Lock gate 3: MUX that passes through when key[3]=1
    // If key[3]=1, output = n4; else output = ~n4
    wire mux3_inv;
    not (mux3_inv, n4);
    assign locked_n4 = key[3] ? n4 : mux3_inv;

    // Output logic
    or  (y[0], locked_n1, locked_n2);
    and (y[1], locked_n3, locked_n4);

endmodule