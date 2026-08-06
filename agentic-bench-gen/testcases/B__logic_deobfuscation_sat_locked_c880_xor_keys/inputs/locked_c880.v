// locked_c880.v
// Structural gate-level netlist derived from an ISCAS-85 c880-style
// combinational fragment, modified with logic locking.
// Ports: primary inputs n1..n20, primary outputs m1..m10,
// and an 8-bit key input bus keyIn[0:7].

module locked_c880 (
    n1, n2, n3, n4, n5, n6, n7, n8, n9, n10,
    n11, n12, n13, n14, n15, n16, n17, n18, n19, n20,
    keyIn,
    m1, m2, m3, m4, m5, m6, m7, m8, m9, m10
);

    input  n1, n2, n3, n4, n5, n6, n7, n8, n9, n10;
    input  n11, n12, n13, n14, n15, n16, n17, n18, n19, n20;
    input  [0:7] keyIn;
    output m1, m2, m3, m4, m5, m6, m7, m8, m9, m10;

    // Internal nets
    wire w1, w2, w3, w4, w5, w6, w7, w8, w9, w10;
    wire w11, w12, w13, w14, w15, w16, w17, w18, w19, w20;
    wire w21, w22, w23, w24, w25, w26, w27, w28, w29, w30;
    wire w31, w32, w33, w34, w35, w36, w37, w38;

    // Key-gate protected nets
    wire kw0, kw1, kw2, kw3, kw4, kw5, kw6, kw7;

    // Dead-end stub nets (not reaching any primary output)
    wire stubnet_a, stubnet_b, stub_and_a, stub_and_b;

    // ---------------- First logic cone ----------------
    and  u1  (w1,  n1,  n2);
    nand u2  (w2,  n3,  n4);
    or   u3  (w3,  n5,  n6);
    nor  u4  (w4,  n7,  n8);
    not  u5  (w5,  n9);
    and  u6  (w6,  n10, n11);
    nand u7  (w7,  n12, n13);
    or   u8  (w8,  n14, n15);
    nor  u9  (w9,  n16, n17);
    not  u10 (w10, n18);

    and  u11 (w11, w1, w2);
    or   u12 (w12, w3, w4);
    nand u13 (w13, w5, w6);
    nor  u14 (w14, w7, w8);
    and  u15 (w15, w9, w10);

    or   u16 (w16, w11, w12);
    and  u17 (w17, w13, w14);
    nand u18 (w18, w15, n19);
    nor  u19 (w19, n20, w16);
    not  u20 (w20, w17);

    // ---------------- Key gate 0: XOR, feeds live cone ----------------
    xor  u_key0 (kw0, w18, keyIn[0]);

    and  u21 (w21, kw0, w19);
    or   u22 (w22, w20, w21);

    // ---------------- Key gate 1: XNOR, feeds live cone ----------------
    xnor u_key1 (kw1, w22, keyIn[1]);

    nand u23 (w23, kw1, n1);
    nor  u24 (w24, w23, n2);

    // ---------------- Key gate 2: XOR, feeds live cone ----------------
    xor  u_key2 (kw2, w24, keyIn[2]);

    and  u25 (w25, kw2, w16);
    or   u26 (w26, w25, w17);

    // ---------------- Key gate 3: XOR, DEAD END (stub only) ----------------
    and  u27 (stub_and_a, n3, n4);
    xor  u_key3 (kw3, stub_and_a, keyIn[3]);
    and  u28 (stubnet_a, kw3, n5);
    // stubnet_a is intentionally not consumed further; no path to any m*

    // ---------------- Continue live cone ----------------
    nor  u29 (w27, w26, n6);
    not  u30 (w28, w27);

    // ---------------- Key gate 4: XOR, feeds live cone ----------------
    xor  u_key4 (kw4, w28, keyIn[4]);

    and  u31 (w29, kw4, n7);
    or   u32 (w30, w29, n8);

    // ---------------- Key gate 5: XNOR, feeds live cone ----------------
    xnor u_key5 (kw5, w30, keyIn[5]);

    nand u33 (w31, kw5, n9);
    nor  u34 (w32, w31, n10);

    // ---------------- Key gate 6: XNOR, DEAD END (stub only) ----------------
    or   u35 (stub_and_b, n11, n12);
    xnor u_key6 (kw6, stub_and_b, keyIn[6]);
    or   u36 (stubnet_b, kw6, n13);
    // stubnet_b is intentionally not consumed further; no path to any m*

    // ---------------- Continue live cone ----------------
    and  u37 (w33, w32, n14);
    or   u38 (w34, w33, n15);

    // ---------------- Key gate 7: XOR, feeds live cone ----------------
    xor  u_key7 (kw7, w34, keyIn[7]);

    nand u39 (w35, kw7, n16);
    nor  u40 (w36, w35, n17);
    and  u41 (w37, w36, n18);
    or   u42 (w38, w37, n19);

    // ---------------- Output stage ----------------
    buf  u43 (m1,  w11);
    buf  u44 (m2,  w14);
    buf  u45 (m3,  w22);
    buf  u46 (m4,  w24);
    buf  u47 (m5,  w26);
    buf  u48 (m6,  w28);
    buf  u49 (m7,  w32);
    buf  u50 (m8,  w34);
    buf  u51 (m9,  w38);
    or   u52 (m10, w20, n20);

endmodule