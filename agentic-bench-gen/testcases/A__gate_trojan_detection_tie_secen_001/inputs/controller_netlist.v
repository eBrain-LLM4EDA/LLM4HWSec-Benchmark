// controller_netlist.v
//
// Flat structural gate-level netlist for the 'controller' peripheral
// block. Built entirely from cells declared in cell_library.v.
//
// Ports:
//   clk            - system clock
//   rst            - synchronous active-high reset
//   access_grant   - access-control input
//   admin_override - access-control input
//   lock_bit       - access-control input
//   data_in[7:0]   - data input bus
//   data_out[7:0]  - data output bus
//   secure_enable  - observability output for the secure-mode enable net

`timescale 1ns/1ps

module controller (
    input        clk,
    input        rst,
    input        access_grant,
    input        admin_override,
    input        lock_bit,
    input  [7:0] data_in,
    output [7:0] data_out,
    output       secure_enable
);

    // -----------------------------------------------------------------
    // secure_enable drive
    // -----------------------------------------------------------------
    // secure_enable is driven directly by a constant-tie cell.
    TIEHI U_TIE_SECEN (
        .o (secure_enable)
    );

    // -----------------------------------------------------------------
    // Intended secure-enable computation cone
    // -----------------------------------------------------------------
    wire sec_and_out;
    wire sec_enable_calc;

    AND2 u_sec_and1 (
        .o (sec_and_out),
        .a (access_grant),
        .b (admin_override)
    );

    OR2 u_sec_or2 (
        .o (sec_enable_calc),
        .a (sec_and_out),
        .b (lock_bit)
    );
    // NOTE: sec_enable_calc has no further connections in this netlist;
    // it is not read by any other instance or output port.

    // -----------------------------------------------------------------
    // Unrelated functional datapath: data_in -> data_out
    // -----------------------------------------------------------------
    wire [7:0] data_reg_q;
    wire [7:0] data_muxed;
    wire       inv_lock_bit;

    INV u_inv_lock (
        .o (inv_lock_bit),
        .a (lock_bit)
    );

    MUX2 u_mux_bit0 (
        .o   (data_muxed[0]),
        .a   (data_in[0]),
        .b   (data_in[7]),
        .sel (inv_lock_bit)
    );

    BUF u_buf_bit1 (
        .o (data_muxed[1]),
        .a (data_in[1])
    );

    BUF u_buf_bit2 (
        .o (data_muxed[2]),
        .a (data_in[2])
    );

    BUF u_buf_bit3 (
        .o (data_muxed[3]),
        .a (data_in[3])
    );

    BUF u_buf_bit4 (
        .o (data_muxed[4]),
        .a (data_in[4])
    );

    BUF u_buf_bit5 (
        .o (data_muxed[5]),
        .a (data_in[5])
    );

    BUF u_buf_bit6 (
        .o (data_muxed[6]),
        .a (data_in[6])
    );

    BUF u_buf_bit7 (
        .o (data_muxed[7]),
        .a (data_in[7])
    );

    DFF u_dff_bit0 (
        .q   (data_reg_q[0]),
        .d   (data_muxed[0]),
        .clk (clk),
        .rst (rst)
    );

    DFF u_dff_bit1 (
        .q   (data_reg_q[1]),
        .d   (data_muxed[1]),
        .clk (clk),
        .rst (rst)
    );

    DFF u_dff_bit2 (
        .q   (data_reg_q[2]),
        .d   (data_muxed[2]),
        .clk (clk),
        .rst (rst)
    );

    DFF u_dff_bit3 (
        .q   (data_reg_q[3]),
        .d   (data_muxed[3]),
        .clk (clk),
        .rst (rst)
    );

    DFF u_dff_bit4 (
        .q   (data_reg_q[4]),
        .d   (data_muxed[4]),
        .clk (clk),
        .rst (rst)
    );

    DFF u_dff_bit5 (
        .q   (data_reg_q[5]),
        .d   (data_muxed[5]),
        .clk (clk),
        .rst (rst)
    );

    DFF u_dff_bit6 (
        .q   (data_reg_q[6]),
        .d   (data_muxed[6]),
        .clk (clk),
        .rst (rst)
    );

    DFF u_dff_bit7 (
        .q   (data_reg_q[7]),
        .d   (data_muxed[7]),
        .clk (clk),
        .rst (rst)
    );

    assign data_out = data_reg_q;

endmodule