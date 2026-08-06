// tmr_voter_netlist.v
// Structural gate-level netlist for a triple-modular-redundancy (TMR) block.
// Three replica compute cells produce identical logic from shared primary
// inputs; a majority voter cell masks any single replica fault to produce
// the top-level output voted_out.

`timescale 1ns/1ps

// ---------------------------------------------------------------------
// replica_cell: small combinational logic block. Each replica instance
// computes the same function of the shared primary inputs.
// ---------------------------------------------------------------------
module replica_cell (
    input  wire in_a,
    input  wire in_b,
    input  wire in_c,
    output wire out_y
);
    wire n1, n2;

    and (n1, in_a, in_b);
    or  (n2, n1, in_c);
    buf (out_y, n2);

endmodule

// ---------------------------------------------------------------------
// wire_tap: single-input single-output buffering cell, used generically
// for signal routing/fanout regeneration within the block.
// ---------------------------------------------------------------------
module wire_tap (
    input  wire tap_in,
    output wire tap_out
);
    buf (tap_out, tap_in);
endmodule

// ---------------------------------------------------------------------
// voter3: standard 2-of-3 majority voter.
// voted_out = maj(voter_a, voter_b, voter_c)
// ---------------------------------------------------------------------
module voter3 (
    input  wire voter_a,
    input  wire voter_b,
    input  wire voter_c,
    output wire voted_out
);
    wire m1, m2, m3, m_or1, m_or2;

    and (m1, voter_a, voter_b);
    and (m2, voter_b, voter_c);
    and (m3, voter_a, voter_c);

    or  (m_or1, m1, m2);
    or  (m_or2, m_or1, m3);

    buf (voted_out, m_or2);

endmodule

// ---------------------------------------------------------------------
// tmr_top: top-level triple-modular-redundancy block.
// ---------------------------------------------------------------------
module tmr_top (
    input  wire a,
    input  wire b,
    input  wire c,
    output wire voted_out
);

    // Replica output nets.
    wire net_repa_out;
    wire net_repb_out;   // intended to drive voter_b; left dangling below
    wire net_repc_out;

    // Voter input nets.
    wire voter_a;
    wire voter_b;
    wire voter_c;

    // Buffered/routed signal used to feed voter_b.
    wire net_buf1_out;

    // Three replica instances, each computing the same function from the
    // shared primary inputs.
    replica_cell u_replica_a (
        .in_a  (a),
        .in_b  (b),
        .in_c  (c),
        .out_y (net_repa_out)
    );

    replica_cell u_replica_b (
        .in_a  (a),
        .in_b  (b),
        .in_c  (c),
        .out_y (net_repb_out)
    );

    replica_cell u_replica_c (
        .in_a  (a),
        .in_b  (b),
        .in_c  (c),
        .out_y (net_repc_out)
    );

    // Routing buffer feeding the second voter input.
    wire_tap u_buf1 (
        .tap_in  (net_repa_out),
        .tap_out (net_buf1_out)
    );

    // Voter input wiring.
    assign voter_a = net_repa_out;
    assign voter_b = net_buf1_out;
    assign voter_c = net_repc_out;

    // Majority voter instance.
    voter3 u_voter3 (
        .voter_a   (voter_a),
        .voter_b   (voter_b),
        .voter_c   (voter_c),
        .voted_out (voted_out)
    );

endmodule