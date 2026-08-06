// ============================================================================
// ctrl_datapath - gate-level structural netlist (post-synthesis style)
// Simple accumulator/datapath with saturation, async reset synchronization,
// and power-on initialization sequencing.
// ============================================================================

module DFF (q, d, clk, rst_n);
  output reg q;
  input d, clk, rst_n;
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      q <= 1'b0;
    else
      q <= d;
  end
endmodule

module BUF1 (o, i);
  output o;
  input i;
  assign o = i;
endmodule

module AND2 (o, a, b);
  output o;
  input a, b;
  assign o = a & b;
endmodule

module OR2 (o, a, b);
  output o;
  input a, b;
  assign o = a | b;
endmodule

module XOR2 (o, a, b);
  output o;
  input a, b;
  assign o = a ^ b;
endmodule

module INV1 (o, i);
  output o;
  input i;
  assign o = ~i;
endmodule

module MUX2 (o, a, b, sel);
  output o;
  input a, b, sel;
  assign o = sel ? b : a;
endmodule

module ctrl_datapath (
  clk,
  rst_n,
  in_valid,
  data_in,
  mode,
  data_out,
  out_valid,
  overflow_flag
);

  input clk;
  input rst_n;
  input in_valid;
  input [7:0] data_in;
  input [1:0] mode;
  output [7:0] data_out;
  output out_valid;
  output overflow_flag;

  // ---------------------------------------------------------------
  // reset sync stage 1..3 : active-low async reset synchronizer chain
  // ---------------------------------------------------------------
  wire rst_sync1;
  wire rst_sync2;
  wire rst_sync_n;

  DFF U_RSTSYNC_FF1 (.q(rst_sync1), .d(1'b1), .clk(clk), .rst_n(rst_n));
  DFF U_RSTSYNC_FF2 (.q(rst_sync2), .d(rst_sync1), .clk(clk), .rst_n(rst_n));
  BUF1 U_RSTSYNC_BUF (.o(rst_sync_n), .i(rst_sync2));

  // ---------------------------------------------------------------
  // power-on initialization counter : counts to a fixed value once
  // ---------------------------------------------------------------
  wire [3:0] init_cnt;
  wire [3:0] init_cnt_next;
  wire init_done;
  wire init_cnt_b0_n, init_cnt_b1_n, init_cnt_b2_n, init_cnt_b3_n;
  wire init_cnt_full;

  INV1 U_INITCNT_INV0 (.o(init_cnt_b0_n), .i(init_cnt[0]));
  XOR2 U_INITCNT_XOR0 (.o(init_cnt_next[0]), .a(init_cnt[0]), .b(1'b1));

  AND2 U_INITCNT_AND1 (.o(init_cnt_full), .a(init_cnt[0]), .b(1'b1));
  XOR2 U_INITCNT_XOR1 (.o(init_cnt_next[1]), .a(init_cnt[1]), .b(init_cnt_full));

  wire init_carry1;
  AND2 U_INITCNT_AND2 (.o(init_carry1), .a(init_cnt_full), .b(init_cnt[1]));
  XOR2 U_INITCNT_XOR2 (.o(init_cnt_next[2]), .a(init_cnt[2]), .b(init_carry1));

  wire init_carry2;
  AND2 U_INITCNT_AND3 (.o(init_carry2), .a(init_carry1), .b(init_cnt[2]));
  XOR2 U_INITCNT_XOR3 (.o(init_cnt_next[3]), .a(init_cnt[3]), .b(init_carry2));

  DFF U_INITCNT_FF0 (.q(init_cnt[0]), .d(init_cnt_next[0]), .clk(clk), .rst_n(rst_sync_n));
  DFF U_INITCNT_FF1 (.q(init_cnt[1]), .d(init_cnt_next[1]), .clk(clk), .rst_n(rst_sync_n));
  DFF U_INITCNT_FF2 (.q(init_cnt[2]), .d(init_cnt_next[2]), .clk(clk), .rst_n(rst_sync_n));
  DFF U_INITCNT_FF3 (.q(init_cnt[3]), .d(init_cnt_next[3]), .clk(clk), .rst_n(rst_sync_n));

  // init_done asserts once init_cnt reaches 4'hF (one-time power-on gate)
  wire init_done_and1, init_done_and2;
  AND2 U_INITDONE_AND1 (.o(init_done_and1), .a(init_cnt[0]), .b(init_cnt[1]));
  AND2 U_INITDONE_AND2 (.o(init_done_and2), .a(init_cnt[2]), .b(init_cnt[3]));
  AND2 U_INITDONE_AND (.o(init_done), .a(init_done_and1), .b(init_done_and2));

  // latch init_done so it stays asserted after the counter rolls further
  wire init_done_latched;
  wire init_done_or_in;
  OR2 U_INITDONE_HOLD (.o(init_done_or_in), .a(init_done), .b(init_done_latched));
  DFF U_INITDONE_FF (.q(init_done_latched), .d(init_done_or_in), .clk(clk), .rst_n(rst_sync_n));

  // ---------------------------------------------------------------
  // gated enable : datapath only runs once init sequence has finished
  // ---------------------------------------------------------------
  wire datapath_en;
  AND2 U_DPEN_AND (.o(datapath_en), .a(in_valid), .b(init_done_latched));

  // ---------------------------------------------------------------
  // accumulator datapath : adder with saturation clamp at max value
  // ---------------------------------------------------------------
  wire [7:0] acc_reg;
  wire [7:0] acc_sum;
  wire [7:0] acc_next;
  wire acc_carry0, acc_carry1, acc_carry2, acc_carry3;
  wire acc_carry4, acc_carry5, acc_carry6, acc_carry7;

  XOR2 U_ADD_XOR0 (.o(acc_sum[0]), .a(acc_reg[0]), .b(data_in[0]));
  AND2 U_ADD_AND0 (.o(acc_carry0), .a(acc_reg[0]), .b(data_in[0]));

  wire acc_p1;
  XOR2 U_ADD_XOR1a (.o(acc_p1), .a(acc_reg[1]), .b(data_in[1]));
  XOR2 U_ADD_XOR1b (.o(acc_sum[1]), .a(acc_p1), .b(acc_carry0));
  wire acc_g1, acc_k1;
  AND2 U_ADD_AND1a (.o(acc_g1), .a(acc_reg[1]), .b(data_in[1]));
  AND2 U_ADD_AND1b (.o(acc_k1), .a(acc_p1), .b(acc_carry0));
  OR2  U_ADD_OR1   (.o(acc_carry1), .a(acc_g1), .b(acc_k1));

  wire acc_p2;
  XOR2 U_ADD_XOR2a (.o(acc_p2), .a(acc_reg[2]), .b(data_in[2]));
  XOR2 U_ADD_XOR2b (.o(acc_sum[2]), .a(acc_p2), .b(acc_carry1));
  wire acc_g2, acc_k2;
  AND2 U_ADD_AND2a (.o(acc_g2), .a(acc_reg[2]), .b(data_in[2]));
  AND2 U_ADD_AND2b (.o(acc_k2), .a(acc_p2), .b(acc_carry1));
  OR2  U_ADD_OR2   (.o(acc_carry2), .a(acc_g2), .b(acc_k2));

  wire acc_p3;
  XOR2 U_ADD_XOR3a (.o(acc_p3), .a(acc_reg[3]), .b(data_in[3]));
  XOR2 U_ADD_XOR3b (.o(acc_sum[3]), .a(acc_p3), .b(acc_carry2));
  wire acc_g3, acc_k3;
  AND2 U_ADD_AND3a (.o(acc_g3), .a(acc_reg[3]), .b(data_in[3]));
  AND2 U_ADD_AND3b (.o(acc_k3), .a(acc_p3), .b(acc_carry2));
  OR2  U_ADD_OR3   (.o(acc_carry3), .a(acc_g3), .b(acc_k3));

  wire acc_p4;
  XOR2 U_ADD_XOR4a (.o(acc_p4), .a(acc_reg[4]), .b(data_in[4]));
  XOR2 U_ADD_XOR4b (.o(acc_sum[4]), .a(acc_p4), .b(acc_carry3));
  wire acc_g4, acc_k4;
  AND2 U_ADD_AND4a (.o(acc_g4), .a(acc_reg[4]), .b(data_in[4]));
  AND2 U_ADD_AND4b (.o(acc_k4), .a(acc_p4), .b(acc_carry3));
  OR2  U_ADD_OR4   (.o(acc_carry4), .a(acc_g4), .b(acc_k4));

  wire acc_p5;
  XOR2 U_ADD_XOR5a (.o(acc_p5), .a(acc_reg[5]), .b(data_in[5]));
  XOR2 U_ADD_XOR5b (.o(acc_sum[5]), .a(acc_p5), .b(acc_carry4));
  wire acc_g5, acc_k5;
  AND2 U_ADD_AND5a (.o(acc_g5), .a(acc_reg[5]), .b(data_in[5]));
  AND2 U_ADD_AND5b (.o(acc_k5), .a(acc_p5), .b(acc_carry4));
  OR2  U_ADD_OR5   (.o(acc_carry5), .a(acc_g5), .b(acc_k5));

  wire acc_p6;
  XOR2 U_ADD_XOR6a (.o(acc_p6), .a(acc_reg[6]), .b(data_in[6]));
  XOR2 U_ADD_XOR6b (.o(acc_sum[6]), .a(acc_p6), .b(acc_carry5));
  wire acc_g6, acc_k6;
  AND2 U_ADD_AND6a (.o(acc_g6), .a(acc_reg[6]), .b(data_in[6]));
  AND2 U_ADD_AND6b (.o(acc_k6), .a(acc_p6), .b(acc_carry5));
  OR2  U_ADD_OR6   (.o(acc_carry6), .a(acc_g6), .b(acc_k6));

  wire acc_p7;
  XOR2 U_ADD_XOR7a (.o(acc_p7), .a(acc_reg[7]), .b(data_in[7]));
  XOR2 U_ADD_XOR7b (.o(acc_sum[7]), .a(acc_p7), .b(acc_carry6));
  wire acc_g7, acc_k7;
  AND2 U_ADD_AND7a (.o(acc_g7), .a(acc_reg[7]), .b(data_in[7]));
  AND2 U_ADD_AND7b (.o(acc_k7), .a(acc_p7), .b(acc_carry6));
  OR2  U_ADD_OR7   (.o(acc_carry7), .a(acc_g7), .b(acc_k7));

  // saturation compare: rare condition, all sum bits high & carry-out set
  wire sat_cmp_ge_max_a, sat_cmp_ge_max_b;
  AND2 U_SATCMP_AND1 (.o(sat_cmp_ge_max_a), .a(acc_sum[7]), .b(acc_sum[6]));
  AND2 U_SATCMP_AND2 (.o(sat_cmp_ge_max_b), .a(acc_sum[5]), .b(acc_sum[4]));
  wire sat_cmp_ge_max_c;
  AND2 U_SATCMP_AND3 (.o(sat_cmp_ge_max_c), .a(sat_cmp_ge_max_a), .b(sat_cmp_ge_max_b));
  wire sat_cmp_ge_max;
  AND2 U_SATCMP_AND4 (.o(sat_cmp_ge_max), .a(sat_cmp_ge_max_c), .b(acc_carry7));

  // saturation clamp mux: when sat_cmp_ge_max, clamp acc_next to 8'hFF
  MUX2 U_SAT_MUX0 (.o(acc_next[0]), .a(acc_sum[0]), .b(1'b1), .sel(sat_cmp_ge_max));
  MUX2 U_SAT_MUX1 (.o(acc_next[1]), .a(acc_sum[1]), .b(1'b1), .sel(sat_cmp_ge_max));
  MUX2 U_SAT_MUX2 (.o(acc_next[2]), .a(acc_sum[2]), .b(1'b1), .sel(sat_cmp_ge_max));
  MUX2 U_SAT_MUX3 (.o(acc_next[3]), .a(acc_sum[3]), .b(1'b1), .sel(sat_cmp_ge_max));
  MUX2 U_SAT_MUX4 (.o(acc_next[4]), .a(acc_sum[4]), .b(1'b1), .sel(sat_cmp_ge_max));
  MUX2 U_SAT_MUX5 (.o(acc_next[5]), .a(acc_sum[5]), .b(1'b1), .sel(sat_cmp_ge_max));
  MUX2 U_SAT_MUX6 (.o(acc_next[6]), .a(acc_sum[6]), .b(1'b1), .sel(sat_cmp_ge_max));
  MUX2 U_SAT_MUX7 (.o(acc_next[7]), .a(acc_sum[7]), .b(1'b1), .sel(sat_cmp_ge_max));

  DFF U_ACC_FF0 (.q(acc_reg[0]), .d(acc_next[0]), .clk(clk), .rst_n(rst_sync_n));
  DFF U_ACC_FF1 (.q(acc_reg[1]), .d(acc_next[1]), .clk(clk), .rst_n(rst_sync_n));
  DFF U_ACC_FF2 (.q(acc_reg[2]), .d(acc_next[2]), .clk(clk), .rst_n(rst_sync_n));
  DFF U_ACC_FF3 (.q(acc_reg[3]), .d(acc_next[3]), .clk(clk), .rst_n(rst_sync_n));
  DFF U_ACC_FF4 (.q(acc_reg[4]), .d(acc_next[4]), .clk(clk), .rst_n(rst_sync_n));
  DFF U_ACC_FF5 (.q(acc_reg[5]), .d(acc_next[5]), .clk(clk), .rst_n(rst_sync_n));
  DFF U_ACC_FF6 (.q(acc_reg[6]), .d(acc_next[6]), .clk(clk), .rst_n(rst_sync_n));
  DFF U_ACC_FF7 (.q(acc_reg[7]), .d(acc_next[7]), .clk(clk), .rst_n(rst_sync_n));

  DFF U_OVFLAG_FF (.q(overflow_flag), .d(sat_cmp_ge_max), .clk(clk), .rst_n(rst_sync_n));

  // ---------------------------------------------------------------
  // mode-controlled output mux: pass-through vs accumulator result
  // ---------------------------------------------------------------
  wire mode0_sel;
  BUF1 U_MODESEL_BUF (.o(mode0_sel), .i(mode[0]));

  MUX2 U_OUTMUX0 (.o(data_out[0]), .a(data_in[0]), .b(acc_reg[0]), .sel(mode0_sel));
  MUX2 U_OUTMUX1 (.o(data_out[1]), .a(data_in[1]), .b(acc_reg[1]), .sel(mode0_sel));
  MUX2 U_OUTMUX2 (.o(data_out[2]), .a(data_in[2]), .b(acc_reg[2]), .sel(mode0_sel));
  MUX2 U_OUTMUX3 (.o(data_out[3]), .a(data_in[3]), .b(acc_reg[3]), .sel(mode0_sel));
  MUX2 U_OUTMUX4 (.o(data_out[4]), .a(data_in[4]), .b(acc_reg[4]), .sel(mode0_sel));
  MUX2 U_OUTMUX5 (.o(data_out[5]), .a(data_in[5]), .b(acc_reg[5]), .sel(mode0_sel));
  MUX2 U_OUTMUX6 (.o(data_out[6]), .a(data_in[6]), .b(acc_reg[6]), .sel(mode0_sel));
  MUX2 U_OUTMUX7 (.o(data_out[7]), .a(data_in[7]), .b(acc_reg[7]), .sel(mode0_sel));

  DFF U_OUTVALID_FF (.q(out_valid), .d(datapath_en), .clk(clk), .rst_n(rst_sync_n));

endmodule