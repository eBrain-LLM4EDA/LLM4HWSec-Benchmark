// -----------------------------------------------------------------------
// top.v -- structural gate-level netlist
// Controller/datapath module with a small bank of control, datapath, and
// privilege/lock-state registers, plus a synchronous reset distribution
// network. Built from simple primitive gate models so it elaborates and
// simulates cleanly under plain Verilog (iverilog -g2012), with no
// dependency on any proprietary cell library.
// -----------------------------------------------------------------------

`timescale 1ns/1ps

// -------------------------------------------------------------------
// Primitive gate models
// -------------------------------------------------------------------

module PRIM_INV(input a, output y);
    assign y = ~a;
endmodule

module PRIM_AND2(input a, input b, output y);
    assign y = a & b;
endmodule

module PRIM_OR2(input a, input b, output y);
    assign y = a | b;
endmodule

module PRIM_XOR2(input a, input b, output y);
    assign y = a ^ b;
endmodule

module PRIM_BUF(input a, output y);
    assign y = a;
endmodule

// Simple synchronous-clear D flip-flop.
// RST_N is the flop's local reset pin: when RST_N == 1'b0 at the rising
// clock edge, Q is synchronously cleared to 0. Otherwise Q captures D.
module PRIM_DFF_SYNC(input CLK, input RST_N, input D, output reg Q);
    always @(posedge CLK) begin
        if (RST_N == 1'b0)
            Q <= 1'b0;
        else
            Q <= D;
    end
endmodule

// -------------------------------------------------------------------
// Top-level module
// -------------------------------------------------------------------

module top(
    input        CLK,
    input        RSTN,
    input  [3:0] DIN,
    input  [3:0] CTRL,
    output [3:0] DOUT
);

    // Locally inverted copy of the reset net.
    wire rstn_b;

    // Control-path register outputs.
    wire ctrl_ff0_q, ctrl_ff1_q, ctrl_ff2_q, ctrl_ff3_q;

    // Datapath register outputs.
    wire dp_ff4_q, dp_ff5_q;

    // Privilege/lock-state register outputs.
    wire priv_ff1_q, priv_ff2_q;

    // Next-state combinational nets for control registers.
    wire ctrl_ff0_d, ctrl_ff1_d, ctrl_ff2_d, ctrl_ff3_d;

    // Next-state combinational nets for datapath registers.
    wire dp_ff4_d, dp_ff5_d;

    // Next-state combinational nets for privilege registers.
    wire priv_ff1_d, priv_ff2_d;

    // -------------------------------------------------------------
    // Reset distribution
    // -------------------------------------------------------------
    PRIM_INV u_inv_rst_b (.a(RSTN), .y(rstn_b));

    // -------------------------------------------------------------
    // Control-path next-state logic
    // -------------------------------------------------------------
    PRIM_XOR2 u_ctrl_nxt0 (.a(CTRL[0]), .b(ctrl_ff3_q), .y(ctrl_ff0_d));
    PRIM_AND2 u_ctrl_nxt1 (.a(CTRL[1]), .b(ctrl_ff0_q), .y(ctrl_ff1_d));
    PRIM_OR2  u_ctrl_nxt2 (.a(CTRL[2]), .b(ctrl_ff1_q), .y(ctrl_ff2_d));
    PRIM_XOR2 u_ctrl_nxt3 (.a(CTRL[3]), .b(ctrl_ff2_q), .y(ctrl_ff3_d));

    // -------------------------------------------------------------
    // Datapath next-state logic
    // -------------------------------------------------------------
    PRIM_AND2 u_dp_nxt4 (.a(DIN[0]), .b(ctrl_ff0_q), .y(dp_ff4_d));
    PRIM_XOR2 u_dp_nxt5 (.a(DIN[1]), .b(ctrl_ff1_q), .y(dp_ff5_d));

    // -------------------------------------------------------------
    // Privilege/lock-state next-state logic
    // -------------------------------------------------------------
    PRIM_OR2  u_priv_nxt1 (.a(CTRL[2]), .b(ctrl_ff2_q), .y(priv_ff1_d));
    PRIM_AND2 u_priv_nxt2 (.a(CTRL[3]), .b(priv_ff1_q), .y(priv_ff2_d));

    // -------------------------------------------------------------
    // Control-path registers -- reset pin driven directly by RSTN
    // -------------------------------------------------------------
    PRIM_DFF_SYNC u_ctrl_ff0 (.CLK(CLK), .RST_N(RSTN), .D(ctrl_ff0_d), .Q(ctrl_ff0_q));
    PRIM_DFF_SYNC u_ctrl_ff1 (.CLK(CLK), .RST_N(RSTN), .D(ctrl_ff1_d), .Q(ctrl_ff1_q));
    PRIM_DFF_SYNC u_ctrl_ff2 (.CLK(CLK), .RST_N(RSTN), .D(ctrl_ff2_d), .Q(ctrl_ff2_q));
    PRIM_DFF_SYNC u_ctrl_ff3 (.CLK(CLK), .RST_N(RSTN), .D(ctrl_ff3_d), .Q(ctrl_ff3_q));

    // -------------------------------------------------------------
    // Datapath registers -- reset pin driven directly by RSTN
    // -------------------------------------------------------------
    PRIM_DFF_SYNC u_dp_ff4 (.CLK(CLK), .RST_N(RSTN), .D(dp_ff4_d), .Q(dp_ff4_q));
    PRIM_DFF_SYNC u_dp_ff5 (.CLK(CLK), .RST_N(RSTN), .D(dp_ff5_d), .Q(dp_ff5_q));

    // -------------------------------------------------------------
    // Privilege/lock-state registers -- reset pin driven by rstn_b
    // (the inverted copy of the global reset net), not by RSTN directly.
    // -------------------------------------------------------------
    PRIM_DFF_SYNC u_priv_ff1 (.CLK(CLK), .RST_N(rstn_b), .D(priv_ff1_d), .Q(priv_ff1_q));
    PRIM_DFF_SYNC u_priv_ff2 (.CLK(CLK), .RST_N(rstn_b), .D(priv_ff2_d), .Q(priv_ff2_q));

    // -------------------------------------------------------------
    // Output logic
    // -------------------------------------------------------------
    assign DOUT[0] = dp_ff4_q ^ DIN[2];
    assign DOUT[1] = dp_ff5_q ^ DIN[3];
    assign DOUT[2] = ctrl_ff2_q & priv_ff1_q;
    assign DOUT[3] = ctrl_ff3_q | priv_ff2_q;

endmodule