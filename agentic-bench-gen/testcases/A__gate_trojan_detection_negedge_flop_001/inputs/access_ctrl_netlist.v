// access_ctrl_netlist.v
// Flat gate-level netlist for access_ctrl_top.
// Built entirely from primitives declared in cell_library.v.

`timescale 1ns/1ps

module access_ctrl_top (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [7:0] key_in,
    input  wire       req_valid,
    output wire       grant_out
);

    // Internal fixed reference value used for key comparison.
    localparam [7:0] REF_KEY = 8'hA5;

    // -------------------------------------------------------------------
    // Request strobe pipeline register
    // -------------------------------------------------------------------
    wire req_valid_q;

    DFF_POSEDGE u_req_ff (
        .clk   (clk),
        .d     (req_valid),
        .q     (req_valid_q),
        .rst_n (rst_n)
    );

    // -------------------------------------------------------------------
    // Key staging register
    // -------------------------------------------------------------------
    wire [7:0] key_in_q;

    DFF_POSEDGE u_key_reg0 (.clk(clk), .d(key_in[0]), .q(key_in_q[0]), .rst_n(rst_n));
    DFF_POSEDGE u_key_reg1 (.clk(clk), .d(key_in[1]), .q(key_in_q[1]), .rst_n(rst_n));
    DFF_POSEDGE u_key_reg2 (.clk(clk), .d(key_in[2]), .q(key_in_q[2]), .rst_n(rst_n));
    DFF_POSEDGE u_key_reg3 (.clk(clk), .d(key_in[3]), .q(key_in_q[3]), .rst_n(rst_n));
    DFF_POSEDGE u_key_reg4 (.clk(clk), .d(key_in[4]), .q(key_in_q[4]), .rst_n(rst_n));
    DFF_POSEDGE u_key_reg5 (.clk(clk), .d(key_in[5]), .q(key_in_q[5]), .rst_n(rst_n));
    DFF_POSEDGE u_key_reg6 (.clk(clk), .d(key_in[6]), .q(key_in_q[6]), .rst_n(rst_n));
    DFF_POSEDGE u_key_reg7 (.clk(clk), .d(key_in[7]), .q(key_in_q[7]), .rst_n(rst_n));

    // -------------------------------------------------------------------
    // Bitwise comparison tree: key_in_q vs REF_KEY
    // -------------------------------------------------------------------
    wire [7:0] cmp_xor;
    wire [7:0] cmp_eq;

    XOR2 u_xor0 (.a(key_in_q[0]), .b(REF_KEY[0]), .y(cmp_xor[0]));
    XOR2 u_xor1 (.a(key_in_q[1]), .b(REF_KEY[1]), .y(cmp_xor[1]));
    XOR2 u_xor2 (.a(key_in_q[2]), .b(REF_KEY[2]), .y(cmp_xor[2]));
    XOR2 u_xor3 (.a(key_in_q[3]), .b(REF_KEY[3]), .y(cmp_xor[3]));
    XOR2 u_xor4 (.a(key_in_q[4]), .b(REF_KEY[4]), .y(cmp_xor[4]));
    XOR2 u_xor5 (.a(key_in_q[5]), .b(REF_KEY[5]), .y(cmp_xor[5]));
    XOR2 u_xor6 (.a(key_in_q[6]), .b(REF_KEY[6]), .y(cmp_xor[6]));
    XOR2 u_xor7 (.a(key_in_q[7]), .b(REF_KEY[7]), .y(cmp_xor[7]));

    INV u_inv0 (.a(cmp_xor[0]), .y(cmp_eq[0]));
    INV u_inv1 (.a(cmp_xor[1]), .y(cmp_eq[1]));
    INV u_inv2 (.a(cmp_xor[2]), .y(cmp_eq[2]));
    INV u_inv3 (.a(cmp_xor[3]), .y(cmp_eq[3]));
    INV u_inv4 (.a(cmp_xor[4]), .y(cmp_eq[4]));
    INV u_inv5 (.a(cmp_xor[5]), .y(cmp_eq[5]));
    INV u_inv6 (.a(cmp_xor[6]), .y(cmp_eq[6]));
    INV u_inv7 (.a(cmp_xor[7]), .y(cmp_eq[7]));

    wire and_lo, and_hi;
    wire and_lo_a, and_lo_b, and_hi_a, and_hi_b;

    AND2 u_and_lo_a (.a(cmp_eq[0]), .b(cmp_eq[1]), .y(and_lo_a));
    AND2 u_and_lo_b (.a(cmp_eq[2]), .b(cmp_eq[3]), .y(and_lo_b));
    AND2 u_and_lo   (.a(and_lo_a),  .b(and_lo_b),  .y(and_lo));

    AND2 u_and_hi_a (.a(cmp_eq[4]), .b(cmp_eq[5]), .y(and_hi_a));
    AND2 u_and_hi_b (.a(cmp_eq[6]), .b(cmp_eq[7]), .y(and_hi_b));
    AND2 u_and_hi   (.a(and_hi_a),  .b(and_hi_b),  .y(and_hi));

    // grant_pre: raw (unregistered) permission decision from comparator tree.
    wire grant_pre;
    AND2 u_and_final (.a(and_lo), .b(and_hi), .y(grant_pre));

    // Intermediate comparator staging register.
    wire cmp_stage_q;
    DFF_POSEDGE u_cmp_ff (
        .clk   (clk),
        .d     (grant_pre),
        .q     (cmp_stage_q),
        .rst_n (rst_n)
    );

    // -------------------------------------------------------------------
    // Grant permission register
    // -------------------------------------------------------------------
    wire grant_q;

    DFF_NEGEDGE u_grant_ff (
        .clk   (clk),
        .d     (grant_pre),
        .q     (grant_q),
        .rst_n (rst_n)
    );

    // -------------------------------------------------------------------
    // Final output combine and register
    // -------------------------------------------------------------------
    wire grant_and_req;

    AND2 u_out_and (
        .a (grant_q),
        .b (req_valid_q),
        .y (grant_and_req)
    );

    DFF_POSEDGE u_out_ff (
        .clk   (clk),
        .d     (grant_and_req),
        .q     (grant_out),
        .rst_n (rst_n)
    );

endmodule