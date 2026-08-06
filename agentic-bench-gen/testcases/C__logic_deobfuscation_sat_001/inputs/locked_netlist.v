// locked_netlist.v
// A simple combinational circuit: 4-bit comparator with parity output.
// Uses XOR gates for parity computation and a 2-to-1 MUX for output selection.
// No key ports, no key-gate logic, no locking cone.

module locked_netlist (
    input  [3:0] a,
    input  [3:0] b,
    input        sel,
    output       result
);

    // Internal nets
    wire [3:0] xor_out;
    wire       parity;
    wire       comp_eq;

    // XOR gates for bitwise comparison
    xor xor_gate_0 (xor_out[0], a[0], b[0]);
    xor xor_gate_1 (xor_out[1], a[1], b[1]);
    xor xor_gate_2 (xor_out[2], a[2], b[2]);
    xor xor_gate_3 (xor_out[3], a[3], b[3]);

    // Parity computation: XOR tree over xor_out
    wire parity_01, parity_23;
    xor xor_parity_01 (parity_01, xor_out[0], xor_out[1]);
    xor xor_parity_23 (parity_23, xor_out[2], xor_out[3]);
    xor xor_parity    (parity,    parity_01, parity_23);

    // Equality check: all xor_out bits must be 0
    nor nor_eq_0 (comp_eq, xor_out[0], xor_out[1], xor_out[2], xor_out[3]);

    // 2-to-1 MUX: select between parity and equality result
    wire mux_out;
    assign mux_out = sel ? parity : comp_eq;

    // Output buffer
    buf buf_result (result, mux_out);

endmodule