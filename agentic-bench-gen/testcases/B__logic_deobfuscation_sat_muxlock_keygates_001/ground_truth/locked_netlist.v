module mux2x1(A, B, S, Y);
    input A, B, S;
    output Y;
    wire notS, t1, t2;
    not (notS, S);
    and (t1, A, notS);
    and (t2, B, S);
    or  (Y, t1, t2);
endmodule

module lockednetlist(N1, N2, N3, N6, N7, N22, N23, key);
    input N1, N2, N3, N6, N7;
    output N22, N23;
    input [3:0] key;

    wire N10_func, N10_decoy, N10;
    wire N11_func, N11_decoy, N11;
    wire N16_func, N16_decoy, N16;
    wire N19_func, N19_decoy, N19;

    // N10 = NAND(N1, N3) -- functional path on A (select=0 -> resolved_value=0)
    nand (N10_func, N1, N3);
    not  (N10_decoy, N10_func);
    mux2x1 u_keymux0 (.A(N10_func), .B(N10_decoy), .S(key[0]), .Y(N10));

    // N11 = NAND(N3, N6) -- functional path on B (select=1 -> resolved_value=1)
    nand (N11_func, N3, N6);
    not  (N11_decoy, N11_func);
    mux2x1 u_keymux1 (.A(N11_decoy), .B(N11_func), .S(key[1]), .Y(N11));

    // N16 = NAND(N2, N11) -- functional path on A (select=0 -> resolved_value=0)
    nand (N16_func, N2, N11);
    not  (N16_decoy, N16_func);
    mux2x1 u_keymux2 (.A(N16_func), .B(N16_decoy), .S(key[2]), .Y(N16));

    // N19 = NAND(N11, N7) -- functional path on A (select=0 -> resolved_value=0)
    nand (N19_func, N11, N7);
    not  (N19_decoy, N19_func);
    mux2x1 u_keymux3 (.A(N19_func), .B(N19_decoy), .S(key[3]), .Y(N19));

    nand (N22, N10, N16);
    nand (N23, N16, N19);

endmodule