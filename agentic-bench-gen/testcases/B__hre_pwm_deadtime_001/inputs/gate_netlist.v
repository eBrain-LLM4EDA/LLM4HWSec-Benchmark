// ============================================================
// gate-level netlist recovered from teardown scan
// module: gate_pwm_block
// flattened cell-level representation, generic net names
// local DFF primitive declared below for standalone elaboration
// ============================================================

module DFF (
    input  wire D,
    input  wire CLK,
    input  wire RST,
    output reg  Q
);
    always @(posedge CLK) begin
        if (RST)
            Q <= 1'b0;
        else
            Q <= D;
    end
endmodule

module gate_pwm_block (
    input  wire CLK,
    input  wire RST,
    input  wire EN,
    input  wire D0,
    input  wire D1,
    input  wire D2,
    input  wire D3,
    output wire PH,
    output wire PL
);

    // ---- counter state bits (cnt[0]=n1 ... cnt[3]=n4) ----
    wire n1, n2, n3, n4;

    // ---- ripple-carry increment logic (cnt + 1) ----
    wire w_a, w_b, w_c;
    wire c0, c1, c2;

    // bit0 toggles every enabled cycle
    xor  u_x0 (w_a, n1, 1'b1);

    // carry chain for bits 1..3
    and  u_c0 (c0, n1, 1'b1);
    xor  u_x1 (w_b, n2, c0);
    and  u_c1 (c1, n2, c0);
    xor  u_x2 (w_c, n3, c1);
    and  u_c2 (c2, n3, c1);
    xor  u_x3 (n40_next, n4, c2);

    wire n40_next;

    // ---- next-state muxing: hold when EN=0, incr when EN=1, else 0 on RST ----
    wire mux0, mux1, mux2, mux3;
    wire not_en;

    not  u_ne (not_en, EN);

    wire hold0, hold1, hold2, hold3;
    wire inc0, inc1, inc2, inc3;

    and  u_h0 (hold0, n1, not_en);
    and  u_h1 (hold1, n2, not_en);
    and  u_h2 (hold2, n3, not_en);
    and  u_h3 (hold3, n4, not_en);

    and  u_i0 (inc0, w_a, EN);
    and  u_i1 (inc1, w_b, EN);
    and  u_i2 (inc2, w_c, EN);
    and  u_i3 (inc3, n40_next, EN);

    or   u_m0 (mux0, hold0, inc0);
    or   u_m1 (mux1, hold1, inc1);
    or   u_m2 (mux2, hold2, inc2);
    or   u_m3 (mux3, hold3, inc3);

    // ---- state flip-flops ----
    DFF dff_c0 (.D(mux0), .CLK(CLK), .RST(RST), .Q(n1));
    DFF dff_c1 (.D(mux1), .CLK(CLK), .RST(RST), .Q(n2));
    DFF dff_c2 (.D(mux2), .CLK(CLK), .RST(RST), .Q(n3));
    DFF dff_c3 (.D(mux3), .CLK(CLK), .RST(RST), .Q(n4));

    // ---- guard band: counter >= 2  (n4 term unused for >=2 since 2..3 use only n2) ----
    // n5 = n2 & ~( n1 & ~n2 )  simplified: cnt>=2 means bit1 or bit2 or bit3 set,
    // equivalently NOT(cnt==0) AND NOT(cnt==1)
    wire n5, n6, n7, n8, n9;
    wire not_n1, not_n2, not_n3, not_n4;

    not  u_n1 (not_n1, n1);
    not  u_n2 (not_n2, n2);
    not  u_n3 (not_n3, n3);
    not  u_n4 (not_n4, n4);

    // cnt==0: ~n1 & ~n2 & ~n3 & ~n4
    and  u_eq0a (n6, not_n1, not_n2);
    and  u_eq0b (n7, not_n3, not_n4);
    and  u_eq0  (n8, n6, n7);

    // cnt==1: n1 & ~n2 & ~n3 & ~n4
    and  u_eq1a (n9, n1, not_n2);
    wire n10, n11;
    and  u_eq1b (n10, not_n3, not_n4);
    and  u_eq1  (n11, n9, n10);

    // guard_ge2 = NOT(cnt==0) AND NOT(cnt==1)
    wire not_eq0, not_eq1, n12;
    not  u_ne0 (not_eq0, n8);
    not  u_ne1 (not_eq1, n11);
    and  u_ge2 (n12, not_eq0, not_eq1);

    // ---- 4-bit magnitude comparator: cnt < duty ----
    // built bitwise from MSB down (standard subtractor-style comparator)
    wire lt3, eq3, lt2, eq2, lt1, eq1_, lt0;
    wire nD3, nD2, nD1, nD0;

    not  u_nd3 (nD3, D3);
    not  u_nd2 (nD2, D2);
    not  u_nd1 (nD1, D1);
    not  u_nd0 (nD0, D0);

    // bit3: lt3 = ~n4 & D3 ; eq3 = ~(n4 ^ D3)
    wire xn3;
    and  u_lt3 (lt3, not_n4, D3);
    xor  u_xn3 (xn3, n4, D3);
    not  u_eq3 (eq3, xn3);

    // bit2: lt2 = ~n3 & D2 ; eq2 = ~(n3 ^ D2)
    wire xn2, lt2raw;
    and  u_lt2 (lt2raw, not_n3, D2);
    xor  u_xn2 (xn2, n3, D2);
    not  u_eq2 (eq2, xn2);
    or   u_lt2c (lt2, lt3, w_lt2and);
    wire w_lt2and;
    and  u_lt2and (w_lt2and, eq3, lt2raw);

    // bit1: lt1 = ~n2 & D1 ; eq1_ = ~(n2 ^ D1)
    wire xn1, lt1raw, eqchain2, w_lt1and;
    and  u_lt1 (lt1raw, not_n2, D1);
    xor  u_xn1 (xn1, n2, D1);
    not  u_eq1raw (eq1_, xn1);
    and  u_eqc2 (eqchain2, eq3, eq2);
    and  u_lt1and (w_lt1and, eqchain2, lt1raw);
    or   u_lt1c (lt1, lt2, w_lt1and);

    // bit0: lt0 = ~n1 & D0 ; final n2_lt = cnt < duty
    wire xn0, lt0raw, eqchain3, w_lt0and, cnt_lt_duty;
    and  u_lt0 (lt0raw, not_n1, D0);
    xor  u_xn0 (xn0, n1, D0);
    and  u_eqc3 (eqchain3, eqchain2, eq1_);
    and  u_lt0and (w_lt0and, eqchain3, lt0raw);
    or   u_ltfinal (cnt_lt_duty, lt1, w_lt0and);

    // ---- stateA (hi-side window candidate) = guard_ge2 & cnt_lt_duty ----
    wire n30;
    and  u_stateA (n30, n12, cnt_lt_duty);

    // ---- comparator: cnt >= duty + 2 ----
    // implemented as NOT( cnt < duty+2 ), reuse subtractor-style chain on (duty+2)
    wire dp0, dp1, dp2, dp3, carry_in;
    // duty+2 addition (duty + 010b)
    xor  u_dp0 (dp0, D0, 1'b0);
    wire c_a0;
    and  u_ca0 (c_a0, D0, 1'b0);
    xor  u_dp1 (dp1, D1, 1'b1);
    wire c_a1, t_a1;
    and  u_ta1 (t_a1, D1, 1'b1);
    or   u_ca1 (c_a1, t_a1, c_a0);
    xor  u_dp2t (dp2t, D2, c_a1);
    wire dp2t, c_a2;
    and  u_ca2 (c_a2, D2, c_a1);
    xor  u_dp3t (dp3t, D3, c_a2);
    wire dp3t;

    // cnt < (duty+2) chain, mirroring the structure above using dp0..dp3t
    wire ndp3, ndp2, ndp1, ndp0;
    not  u_ndp3 (ndp3, dp3t);
    not  u_ndp2 (ndp2, dp2t);
    not  u_ndp1 (ndp1, dp1);
    not  u_ndp0 (ndp0, dp0);

    wire lt3b, eq3b, lt2rawb, w_lt2andb, lt2b, eq2b;
    wire xn3b, xn2b;
    and  u_lt3b (lt3b, not_n4, dp3t);
    xor  u_xn3b (xn3b, n4, dp3t);
    not  u_eq3b (eq3b, xn3b);

    and  u_lt2rawb (lt2rawb, not_n3, dp2t);
    xor  u_xn2b (xn2b, n3, dp2t);
    not  u_eq2b (eq2b, xn2b);
    and  u_lt2andb (w_lt2andb, eq3b, lt2rawb);
    or   u_lt2cb (lt2b, lt3b, w_lt2andb);

    wire xn1b, lt1rawb, eqchain2b, w_lt1andb, lt1b, eq1b;
    and  u_lt1rawb (lt1rawb, not_n2, dp1);
    xor  u_xn1b (xn1b, n2, dp1);
    not  u_eq1b (eq1b, xn1b);
    and  u_eqc2b (eqchain2b, eq3b, eq2b);
    and  u_lt1andb (w_lt1andb, eqchain2b, lt1rawb);
    or   u_lt1cb (lt1b, lt2b, w_lt1andb);

    wire xn0b, lt0rawb, eqchain3b, w_lt0andb, cnt_lt_dutyplus2;
    and  u_lt0rawb (lt0rawb, not_n1, dp0);
    xor  u_xn0b (xn0b, n1, dp0);
    and  u_eqc3b (eqchain3b, eqchain2b, eq1b);
    and  u_lt0andb (w_lt0andb, eqchain3b, lt0rawb);
    or   u_ltfinalb (cnt_lt_dutyplus2, lt1b, w_lt0andb);

    wire n31;
    not  u_stateBpre (n31, cnt_lt_dutyplus2);

    // ---- final output next-state, registered ----
    DFF dff_ph (.D(n30), .CLK(CLK), .RST(RST), .Q(PH));
    DFF dff_pl (.D(n31), .CLK(CLK), .RST(RST), .Q(PL));

endmodule