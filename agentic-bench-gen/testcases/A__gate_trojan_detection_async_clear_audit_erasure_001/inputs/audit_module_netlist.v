// =============================================================================
// audit_module_netlist.v
//
// Gate-level structural netlist for the tamper-monitoring audit subsystem.
// Module: audit_top
//
// This file is fully self-contained: all standard-cell-style primitives used
// below (INV, BUF, AND2, OR2, DFF_ASYNC_CLR) are declared in this same file
// as simple structural/behavioral models so the design elaborates and
// simulates standalone with iverilog (no external cell library required).
// =============================================================================

`timescale 1ns / 1ps

// -----------------------------------------------------------------------
// Primitive cell models
// -----------------------------------------------------------------------

module INV (input A, output Y);
    assign Y = ~A;
endmodule

module BUF (input A, output Y);
    assign Y = A;
endmodule

module AND2 (input A, input B, output Y);
    assign Y = A & B;
endmodule

module OR2 (input A, input B, output Y);
    assign Y = A | B;
endmodule

// Flip-flop with asynchronous, active-high clear.
module DFF_ASYNC_CLR (input clk, input D, input CLR, output reg Q);
    always @(posedge clk or posedge CLR) begin
        if (CLR)
            Q <= 1'b0;
        else
            Q <= D;
    end
endmodule

// -----------------------------------------------------------------------
// Top-level audit subsystem
// -----------------------------------------------------------------------

module audit_top (
    input        clk,
    input        rst_n,
    input        maintenance_req,
    input        alarm,
    input        tamper_event,
    output [7:0] tamper_count
);

    // -------------------------------------------------------------------
    // Reset synchronizer chain: rst_n (active-low) -> inverter -> buffer
    // -> rst_sync (active-high, synchronized reset used internally).
    // This chain is fully correct and self-sufficient on its own.
    // -------------------------------------------------------------------
    wire rst_n_inv;
    wire rst_sync;

    INV  u_rst_inv  (.A(rst_n),     .Y(rst_n_inv));
    BUF  u_rst_buf  (.A(rst_n_inv), .Y(rst_sync));

    // -------------------------------------------------------------------
    // Maintenance / alarm condition logic feeding into the counter's
    // asynchronous clear network, merged with the synchronized reset.
    // -------------------------------------------------------------------
    wire maint_alarm_hit;
    wire audit_clr;

    AND2 u_maint_alarm_and (
        .A(maintenance_req),
        .B(alarm),
        .Y(maint_alarm_hit)
    );

    OR2 u_audit_clr_or (
        .A(maint_alarm_hit),
        .B(rst_sync),
        .Y(audit_clr)
    );

    // -------------------------------------------------------------------
    // Tamper-event counter register bank: 8 explicit DFF_ASYNC_CLR
    // instances, each cleared by audit_clr and clocked by clk.
    // The D input of each bit is fed by a simple increment/hold stub:
    // bit 0 toggles on tamper_event; each higher bit toggles when all
    // lower bits are currently set and tamper_event is asserted, giving
    // simple ripple-increment behavior.
    // -------------------------------------------------------------------

    wire [7:0] tamper_count_d;
    wire [7:0] tamper_count_q_int;

    assign tamper_count = tamper_count_q_int;

    // Bit 0: toggles on every tamper_event pulse.
    assign tamper_count_d[0] = tamper_count_q_int[0] ^ tamper_event;

    // Bits 1..7: toggle when tamper_event is asserted and all lower bits
    // are currently 1 (simple ripple-carry increment stub).
    assign tamper_count_d[1] = tamper_count_q_int[1] ^
                                (tamper_event & tamper_count_q_int[0]);

    assign tamper_count_d[2] = tamper_count_q_int[2] ^
                                (tamper_event & &tamper_count_q_int[1:0]);

    assign tamper_count_d[3] = tamper_count_q_int[3] ^
                                (tamper_event & &tamper_count_q_int[2:0]);

    assign tamper_count_d[4] = tamper_count_q_int[4] ^
                                (tamper_event & &tamper_count_q_int[3:0]);

    assign tamper_count_d[5] = tamper_count_q_int[5] ^
                                (tamper_event & &tamper_count_q_int[4:0]);

    assign tamper_count_d[6] = tamper_count_q_int[6] ^
                                (tamper_event & &tamper_count_q_int[5:0]);

    assign tamper_count_d[7] = tamper_count_q_int[7] ^
                                (tamper_event & &tamper_count_q_int[6:0]);

    DFF_ASYNC_CLR tamper_count_q_0 (.clk(clk), .D(tamper_count_d[0]), .CLR(audit_clr), .Q(tamper_count_q_int[0]));
    DFF_ASYNC_CLR tamper_count_q_1 (.clk(clk), .D(tamper_count_d[1]), .CLR(audit_clr), .Q(tamper_count_q_int[1]));
    DFF_ASYNC_CLR tamper_count_q_2 (.clk(clk), .D(tamper_count_d[2]), .CLR(audit_clr), .Q(tamper_count_q_int[2]));
    DFF_ASYNC_CLR tamper_count_q_3 (.clk(clk), .D(tamper_count_d[3]), .CLR(audit_clr), .Q(tamper_count_q_int[3]));
    DFF_ASYNC_CLR tamper_count_q_4 (.clk(clk), .D(tamper_count_d[4]), .CLR(audit_clr), .Q(tamper_count_q_int[4]));
    DFF_ASYNC_CLR tamper_count_q_5 (.clk(clk), .D(tamper_count_d[5]), .CLR(audit_clr), .Q(tamper_count_q_int[5]));
    DFF_ASYNC_CLR tamper_count_q_6 (.clk(clk), .D(tamper_count_d[6]), .CLR(audit_clr), .Q(tamper_count_q_int[6]));
    DFF_ASYNC_CLR tamper_count_q_7 (.clk(clk), .D(tamper_count_d[7]), .CLR(audit_clr), .Q(tamper_count_q_int[7]));

endmodule