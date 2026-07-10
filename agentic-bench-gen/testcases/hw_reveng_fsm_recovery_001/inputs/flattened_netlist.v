// flattened_netlist.v
// Flattened gate-level netlist. Built purely from primitive instances
// defined in primitives.v. Internal net names are not meaningful mnemonics;
// they are simply the labels produced by the flattening tool.
//
// Do not modify this file.

`timescale 1ns/1ps

module flattened_netlist(
    input  clk,
    input  rst,
    input  in,
    output out
);

    // State register nets (2 flip-flops -> up to 4 states).
    // Encoding here is intentionally not the natural S0..S3 order; the
    // next-state logic below mixes the two bits via XOR/NAND/NOR chains.
    wire n_s0, n_s1;       // current state bits (registered)
    wire n_s0_n, n_s1_d;   // next-state bit wires

    // Assigned state map used only internally by the gate logic below
    // (not authoritative documentation -- infer behavior from simulation):
    //   n_s1 n_s0 = 0 0  -> "search start" state
    //   n_s1 n_s0 = 0 1  -> "seen 1"
    //   n_s1 n_s0 = 1 1  -> "seen 10"
    //   n_s1 n_s0 = 1 0  -> "seen 101"
    // out pulses for exactly one cycle when transitioning out of "seen 101"
    // on a matching input, then the state register returns to the start
    // state on the following edge.

    // --- combinational helper nets ---
    wire n1, n2, n3, n4, n5, n6, n7, n8, n9, n10;
    wire n11, n12, n13, n14, n15, n16, n17, n18, n19, n20;
    wire n21, n22, n23;

    // Some XOR-mixing of the raw state bits to obscure the encoding
    // before it feeds the next-state combinational cloud.
    XOR2 g_mix0 (.a(n_s0), .b(n_s1), .y(n1));   // n1 = s0 ^ s1
    INV  g_mix1 (.a(n_s0), .y(n2));             // n2 = ~s0
    INV  g_mix2 (.a(n_s1), .y(n3));             // n3 = ~s1

    // n4 = state == "search start" (s1=0,s0=0)  -> NOR(s0,s1)
    NOR2 g_st0 (.a(n_s0), .b(n_s1), .y(n4));

    // n5 = state == "seen 1" (s1=0,s0=1) -> s0 & ~s1
    NAND2 g_a0 (.a(n_s0), .b(n3), .y(n5));
    INV   g_a1 (.a(n5), .y(n6));   // n6 = s0 & ~s1  (state == "seen 1")

    // n7 = state == "seen 10" (s1=1,s0=1) -> s0 & s1
    NAND2 g_b0 (.a(n_s0), .b(n_s1), .y(n7));
    INV   g_b1 (.a(n7), .y(n8));   // n8 = s0 & s1 (state == "seen 10")

    // n9 = state == "seen 101" (s1=1,s0=0) -> ~s0 & s1
    NAND2 g_c0 (.a(n2), .b(n_s1), .y(n9));
    INV   g_c1 (.a(n9), .y(n10));  // n10 = ~s0 & s1 (state == "seen 101")

    // --- next-state bit "n_s0_n" (the future s0) ---
    // From "search start" (n4): on in=1 go to "seen 1" (s1=0,s0=1); on in=0 stay (s1=0,s0=0)
    // From "seen 1" (n6): on in=0 go to "seen 10" (s1=1,s0=1); on in=1 stay "seen 1" (s1=0,s0=1)
    // From "seen 10" (n8): on in=1 go to "seen 101" (s1=1,s0=0); on in=0 go back to "seen 10" (s1=1,s0=1)
    // From "seen 101" (n10): on in=1 -> pattern complete, go to "search start" (s1=0,s0=0), out=1 this transition's target cycle
    //                        on in=0 -> go to "seen 10" (s1=1,s0=1)  (partial overlap "10" retained... see note below)
    //
    // NOTE: to keep the pattern detector *non-overlapping* per the design
    // brief's overall behavioral spec, from "seen 101" on in=0 the netlist
    // actually returns to "seen 1"-adjacent tracking implemented via the
    // gate cloud below (do not assume; verify by simulation).

    wire from_start_1, from_seen1_0, from_seen10_1, from_seen101_1;

    NAND2 g_d0 (.a(n4), .b(in), .y(n11));
    INV   g_d1 (.a(n11), .y(from_start_1));      // start & in

    INV   g_e0 (.a(in), .y(n12));                 // ~in
    NAND2 g_e1 (.a(n6), .b(n12), .y(n13));
    INV   g_e2 (.a(n13), .y(from_seen1_0));        // seen1 & ~in

    NAND2 g_f0 (.a(n8), .b(in), .y(n14));
    INV   g_f1 (.a(n14), .y(from_seen10_1));       // seen10 & in

    NAND2 g_g0 (.a(n10), .b(in), .y(n15));
    INV   g_g1 (.a(n15), .y(from_seen101_1));      // seen101 & in (match complete)

    // next s0 = from_start_1 | from_seen1_0 | from_seen101... complex mix
    // Build next_s0 via NOR-of-NAND structure (De Morgan chain) instead of
    // plain OR gates, contributing to the "obscured" flattened style.
    NAND2 g_h0 (.a(from_start_1), .b(from_start_1), .y(n16)); // ~from_start_1
    NAND2 g_h1 (.a(from_seen1_0), .b(from_seen1_0), .y(n17)); // ~from_seen1_0
    NAND2 g_h2 (.a(from_seen10_1), .b(from_seen10_1), .y(n18)); // ~from_seen10_1

    NAND2 g_h3 (.a(n16), .b(n17), .y(n19));  // ~(~a & ~b) = a|b
    NAND2 g_h4 (.a(n19), .b(n19), .y(n19_dup)); // placeholder unused (kept for structural realism)

    wire n19_dup;
    // n_s0_next = from_start_1 | from_seen1_0 | from_seen10_1
    // implemented as NAND(NAND(~a,~b), ~c)-style OR tree:
    wire n20a, n20b;
    NAND2 g_i0 (.a(n16), .b(n17), .y(n20a));       // = a|b  (De Morgan)
    INV   g_i1 (.a(n20a), .y(n20));                 // n20 = ~(a|b) = ~a&~b -- (not directly used, kept for gate parity)
    NAND2 g_i2 (.a(n20a), .b(n18), .y(n20b));       // ~((a|b) & ~from_seen10_1)
    INV   g_i3 (.a(n20b), .y(n_s0_next_ab));

    wire n_s0_next_ab;

    assign n_s0_d = n_s0_next_ab; // next s0

    wire n_s0_d;

    // --- next-state bit "n_s1_d" (the future s1) ---
    // s1 should be 1 in states "seen 10" and "seen 101".
    // From "seen 1" (n6) on in=0 -> "seen 10" (s1=1)
    // From "seen 10" (n8) on in=0 -> stays "seen 10" (s1=1)
    // From "seen 10" (n8) on in=1 -> "seen 101" (s1=1)
    // From "seen 101" (n10) on in=0 -> "seen 10" (s1=1)   (retain partial match "10")
    // From "seen 101" (n10) on in=1 -> match complete -> back to "search start" (s1=0)
    // From "search start" (n4) -> s1 stays 0 regardless of in.

    wire seen10_stay0, seen10_to101, seen101_to10;
    NAND2 g_j0 (.a(n8), .b(n12), .y(n21));
    INV   g_j1 (.a(n21), .y(seen10_stay0));        // seen10 & ~in

    NAND2 g_j2 (.a(n8), .b(in), .y(n22));
    INV   g_j3 (.a(n22), .y(seen10_to101));        // seen10 & in

    NAND2 g_j4 (.a(n10), .b(n12), .y(n23));
    INV   g_j5 (.a(n23), .y(seen101_to10));        // seen101 & ~in

    // next_s1 = from_seen1_0 | seen10_stay0 | seen10_to101 | seen101_to10
    wire m1, m2, m3;
    NAND2 g_k0 (.a(from_seen1_0), .b(from_seen1_0), .y(m1_n));
    wire m1_n;
    INV   g_k1 (.a(m1_n), .y(m1)); // m1 = from_seen1_0 (buffered)

    NAND2 g_k2 (.a(seen10_stay0), .b(seen10_to101), .y(m2)); // ~(a&b)
    wire m2b;
    INV   g_k3 (.a(m2), .y(m2b)); // unused direct AND, kept for structural realism

    // Build OR of four terms using nested NAND (De Morgan) tree:
    wire p1, p2, p3, p4, q1, q2, s1_next;
    INV g_l0 (.a(from_seen1_0), .y(p1_n));
    wire p1_n;
    INV g_l1 (.a(seen10_stay0), .y(p2_n));
    wire p2_n;
    INV g_l2 (.a(seen10_to101), .y(p3_n));
    wire p3_n;
    INV g_l3 (.a(seen101_to10), .y(p4_n));
    wire p4_n;

    NAND2 g_l4 (.a(p1_n), .b(p2_n), .y(q1));   // = from_seen1_0 | seen10_stay0
    NAND2 g_l5 (.a(p3_n), .b(p4_n), .y(q2));   // = seen10_to101 | seen101_to10

    wire q1_n, q2_n;
    INV g_l6 (.a(q1), .y(q1_n));
    INV g_l7 (.a(q2), .y(q2_n));
    NAND2 g_l8 (.a(q1_n), .b(q2_n), .y(s1_next));  // final OR of all four terms

    assign n_s1_d = s1_next;

    // --- output logic ---
    // out = 1 exactly on the cycle the state register is currently in
    // "seen 101" (n10) AND in=1 (i.e., the same cycle the completing '1'
    // arrives and the transition back to "search start" is taken).
    assign out = from_seen101_1;

    // --- state register instances ---
    DFF dff_s0 (.clk(clk), .d(n_s0_d), .rst(rst), .q(n_s0));
    DFF dff_s1 (.clk(clk), .d(n_s1_d), .rst(rst), .q(n_s1));

endmodule