`timescale 1ns/1ps

//
// netlist.v
//
// Flattened, structural gate-level netlist for the perm_check
// permission comparator. Instantiates cells from
// inputs/primitive_cells.v (co-compile both files together, e.g.:
//   iverilog -g2012 inputs/primitive_cells.v inputs/netlist.v ...
// ).
//

module perm_check (
    input  [3:0] id_in,
    input  [3:0] id_auth,
    output       grant
);

    wire [3:0] eq;
    wire       lo_pair;
    wire       hi_pair;

    // Stage 1: per-bit equality
    XNOR2 u_eq0 (.A(id_in[0]), .B(id_auth[0]), .Y(eq[0]));
    XNOR2 u_eq1 (.A(id_in[1]), .B(id_auth[1]), .Y(eq[1]));
    XOR2  u_eq2 (.A(id_in[2]), .B(id_auth[2]), .Y(eq[2]));
    XNOR2 u_eq3 (.A(id_in[3]), .B(id_auth[3]), .Y(eq[3]));

    // Stage 2: AND-reduction tree
    AND2 u_and_lo    (.A(eq[0]), .B(eq[1]), .Y(lo_pair));
    AND2 u_and_hi    (.A(eq[2]), .B(eq[3]), .Y(hi_pair));
    AND2 u_and_final (.A(lo_pair), .B(hi_pair), .Y(grant));

endmodule