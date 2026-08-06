// locked_c17ish.v
// Structural gate-level netlist derived from a small c17-like combinational
// benchmark circuit, logic-locked by inserting four key-controlled 2:1
// multiplexers at internal wire locations. Each multiplexer is built from
// basic gate primitives (no behavioral 'mux' keyword is used).
//
// Each key-controlled multiplexer instance:
//   - has data input A (one candidate signal)
//   - has data input B (the other candidate signal)
//   - has select input S driven by one bit of the 'key' port
//   - produces output Y = (S & B) | (~S & A), built from and/or/not primitives
//
// All instance names of these locking multiplexers contain the substring
// "keymux".

module locked_c17ish (
    N1, N2, N3, N6, N7,
    key,
    N22, N23
);

    input  N1, N2, N3, N6, N7;
    input  [3:0] key;
    output N22, N23;

    // Internal nets (original, unlocked functional signals)
    wire N10, N11, N16, N19;

    // Decoy / corrupted alternative signals for locking multiplexers
    wire N10_alt, N11_alt, N16_alt, N19_alt;

    // Post-lock (selected) versions of the locked nets
    wire N10_locked, N11_locked, N16_locked, N19_locked;

    // Select-line inverters
    wire sel0_n, sel1_n, sel2_n, sel3_n;

    // Mux internal AND-term nets
    wire m0_a_and_selN, m0_b_and_sel;
    wire m1_a_and_selN, m1_b_and_sel;
    wire m2_a_and_selN, m2_b_and_sel;
    wire m3_a_and_selN, m3_b_and_sel;

    // ---------------------------------------------------------------
    // Original (unlocked) c17-like structural logic
    // ---------------------------------------------------------------

    nand g1 (N10, N1,  N3);
    nand g2 (N11, N3,  N6);
    nand g3 (N16, N2,  N11);
    nand g4 (N19, N11, N7);

    // ---------------------------------------------------------------
    // Decoy / corrupted alternative signals for locking multiplexers.
    // These are deliberately incorrect variants of the functional
    // signals N10, N11, N16, N19, used as the "B" input of each keymux.
    // ---------------------------------------------------------------

    not gd1 (N10_alt, N10);
    not gd2 (N11_alt, N11);
    not gd3 (N16_alt, N16);
    not gd4 (N19_alt, N19);

    // ---------------------------------------------------------------
    // Key-controlled locking multiplexers (2:1 mux from primitives)
    //   Y = (S & B) | (~S & A)
    // select S = key[i]
    // ---------------------------------------------------------------

    // keymux instance 0: locks node N10, select = key[0]
    not  g_not0 (sel0_n, key[0]);
    and  g_m0a  (m0_a_and_selN, N10, sel0_n);
    and  g_m0b  (m0_b_and_sel,  N10_alt, key[0]);
    or   u_keymux0 (N10_locked, m0_a_and_selN, m0_b_and_sel);

    // keymux instance 1: locks node N11, select = key[1]
    not  g_not1 (sel1_n, key[1]);
    and  g_m1a  (m1_a_and_selN, N11, sel1_n);
    and  g_m1b  (m1_b_and_sel,  N11_alt, key[1]);
    or   u_keymux1 (N11_locked, m1_a_and_selN, m1_b_and_sel);

    // keymux instance 2: locks node N16, select = key[2]
    not  g_not2 (sel2_n, key[2]);
    and  g_m2a  (m2_a_and_selN, N16, sel2_n);
    and  g_m2b  (m2_b_and_sel,  N16_alt, key[2]);
    or   u_keymux2 (N16_locked, m2_a_and_selN, m2_b_and_sel);

    // keymux instance 3: locks node N19, select = key[3]
    not  g_not3 (sel3_n, key[3]);
    and  g_m3a  (m3_a_and_selN, N19, sel3_n);
    and  g_m3b  (m3_b_and_sel,  N19_alt, key[3]);
    or   u_keymux3 (N19_locked, m3_a_and_selN, m3_b_and_sel);

    // ---------------------------------------------------------------
    // Remaining logic consumes the (post-lock) versions of the nets,
    // so an incorrect key value at any keymux corrupts the outputs.
    // ---------------------------------------------------------------

    nand g5 (N22, N11_locked, N16_locked);
    nand g6 (N23, N16_locked, N19_locked);

endmodule