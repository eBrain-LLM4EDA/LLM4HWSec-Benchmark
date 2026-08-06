// net_shifter_flat.v
// Flattened, auto-generated gate-level netlist.
// WARNING: this file was produced by a netlist-flattening tool.
// Original hierarchy, module names, and signal names have been lost.
// Do not hand-edit.

`timescale 1ns/1ps

module mux2 (
    input  a,
    input  b,
    input  s,
    output y
);
    // y = s ? b : a
    assign y = (a & ~s) | (b & s);
endmodule

module net_shifter_flat (
    input  [7:0] data_in,
    input  [2:0] amount,
    input        direction,
    input  [1:0] mode,
    output [7:0] data_out
);

    // ---------------------------------------------------------------
    // Stage L0 : logical left shift datapath, staged by amount bits
    // amount[0] -> shift by 1, amount[1] -> shift by 2, amount[2] -> shift by 4
    // ---------------------------------------------------------------
    wire [7:0] n1;  // after shift-by-1 (left)
    wire [7:0] n2;  // after shift-by-2 (left)
    wire [7:0] n3;  // after shift-by-4 (left) = logical left shift result

    assign n1[0] = mux2_out_l1_0;
    // (explicit per-bit generate below to keep things "flattened")

    // ---- logical left shift by 1 ----
    wire mux2_out_l1_0, mux2_out_l1_1, mux2_out_l1_2, mux2_out_l1_3,
         mux2_out_l1_4, mux2_out_l1_5, mux2_out_l1_6, mux2_out_l1_7;
    mux2 u_l1_0 (.a(data_in[0]), .b(1'b0),       .s(amount[0]), .y(mux2_out_l1_0));
    mux2 u_l1_1 (.a(data_in[1]), .b(data_in[0]), .s(amount[0]), .y(mux2_out_l1_1));
    mux2 u_l1_2 (.a(data_in[2]), .b(data_in[1]), .s(amount[0]), .y(mux2_out_l1_2));
    mux2 u_l1_3 (.a(data_in[3]), .b(data_in[2]), .s(amount[0]), .y(mux2_out_l1_3));
    mux2 u_l1_4 (.a(data_in[4]), .b(data_in[3]), .s(amount[0]), .y(mux2_out_l1_4));
    mux2 u_l1_5 (.a(data_in[5]), .b(data_in[4]), .s(amount[0]), .y(mux2_out_l1_5));
    mux2 u_l1_6 (.a(data_in[6]), .b(data_in[5]), .s(amount[0]), .y(mux2_out_l1_6));
    mux2 u_l1_7 (.a(data_in[7]), .b(data_in[6]), .s(amount[0]), .y(mux2_out_l1_7));

    assign n1 = {mux2_out_l1_7, mux2_out_l1_6, mux2_out_l1_5, mux2_out_l1_4,
                 mux2_out_l1_3, mux2_out_l1_2, mux2_out_l1_1, mux2_out_l1_0};

    // ---- logical left shift by 2 ----
    wire w_a0, w_a1, w_a2, w_a3, w_a4, w_a5, w_a6, w_a7;
    mux2 u_l2_0 (.a(n1[0]), .b(1'b0),  .s(amount[1]), .y(w_a0));
    mux2 u_l2_1 (.a(n1[1]), .b(1'b0),  .s(amount[1]), .y(w_a1));
    mux2 u_l2_2 (.a(n1[2]), .b(n1[0]), .s(amount[1]), .y(w_a2));
    mux2 u_l2_3 (.a(n1[3]), .b(n1[1]), .s(amount[1]), .y(w_a3));
    mux2 u_l2_4 (.a(n1[4]), .b(n1[2]), .s(amount[1]), .y(w_a4));
    mux2 u_l2_5 (.a(n1[5]), .b(n1[3]), .s(amount[1]), .y(w_a5));
    mux2 u_l2_6 (.a(n1[6]), .b(n1[4]), .s(amount[1]), .y(w_a6));
    mux2 u_l2_7 (.a(n1[7]), .b(n1[5]), .s(amount[1]), .y(w_a7));

    assign n2 = {w_a7, w_a6, w_a5, w_a4, w_a3, w_a2, w_a1, w_a0};

    // ---- logical left shift by 4 ----
    wire w_b0, w_b1, w_b2, w_b3, w_b4, w_b5, w_b6, w_b7;
    mux2 u_l4_0 (.a(n2[0]), .b(1'b0), .s(amount[2]), .y(w_b0));
    mux2 u_l4_1 (.a(n2[1]), .b(1'b0), .s(amount[2]), .y(w_b1));
    mux2 u_l4_2 (.a(n2[2]), .b(1'b0), .s(amount[2]), .y(w_b2));
    mux2 u_l4_3 (.a(n2[3]), .b(1'b0), .s(amount[2]), .y(w_b3));
    mux2 u_l4_4 (.a(n2[4]), .b(n2[0]), .s(amount[2]), .y(w_b4));
    mux2 u_l4_5 (.a(n2[5]), .b(n2[1]), .s(amount[2]), .y(w_b5));
    mux2 u_l4_6 (.a(n2[6]), .b(n2[2]), .s(amount[2]), .y(w_b6));
    mux2 u_l4_7 (.a(n2[7]), .b(n2[3]), .s(amount[2]), .y(w_b7));

    assign n3 = {w_b7, w_b6, w_b5, w_b4, w_b3, w_b2, w_b1, w_b0};
    // n3 = logical left shift of data_in by amount, zero-filled

    // ---------------------------------------------------------------
    // Stage R0 : logical right shift datapath (zero-fill), staged
    // ---------------------------------------------------------------
    wire [7:0] m1, m2, m3;

    wire mux2_out_r1_0, mux2_out_r1_1, mux2_out_r1_2, mux2_out_r1_3,
         mux2_out_r1_4, mux2_out_r1_5, mux2_out_r1_6, mux2_out_r1_7;
    mux2 u_r1_0 (.a(data_in[0]), .b(data_in[1]), .s(amount[0]), .y(mux2_out_r1_0));
    mux2 u_r1_1 (.a(data_in[1]), .b(data_in[2]), .s(amount[0]), .y(mux2_out_r1_1));
    mux2 u_r1_2 (.a(data_in[2]), .b(data_in[3]), .s(amount[0]), .y(mux2_out_r1_2));
    mux2 u_r1_3 (.a(data_in[3]), .b(data_in[4]), .s(amount[0]), .y(mux2_out_r1_3));
    mux2 u_r1_4 (.a(data_in[4]), .b(data_in[5]), .s(amount[0]), .y(mux2_out_r1_4));
    mux2 u_r1_5 (.a(data_in[5]), .b(data_in[6]), .s(amount[0]), .y(mux2_out_r1_5));
    mux2 u_r1_6 (.a(data_in[6]), .b(data_in[7]), .s(amount[0]), .y(mux2_out_r1_6));
    mux2 u_r1_7 (.a(data_in[7]), .b(1'b0),       .s(amount[0]), .y(mux2_out_r1_7));

    assign m1 = {mux2_out_r1_7, mux2_out_r1_6, mux2_out_r1_5, mux2_out_r1_4,
                 mux2_out_r1_3, mux2_out_r1_2, mux2_out_r1_1, mux2_out_r1_0};

    wire w_c0, w_c1, w_c2, w_c3, w_c4, w_c5, w_c6, w_c7;
    mux2 u_r2_0 (.a(m1[0]), .b(m1[2]), .s(amount[1]), .y(w_c0));
    mux2 u_r2_1 (.a(m1[1]), .b(m1[3]), .s(amount[1]), .y(w_c1));
    mux2 u_r2_2 (.a(m1[2]), .b(m1[4]), .s(amount[1]), .y(w_c2));
    mux2 u_r2_3 (.a(m1[3]), .b(m1[5]), .s(amount[1]), .y(w_c3));
    mux2 u_r2_4 (.a(m1[4]), .b(m1[6]), .s(amount[1]), .y(w_c4));
    mux2 u_r2_5 (.a(m1[5]), .b(m1[7]), .s(amount[1]), .y(w_c5));
    mux2 u_r2_6 (.a(m1[6]), .b(1'b0),  .s(amount[1]), .y(w_c6));
    mux2 u_r2_7 (.a(m1[7]), .b(1'b0),  .s(amount[1]), .y(w_c7));

    assign m2 = {w_c7, w_c6, w_c5, w_c4, w_c3, w_c2, w_c1, w_c0};

    wire w_d0, w_d1, w_d2, w_d3, w_d4, w_d5, w_d6, w_d7;
    mux2 u_r4_0 (.a(m2[0]), .b(m2[4]), .s(amount[2]), .y(w_d0));
    mux2 u_r4_1 (.a(m2[1]), .b(m2[5]), .s(amount[2]), .y(w_d1));
    mux2 u_r4_2 (.a(m2[2]), .b(m2[6]), .s(amount[2]), .y(w_d2));
    mux2 u_r4_3 (.a(m2[3]), .b(m2[7]), .s(amount[2]), .y(w_d3));
    mux2 u_r4_4 (.a(m2[4]), .b(1'b0),  .s(amount[2]), .y(w_d4));
    mux2 u_r4_5 (.a(m2[5]), .b(1'b0),  .s(amount[2]), .y(w_d5));
    mux2 u_r4_6 (.a(m2[6]), .b(1'b0),  .s(amount[2]), .y(w_d6));
    mux2 u_r4_7 (.a(m2[7]), .b(1'b0),  .s(amount[2]), .y(w_d7));

    assign m3 = {w_d7, w_d6, w_d5, w_d4, w_d3, w_d2, w_d1, w_d0};
    // m3 = logical right shift of data_in by amount, zero-filled

    // ---------------------------------------------------------------
    // Stage RS0 : arithmetic right shift datapath (sign-fill), staged
    // ---------------------------------------------------------------
    wire sbit;
    assign sbit = data_in[7];

    wire [7:0] s1, s2, s3;

    wire w_e0, w_e1, w_e2, w_e3, w_e4, w_e5, w_e6, w_e7;
    mux2 u_s1_0 (.a(data_in[0]), .b(data_in[1]), .s(amount[0]), .y(w_e0));
    mux2 u_s1_1 (.a(data_in[1]), .b(data_in[2]), .s(amount[0]), .y(w_e1));
    mux2 u_s1_2 (.a(data_in[2]), .b(data_in[3]), .s(amount[0]), .y(w_e2));
    mux2 u_s1_3 (.a(data_in[3]), .b(data_in[4]), .s(amount[0]), .y(w_e3));
    mux2 u_s1_4 (.a(data_in[4]), .b(data_in[5]), .s(amount[0]), .y(w_e4));
    mux2 u_s1_5 (.a(data_in[5]), .b(data_in[6]), .s(amount[0]), .y(w_e5));
    mux2 u_s1_6 (.a(data_in[6]), .b(data_in[7]), .s(amount[0]), .y(w_e6));
    mux2 u_s1_7 (.a(data_in[7]), .b(sbit),       .s(amount[0]), .y(w_e7));

    assign s1 = {w_e7, w_e6, w_e5, w_e4, w_e3, w_e2, w_e1, w_e0};

    wire w_f0, w_f1, w_f2, w_f3, w_f4, w_f5, w_f6, w_f7;
    mux2 u_s2_0 (.a(s1[0]), .b(s1[2]), .s(amount[1]), .y(w_f0));
    mux2 u_s2_1 (.a(s1[1]), .b(s1[3]), .s(amount[1]), .y(w_f1));
    mux2 u_s2_2 (.a(s1[2]), .b(s1[4]), .s(amount[1]), .y(w_f2));
    mux2 u_s2_3 (.a(s1[3]), .b(s1[5]), .s(amount[1]), .y(w_f3));
    mux2 u_s2_4 (.a(s1[4]), .b(s1[6]), .s(amount[1]), .y(w_f4));
    mux2 u_s2_5 (.a(s1[5]), .b(s1[7]), .s(amount[1]), .y(w_f5));
    mux2 u_s2_6 (.a(s1[6]), .b(sbit),  .s(amount[1]), .y(w_f6));
    mux2 u_s2_7 (.a(s1[7]), .b(sbit),  .s(amount[1]), .y(w_f7));

    assign s2 = {w_f7, w_f6, w_f5, w_f4, w_f3, w_f2, w_f1, w_f0};

    wire w_g0, w_g1, w_g2, w_g3, w_g4, w_g5, w_g6, w_g7;
    mux2 u_s4_0 (.a(s2[0]), .b(s2[4]), .s(amount[2]), .y(w_g0));
    mux2 u_s4_1 (.a(s2[1]), .b(s2[5]), .s(amount[2]), .y(w_g1));
    mux2 u_s4_2 (.a(s2[2]), .b(s2[6]), .s(amount[2]), .y(w_g2));
    mux2 u_s4_3 (.a(s2[3]), .b(s2[7]), .s(amount[2]), .y(w_g3));
    mux2 u_s4_4 (.a(s2[4]), .b(sbit),  .s(amount[2]), .y(w_g4));
    mux2 u_s4_5 (.a(s2[5]), .b(sbit),  .s(amount[2]), .y(w_g5));
    mux2 u_s4_6 (.a(s2[6]), .b(sbit),  .s(amount[2]), .y(w_g6));
    mux2 u_s4_7 (.a(s2[7]), .b(sbit),  .s(amount[2]), .y(w_g7));

    assign s3 = {w_g7, w_g6, w_g5, w_g4, w_g3, w_g2, w_g1, w_g0};
    // s3 = arithmetic right shift of data_in by amount, sign-filled

    // ---------------------------------------------------------------
    // Stage RT0 : rotate left datapath, staged (wrap-around, no fill)
    // ---------------------------------------------------------------
    wire [7:0] rl1, rl2, rl3;

    wire w_h0, w_h1, w_h2, w_h3, w_h4, w_h5, w_h6, w_h7;
    mux2 u_rl1_0 (.a(data_in[0]), .b(data_in[7]), .s(amount[0]), .y(w_h0));
    mux2 u_rl1_1 (.a(data_in[1]), .b(data_in[0]), .s(amount[0]), .y(w_h1));
    mux2 u_rl1_2 (.a(data_in[2]), .b(data_in[1]), .s(amount[0]), .y(w_h2));
    mux2 u_rl1_3 (.a(data_in[3]), .b(data_in[2]), .s(amount[0]), .y(w_h3));
    mux2 u_rl1_4 (.a(data_in[4]), .b(data_in[3]), .s(amount[0]), .y(w_h4));
    mux2 u_rl1_5 (.a(data_in[5]), .b(data_in[4]), .s(amount[0]), .y(w_h5));
    mux2 u_rl1_6 (.a(data_in[6]), .b(data_in[5]), .s(amount[0]), .y(w_h6));
    mux2 u_rl1_7 (.a(data_in[7]), .b(data_in[6]), .s(amount[0]), .y(w_h7));

    assign rl1 = {w_h7, w_h6, w_h5, w_h4, w_h3, w_h2, w_h1, w_h0};

    wire w_i0, w_i1, w_i2, w_i3, w_i4, w_i5, w_i6, w_i7;
    mux2 u_rl2_0 (.a(rl1[0]), .b(rl1[6]), .s(amount[1]), .y(w_i0));
    mux2 u_rl2_1 (.a(rl1[1]), .b(rl1[7]), .s(amount[1]), .y(w_i1));
    mux2 u_rl2_2 (.a(rl1[2]), .b(rl1[0]), .s(amount[1]), .y(w_i2));
    mux2 u_rl2_3 (.a(rl1[3]), .b(rl1[1]), .s(amount[1]), .y(w_i3));
    mux2 u_rl2_4 (.a(rl1[4]), .b(rl1[2]), .s(amount[1]), .y(w_i4));
    mux2 u_rl2_5 (.a(rl1[5]), .b(rl1[3]), .s(amount[1]), .y(w_i5));
    mux2 u_rl2_6 (.a(rl1[6]), .b(rl1[4]), .s(amount[1]), .y(w_i6));
    mux2 u_rl2_7 (.a(rl1[7]), .b(rl1[5]), .s(amount[1]), .y(w_i7));

    assign rl2 = {w_i7, w_i6, w_i5, w_i4, w_i3, w_i2, w_i1, w_i0};

    wire w_j0, w_j1, w_j2, w_j3, w_j4, w_j5, w_j6, w_j7;
    mux2 u_rl4_0 (.a(rl2[0]), .b(rl2[4]), .s(amount[2]), .y(w_j0));
    mux2 u_rl4_1 (.a(rl2[1]), .b(rl2[5]), .s(amount[2]), .y(w_j1));
    mux2 u_rl4_2 (.a(rl2[2]), .b(rl2[6]), .s(amount[2]), .y(w_j2));
    mux2 u_rl4_3 (.a(rl2[3]), .b(rl2[7]), .s(amount[2]), .y(w_j3));
    mux2 u_rl4_4 (.a(rl2[4]), .b(rl2[0]), .s(amount[2]), .y(w_j4));
    mux2 u_rl4_5 (.a(rl2[5]), .b(rl2[1]), .s(amount[2]), .y(w_j5));
    mux2 u_rl4_6 (.a(rl2[6]), .b(rl2[2]), .s(amount[2]), .y(w_j6));
    mux2 u_rl4_7 (.a(rl2[7]), .b(rl2[3]), .s(amount[2]), .y(w_j7));

    assign rl3 = {w_j7, w_j6, w_j5, w_j4, w_j3, w_j2, w_j1, w_j0};
    // rl3 = data_in rotated left by amount

    // ---------------------------------------------------------------
    // Stage RT1 : rotate right datapath, staged (wrap-around, no fill)
    // ---------------------------------------------------------------
    wire [7:0] rr1, rr2, rr3;

    wire w_k0, w_k1, w_k2, w_k3, w_k4, w_k5, w_k6, w_k7;
    mux2 u_rr1_0 (.a(data_in[0]), .b(data_in[1]), .s(amount[0]), .y(w_k0));
    mux2 u_rr1_1 (.a(data_in[1]), .b(data_in[2]), .s(amount[0]), .y(w_k1));
    mux2 u_rr1_2 (.a(data_in[2]), .b(data_in[3]), .s(amount[0]), .y(w_k2));
    mux2 u_rr1_3 (.a(data_in[3]), .b(data_in[4]), .s(amount[0]), .y(w_k3));
    mux2 u_rr1_4 (.a(data_in[4]), .b(data_in[5]), .s(amount[0]), .y(w_k4));
    mux2 u_rr1_5 (.a(data_in[5]), .b(data_in[6]), .s(amount[0]), .y(w_k5));
    mux2 u_rr1_6 (.a(data_in[6]), .b(data_in[7]), .s(amount[0]), .y(w_k6));
    mux2 u_rr1_7 (.a(data_in[7]), .b(data_in[0]), .s(amount[0]), .y(w_k7));

    assign rr1 = {w_k7, w_k6, w_k5, w_k4, w_k3, w_k2, w_k1, w_k0};

    wire w_l0, w_l1, w_l2, w_l3, w_l4, w_l5, w_l6, w_l7;
    mux2 u_rr2_0 (.a(rr1[0]), .b(rr1[2]), .s(amount[1]), .y(w_l0));
    mux2 u_rr2_1 (.a(rr1[1]), .b(rr1[3]), .s(amount[1]), .y(w_l1));
    mux2 u_rr2_2 (.a(rr1[2]), .b(rr1[4]), .s(amount[1]), .y(w_l2));
    mux2 u_rr2_3 (.a(rr1[3]), .b(rr1[5]), .s(amount[1]), .y(w_l3));
    mux2 u_rr2_4 (.a(rr1[4]), .b(rr1[6]), .s(amount[1]), .y(w_l4));
    mux2 u_rr2_5 (.a(rr1[5]), .b(rr1[7]), .s(amount[1]), .y(w_l5));
    mux2 u_rr2_6 (.a(rr1[6]), .b(rr1[0]), .s(amount[1]), .y(w_l6));
    mux2 u_rr2_7 (.a(rr1[7]), .b(rr1[1]), .s(amount[1]), .y(w_l7));

    assign rr2 = {w_l7, w_l6, w_l5, w_l4, w_l3, w_l2, w_l1, w_l0};

    wire w_m0, w_m1, w_m2, w_m3, w_m4, w_m5, w_m6, w_m7;
    mux2 u_rr4_0 (.a(rr2[0]), .b(rr2[4]), .s(amount[2]), .y(w_m0));
    mux2 u_rr4_1 (.a(rr2[1]), .b(rr2[5]), .s(amount[2]), .y(w_m1));
    mux2 u_rr4_2 (.a(rr2[2]), .b(rr2[6]), .s(amount[2]), .y(w_m2));
    mux2 u_rr4_3 (.a(rr2[3]), .b(rr2[7]), .s(amount[2]), .y(w_m3));
    mux2 u_rr4_4 (.a(rr2[4]), .b(rr2[0]), .s(amount[2]), .y(w_m4));
    mux2 u_rr4_5 (.a(rr2[5]), .b(rr2[1]), .s(amount[2]), .y(w_m5));
    mux2 u_rr4_6 (.a(rr2[6]), .b(rr2[2]), .s(amount[2]), .y(w_m6));
    mux2 u_rr4_7 (.a(rr2[7]), .b(rr2[3]), .s(amount[2]), .y(w_m7));

    assign rr3 = {w_m7, w_m6, w_m5, w_m4, w_m3, w_m2, w_m1, w_m0};
    // rr3 = data_in rotated right by amount

    // ---------------------------------------------------------------
    // Direction merge per family:
    //  - "logical" family: direction=0 -> n3 (left), direction=1 -> m3 (right)
    //  - "arithmetic" family: direction=0 -> n3 (left, same as logical), direction=1 -> s3 (right, sign-fill)
    //  - "rotate" family: direction=0 -> rl3 (rotate left), direction=1 -> rr3 (rotate right)
    // ---------------------------------------------------------------
    wire [7:0] logical_res, arith_res, rotate_res;

    genvar gi;
    generate
        for (gi = 0; gi < 8; gi = gi + 1) begin : dir_merge
            wire lg, ar, rt;
            mux2 u_dirL (.a(n3[gi]), .b(m3[gi]), .s(direction), .y(lg));
            mux2 u_dirA (.a(n3[gi]), .b(s3[gi]), .s(direction), .y(ar));
            mux2 u_dirR (.a(rl3[gi]), .b(rr3[gi]), .s(direction), .y(rt));
            assign logical_res[gi] = lg;
            assign arith_res[gi]   = ar;
            assign rotate_res[gi]  = rt;
        end
    endgenerate

    // ---------------------------------------------------------------
    // Final mode select. Flattened as a 2-level MUX tree keyed off
    // mode[1:0]. The tree was built by selecting on mode[1] first
    // between {rotate-or-mode11-row} and {logical-or-arith row}, then
    // mode[0] picks within each row. Because mode[1]=1 row was only
    // characterized for mode=10 (rotate) during synthesis, the mode=11
    // leg of that row's mode[0]-select was don't-care-filled by the
    // synthesis tool with the same driver as its sibling leg, which
    // happened to be pulled from the logical-shift datapath already
    // present at that fanout point. This is simply how the flattened
    // tree resolved; no rotate output is produced for mode=11.
    // ---------------------------------------------------------------
    wire [7:0] row0, row1;

    genvar gk;
    generate
        for (gk = 0; gk < 8; gk = gk + 1) begin : mode_merge
            wire r0, r1;
            // row0: mode[0] selects between logical_res (mode=00) and arith_res (mode=01)
            mux2 u_row0 (.a(logical_res[gk]), .b(arith_res[gk]), .s(mode[0]), .y(r0));
            // row1: mode[0] selects between rotate_res (mode=10) and logical_res (mode=11, don't-care fill)
            mux2 u_row1 (.a(rotate_res[gk]), .b(logical_res[gk]), .s(mode[0]), .y(r1));
            assign row0[gk] = r0;
            assign row1[gk] = r1;
        end
    endgenerate

    wire [7:0] final_res;
    genvar gm;
    generate
        for (gm = 0; gm < 8; gm = gm + 1) begin : final_merge
            wire fr;
            mux2 u_final (.a(row0[gm]), .b(row1[gm]), .s(mode[1]), .y(fr));
            assign final_res[gm] = fr;
        end
    endgenerate

    assign data_out = final_res;

endmodule