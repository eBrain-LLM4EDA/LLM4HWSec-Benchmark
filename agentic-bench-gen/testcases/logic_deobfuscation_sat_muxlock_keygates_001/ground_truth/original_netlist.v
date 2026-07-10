module originalnetlist(N1, N2, N3, N6, N7, N22, N23);
    input N1, N2, N3, N6, N7;
    output N22, N23;

    wire N10, N11, N16, N19;

    nand (N10, N1, N3);
    nand (N11, N3, N6);
    nand (N16, N2, N11);
    nand (N19, N11, N7);
    nand (N22, N10, N16);
    nand (N23, N16, N19);

endmodule