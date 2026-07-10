module top_locked (
    in,
    key,
    out
);

    input  [7:0] in;
    input  [9:0] key;
    output       out;

    // ------------------------------------------------------------------
    // Functional core: ordinary combinational logic over primary inputs.
    // This block determines the intended function of the circuit and
    // does not depend on the key at all in this instance.
    // ------------------------------------------------------------------
    wire w_and0, w_and1, w_or0, w_xor0, w_xor1;

    and  u_core_and0 (w_and0, in[0], in[1]);
    and  u_core_and1 (w_and1, in[2], in[3]);
    or   u_core_or0  (w_or0, w_and0, w_and1);
    xor  u_core_xor0 (w_xor0, in[4], in[5]);
    xor  u_core_xor1 (w_xor1, in[6], in[7]);

    wire func_out_masked;
    xor  u_core_xor2 (func_out_masked, w_or0, w_xor0, w_xor1);

    // ------------------------------------------------------------------
    // Tie-off cells: fixed-value constant drivers.
    // ------------------------------------------------------------------
    wire tie0_net, tie1_net;

    and  tied_key_const_0 (tie0_net, in[0], 1'b0);
    or   tied_key_const_1 (tie1_net, in[0], 1'b1);

    // ------------------------------------------------------------------
    // Anti-SAT-style branch g: AND-tree over in[0..3] and key[0..4]
    // literals (some inverted).
    // ------------------------------------------------------------------
    wire g_l0, g_l1, g_l2, g_l3, g_l4;
    wire n_key0, n_key2;

    not  u_g_inv0 (n_key0, key[0]);
    not  u_g_inv2 (n_key2, key[2]);

    xor  u_g_lit0 (g_l0, in[0], n_key0);
    xor  u_g_lit1 (g_l1, in[1], key[1]);
    xor  u_g_lit2 (g_l2, in[2], n_key2);
    xor  u_g_lit3 (g_l3, in[3], key[3]);
    buf  u_g_lit4 (g_l4, key[4]);

    wire g_a0, g_a1, antisat_g_out;

    and  antisat_g_inst_a0 (g_a0, g_l0, g_l1);
    and  antisat_g_inst_a1 (g_a1, g_l2, g_l3);
    and  antisat_g_inst (antisat_g_out, g_a0, g_a1, g_l4);

    // ------------------------------------------------------------------
    // Anti-SAT-style branch g': structural mirror of branch g over the
    // same in[0..3] inputs, but using key[5..9] literals with
    // complementary inversions relative to branch g. The literal that
    // would correspond to key[4] in the mirrored position is instead
    // driven by the tied constant-0 net; the literal that would
    // correspond to key[9] in the mirrored position is driven by the
    // tied constant-1 net.
    // ------------------------------------------------------------------
    wire gb_l0, gb_l1, gb_l2, gb_l3, gb_l4;
    wire n_key6, n_key8;

    not  u_gb_inv6 (n_key6, key[6]);
    not  u_gb_inv8 (n_key8, key[8]);

    xor  u_gb_lit0 (gb_l0, in[0], key[5]);
    xor  u_gb_lit1 (gb_l1, in[1], n_key6);
    xor  u_gb_lit2 (gb_l2, in[2], key[7]);
    xor  u_gb_lit3 (gb_l3, in[3], n_key8);
    buf  u_gb_lit4 (gb_l4, tie0_net);

    wire gb_a0, gb_a1, antisat_gbar_out;

    and  antisat_gbar_inst_a0 (gb_a0, gb_l0, gb_l1);
    and  antisat_gbar_inst_a1 (gb_a1, gb_l2, gb_l3);
    and  antisat_gbar_inst (antisat_gbar_out, gb_a0, gb_a1, gb_l4);

    // A second use of the constant-1 tie net occupies the structurally
    // mirrored slot corresponding to key[9] feeding into the final
    // gating comparison, alongside the g'-branch output.
    wire gbar_final_in;
    buf  u_gbar_key9_slot (gbar_final_in, tie1_net);

    wire antisat_gbar_out2;
    and  u_gbar_combine (antisat_gbar_out2, antisat_gbar_out, gbar_final_in);

    // ------------------------------------------------------------------
    // Final Anti-SAT gating gate: combines branch g and branch g'
    // outputs into the gating signal antisat_out.
    // ------------------------------------------------------------------
    wire antisat_out;

    xnor antisat_gate (antisat_out, antisat_g_out, antisat_gbar_out2);

    // ------------------------------------------------------------------
    // Final output mask: the Anti-SAT gating signal is ANDed with the
    // functional-core output to mask it before it reaches the primary
    // output port.
    // ------------------------------------------------------------------
    and  u_out_mask (out, func_out_masked, antisat_out);

endmodule