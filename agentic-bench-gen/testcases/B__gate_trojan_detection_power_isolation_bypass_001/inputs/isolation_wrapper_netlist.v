// isolation_wrapper_netlist.v
// Gate-level structural netlist for the secure-domain power-gating isolation
// cell. Built entirely from AND2 / OR2 / MUX2 primitives declared in
// primitive_library.v.

`timescale 1ns/1ps

module isolation_wrapper (
    input  wire [3:0] secure_data,
    input  wire        power_down,
    input  wire         clk,
    output wire [3:0] public_out
);

    // Bit 0 path
    wire net_bypass_bit0;
    wire net_gate_bit0;

    AND2 u_gate_and0 (
        .a(secure_data[0]),
        .b(power_down),
        .y(net_gate_bit0)
    );

    OR2 u_leak_or (
        .a(secure_data[0]),
        .b(net_gate_bit0),
        .y(net_bypass_bit0)
    );

    assign public_out[0] = net_bypass_bit0;

    // Bit 1 path
    wire net_mux1;
    MUX2 u_iso_mux1 (
        .sel(power_down),
        .a(secure_data[1]),
        .b(1'b0),
        .y(net_mux1)
    );
    assign public_out[1] = net_mux1;

    // Bit 2 path
    wire net_mux2;
    MUX2 u_iso_mux2 (
        .sel(power_down),
        .a(secure_data[2]),
        .b(1'b0),
        .y(net_mux2)
    );
    assign public_out[2] = net_mux2;

    // Bit 3 path
    wire net_mux3;
    MUX2 u_iso_mux3 (
        .sel(power_down),
        .a(secure_data[3]),
        .b(1'b0),
        .y(net_mux3)
    );
    assign public_out[3] = net_mux3;

endmodule