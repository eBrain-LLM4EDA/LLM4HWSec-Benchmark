// =============================================================================
// quadrature_netlist.v
//
// REFERENCE-ONLY. Do not modify. Do not submit this file.
//
// This is a flattened gate-level netlist reconstruction of the undocumented
// quadrature decoder block, built only from primitive gates and flip-flops
// (DFF, and2, or2, xor2, not1, mux2, fadd1). It intentionally avoids any
// word-level operators or case/if decode shortcuts, mirroring how such a
// block might appear after synthesis/flattening tools have stripped away
// the original RTL structure.
//
// Module name is `quad_decoder_gates`, deliberately distinct from the
// pinned `quad_decoder` interface -- this file is analysis input only.
// =============================================================================

`timescale 1ns/1ps

// -----------------------------------------------------------------------
// Primitive: D flip-flop, synchronous active-high reset to rst_val
// -----------------------------------------------------------------------
module DFF (
    input  wire clk,
    input  wire rst,
    input  wire d,
    input  wire rst_val,
    output reg  q
);
    always @(posedge clk) begin
        if (rst)
            q <= rst_val;
        else
            q <= d;
    end
endmodule

// -----------------------------------------------------------------------
// Primitive gates
// -----------------------------------------------------------------------
module and2 (input wire a, input wire b, output wire y);
    assign y = a & b;
endmodule

module or2 (input wire a, input wire b, output wire y);
    assign y = a | b;
endmodule

module xor2 (input wire a, input wire b, output wire y);
    assign y = a ^ b;
endmodule

module not1 (input wire a, output wire y);
    assign y = ~a;
endmodule

// 2:1 mux, sel=1 selects b
module mux2 (input wire a, input wire b, input wire sel, output wire y);
    assign y = sel ? b : a;
endmodule

// Full adder primitive
module fadd1 (
    input  wire a,
    input  wire b,
    input  wire cin,
    output wire s,
    output wire cout
);
    assign s    = a ^ b ^ cin;
    assign cout = (a & b) | (a & cin) | (b & cin);
endmodule

// =============================================================================
// Top-level flattened netlist
// =============================================================================
module quad_decoder_gates (
    input  wire clk,
    input  wire rst,
    input  wire a,
    input  wire b,
    output wire [7:0] pos_out,
    output wire       dir_out,
    output wire       invalid_out
);

    // ---------------------------------------------------------------
    // Current-state DFFs: sample a,b each cycle
    // ---------------------------------------------------------------
    wire cur_a, cur_b;

    DFF dff_cur_a (.clk(clk), .rst(rst), .d(a), .rst_val(1'b0), .q(cur_a));
    DFF dff_cur_b (.clk(clk), .rst(rst), .d(b), .rst_val(1'b0), .q(cur_b));

    // ---------------------------------------------------------------
    // Previous-state DFFs: sample cur_a,cur_b each cycle (one cycle
    // behind current state)
    // ---------------------------------------------------------------
    wire prev_a, prev_b;

    DFF dff_prev_a (.clk(clk), .rst(rst), .d(cur_a), .rst_val(1'b0), .q(prev_a));
    DFF dff_prev_b (.clk(clk), .rst(rst), .d(cur_b), .rst_val(1'b0), .q(prev_b));

    // ---------------------------------------------------------------
    // XOR compare gates
    // ---------------------------------------------------------------
    wire diff_a, diff_b;

    xor2 xor_diff_a (.a(cur_a), .b(prev_a), .y(diff_a));
    xor2 xor_diff_b (.a(cur_b), .b(prev_b), .y(diff_b));

    // no_change = ~diff_a & ~diff_b
    // illegal   = diff_a & diff_b        (both bits changed)
    // one_bit   = diff_a ^ diff_b        (exactly one bit changed)
    wire n_diff_a, n_diff_b;
    not1 not_diff_a (.a(diff_a), .y(n_diff_a));
    not1 not_diff_b (.a(diff_b), .y(n_diff_b));

    wire no_change;
    and2 and_no_change (.a(n_diff_a), .b(n_diff_b), .y(no_change));

    wire illegal_jump;
    and2 and_illegal (.a(diff_a), .b(diff_b), .y(illegal_jump));

    wire one_bit_changed;
    xor2 xor_one_bit (.a(diff_a), .b(diff_b), .y(one_bit_changed));

    // ---------------------------------------------------------------
    // Decode tree: determine legal-forward vs legal-reverse among the
    // one-bit-changed cases, using only and/or/not/mux2 primitives.
    //
    // Gray adjacency (prev -> cur), forward direction:
    //   00 -> 01 -> 11 -> 10 -> 00
    // i.e. forward pairs (prev_a,prev_b -> cur_a,cur_b):
    //   00->01 , 01->11 , 11->10 , 10->00
    //
    // Reverse pairs are the mirror:
    //   00->10 , 10->11 , 11->01 , 01->00
    //
    // Each of these 8 pairs is decoded individually with AND/NOT gates,
    // then OR-reduced into forward_match / reverse_match. Both are only
    // meaningful when one_bit_changed=1 (guaranteed by construction,
    // since a two-bit jump can never equal any of these single-bit
    // patterns).
    // ---------------------------------------------------------------

    wire n_prev_a, n_prev_b, n_cur_a, n_cur_b;
    not1 not_prev_a (.a(prev_a), .y(n_prev_a));
    not1 not_prev_b (.a(prev_b), .y(n_prev_b));
    not1 not_cur_a  (.a(cur_a),  .y(n_cur_a));
    not1 not_cur_b  (.a(cur_b),  .y(n_cur_b));

    // ---- forward pair 00 -> 01 : prev_a=0,prev_b=0,cur_a=0,cur_b=1
    wire f1_0, f1_1, f1_2, f1;
    and2 f1_and0 (.a(n_prev_a), .b(n_prev_b), .y(f1_0));
    and2 f1_and1 (.a(n_cur_a),  .b(cur_b),    .y(f1_1));
    and2 f1_and2 (.a(f1_0),     .b(f1_1),     .y(f1));

    // ---- forward pair 01 -> 11 : prev_a=0,prev_b=1,cur_a=1,cur_b=1
    wire f2_0, f2_1, f2;
    and2 f2_and0 (.a(n_prev_a), .b(prev_b), .y(f2_0));
    and2 f2_and1 (.a(cur_a),    .b(cur_b),  .y(f2_1));
    and2 f2_and2 (.a(f2_0),     .b(f2_1),   .y(f2));

    // ---- forward pair 11 -> 10 : prev_a=1,prev_b=1,cur_a=1,cur_b=0
    wire f3_0, f3_1, f3;
    and2 f3_and0 (.a(prev_a), .b(prev_b),  .y(f3_0));
    and2 f3_and1 (.a(cur_a),  .b(n_cur_b), .y(f3_1));
    and2 f3_and2 (.a(f3_0),   .b(f3_1),    .y(f3));

    // ---- forward pair 10 -> 00 : prev_a=1,prev_b=0,cur_a=0,cur_b=0
    wire f4_0, f4_1, f4;
    and2 f4_and0 (.a(prev_a),  .b(n_prev_b), .y(f4_0));
    and2 f4_and1 (.a(n_cur_a), .b(n_cur_b),  .y(f4_1));
    and2 f4_and2 (.a(f4_0),    .b(f4_1),     .y(f4));

    wire fwd_or1, fwd_or2, forward_match;
    or2 fwd_or_a (.a(f1), .b(f2), .y(fwd_or1));
    or2 fwd_or_b (.a(f3), .b(f4), .y(fwd_or2));
    or2 fwd_or_c (.a(fwd_or1), .b(fwd_or2), .y(forward_match));

    // ---- reverse pair 00 -> 10 : prev_a=0,prev_b=0,cur_a=1,cur_b=0
    wire r1_0, r1_1, r1;
    and2 r1_and0 (.a(n_prev_a), .b(n_prev_b), .y(r1_0));
    and2 r1_and1 (.a(cur_a),    .b(n_cur_b),  .y(r1_1));
    and2 r1_and2 (.a(r1_0),     .b(r1_1),     .y(r1));

    // ---- reverse pair 10 -> 11 : prev_a=1,prev_b=0,cur_a=1,cur_b=1
    wire r2_0, r2_1, r2;
    and2 r2_and0 (.a(prev_a),  .b(n_prev_b), .y(r2_0));
    and2 r2_and1 (.a(cur_a),   .b(cur_b),    .y(r2_1));
    and2 r2_and2 (.a(r2_0),    .b(r2_1),     .y(r2));

    // ---- reverse pair 11 -> 01 : prev_a=1,prev_b=1,cur_a=0,cur_b=1
    wire r3_0, r3_1, r3;
    and2 r3_and0 (.a(prev_a),  .b(prev_b),  .y(r3_0));
    and2 r3_and1 (.a(n_cur_a), .b(cur_b),   .y(r3_1));
    and2 r3_and2 (.a(r3_0),    .b(r3_1),    .y(r3));

    // ---- reverse pair 01 -> 00 : prev_a=0,prev_b=1,cur_a=0,cur_b=0
    wire r4_0, r4_1, r4;
    and2 r4_and0 (.a(n_prev_a), .b(prev_b),   .y(r4_0));
    and2 r4_and1 (.a(n_cur_a),  .b(n_cur_b),  .y(r4_1));
    and2 r4_and2 (.a(r4_0),     .b(r4_1),     .y(r4));

    wire rev_or1, rev_or2, reverse_match;
    or2 rev_or_a (.a(r1), .b(r2), .y(rev_or1));
    or2 rev_or_b (.a(r3), .b(r4), .y(rev_or2));
    or2 rev_or_c (.a(rev_or1), .b(rev_or2), .y(reverse_match));

    // legal_forward / legal_reverse gated by one_bit_changed for safety
    // (redundant given the pair decode above, but keeps the illegal
    // classification robust against any unexpected pair).
    wire legal_forward, legal_reverse;
    and2 and_legal_fwd (.a(forward_match), .b(one_bit_changed), .y(legal_forward));
    and2 and_legal_rev (.a(reverse_match), .b(one_bit_changed), .y(legal_reverse));

    // ---------------------------------------------------------------
    // dir register: updates to 1 on legal_forward, to 0 on legal_reverse,
    // holds otherwise (no_change or illegal_jump).
    // ---------------------------------------------------------------
    wire dir_cur;
    wire dir_hold_sel;
    or2 dir_hold_or (.a(no_change), .b(illegal_jump), .y(dir_hold_sel));

    wire dir_next_stage1, dir_next;
    // dir_next_stage1 = mux(legal_reverse_val=0, legal_forward_val=1, sel=legal_forward)
    mux2 dir_mux1 (.a(1'b0), .b(1'b1), .sel(legal_forward), .y(dir_next_stage1));
    // final: if holding, keep dir_cur; else use dir_next_stage1
    // (dir_next_stage1 already correctly encodes forward=1/reverse=0 since
    //  in the legal-transition case exactly one of legal_forward/legal_reverse
    //  is asserted)
    wire dir_cur_or_next;
    mux2 dir_mux2 (.a(dir_next_stage1), .b(dir_cur), .sel(dir_hold_sel), .y(dir_next));

    DFF dff_dir (.clk(clk), .rst(rst), .d(dir_next), .rst_val(1'b0), .q(dir_cur));

    // ---------------------------------------------------------------
    // invalid register: asserted for exactly one cycle following
    // detection of illegal_jump, cleared otherwise.
    // ---------------------------------------------------------------
    wire invalid_cur;
    DFF dff_invalid (.clk(clk), .rst(rst), .d(illegal_jump), .rst_val(1'b0), .q(invalid_cur));

    // ---------------------------------------------------------------
    // pos accumulator: 8-bit ripple adder/subtractor built from fadd1
    // primitives. On legal_forward: pos_next = pos_cur + 1
    // On legal_reverse: pos_next = pos_cur - 1 (i.e. + 0xFF, two's complement)
    // Otherwise (no_change or illegal_jump): pos_next = pos_cur (hold)
    //
    // Implemented as: pos_next = pos_cur + addend, where
    //   addend = 8'h01 if legal_forward
    //   addend = 8'hFF if legal_reverse
    //   addend = 8'h00 otherwise
    // ---------------------------------------------------------------
    wire [7:0] pos_cur;

    // addend bit construction using mux2 primitives per bit.
    // addend_fwd = 00000001, addend_rev = 11111111, addend_hold = 00000000
    wire [7:0] addend_fwd;
    assign addend_fwd = 8'b00000001; // constant pattern for +1

    wire [7:0] addend_rev;
    assign addend_rev = 8'b11111111; // constant pattern for -1 (two's complement)

    wire [7:0] addend_hold;
    assign addend_hold = 8'b00000000;

    // select addend: hold takes priority if neither legal_forward nor
    // legal_reverse is set (covers no_change and illegal_jump alike,
    // since in the illegal case both legal_forward and legal_reverse
    // are forced low by the pair-decode logic above).
    wire [7:0] addend_stage1;
    wire [7:0] addend_final;

    genvar gi;
    generate
        for (gi = 0; gi < 8; gi = gi + 1) begin : ADD_SEL
            wire stage1_bit;
            mux2 mux_stage1 (.a(addend_hold[gi]), .b(addend_fwd[gi]), .sel(legal_forward), .y(stage1_bit));
            assign addend_stage1[gi] = stage1_bit;

            wire final_bit;
            mux2 mux_final (.a(addend_stage1[gi]), .b(addend_rev[gi]), .sel(legal_reverse), .y(final_bit));
            assign addend_final[gi] = final_bit;
        end
    endgenerate

    // 8-bit ripple adder: pos_cur + addend_final
    wire [7:0] pos_sum;
    wire [8:0] carry_chain;
    assign carry_chain[0] = 1'b0;

    generate
        for (gi = 0; gi < 8; gi = gi + 1) begin : RIPPLE_ADD
            fadd1 fa (
                .a    (pos_cur[gi]),
                .b    (addend_final[gi]),
                .cin  (carry_chain[gi]),
                .s    (pos_sum[gi]),
                .cout (carry_chain[gi+1])
            );
        end
    endgenerate

    // pos register, 8 individual DFF bits
    generate
        for (gi = 0; gi < 8; gi = gi + 1) begin : POS_REG
            DFF dff_pos_bit (
                .clk     (clk),
                .rst     (rst),
                .d       (pos_sum[gi]),
                .rst_val (1'b0),
                .q       (pos_cur[gi])
            );
        end
    endgenerate

    // ---------------------------------------------------------------
    // Output assignments
    // ---------------------------------------------------------------
    assign pos_out     = pos_cur;
    assign dir_out      = dir_cur;
    assign invalid_out = invalid_cur;

endmodule