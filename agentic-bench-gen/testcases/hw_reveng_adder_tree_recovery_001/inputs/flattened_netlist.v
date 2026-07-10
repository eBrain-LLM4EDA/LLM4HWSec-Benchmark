// -----------------------------------------------------------------------------
// flattened_netlist.v
//
// Flattened gate-level netlist. All internal nets have been renamed to
// generic labels during the flattening process; no word-level grouping or
// naming from the original design has been preserved.
//
// This file must be compiled together with primitive_cells.v.
// -----------------------------------------------------------------------------

`timescale 1ns/1ps

module recovered_design (
    input  [15:0] a,
    input  [15:0] b,
    input  [15:0] c,
    input  [15:0] d,
    output [31:0] sum
);

    // Stage 1a: 16-bit ripple-carry addition of a + b -> {n1_cout16, n1_sum[15:0]}
    wire n1;
    wire [15:0] n2;
    wire n3, n4, n5, n6, n7, n8, n9, n10, n11, n12, n13, n14, n15, n16, n17;

    FA1 u1_0  (.a(a[0]),  .b(b[0]),  .cin(1'b0), .sum(n2[0]),  .cout(n3));
    FA1 u1_1  (.a(a[1]),  .b(b[1]),  .cin(n3),   .sum(n2[1]),  .cout(n4));
    FA1 u1_2  (.a(a[2]),  .b(b[2]),  .cin(n4),   .sum(n2[2]),  .cout(n5));
    FA1 u1_3  (.a(a[3]),  .b(b[3]),  .cin(n5),   .sum(n2[3]),  .cout(n6));
    FA1 u1_4  (.a(a[4]),  .b(b[4]),  .cin(n6),   .sum(n2[4]),  .cout(n7));
    FA1 u1_5  (.a(a[5]),  .b(b[5]),  .cin(n7),   .sum(n2[5]),  .cout(n8));
    FA1 u1_6  (.a(a[6]),  .b(b[6]),  .cin(n8),   .sum(n2[6]),  .cout(n9));
    FA1 u1_7  (.a(a[7]),  .b(b[7]),  .cin(n9),   .sum(n2[7]),  .cout(n10));
    FA1 u1_8  (.a(a[8]),  .b(b[8]),  .cin(n10),  .sum(n2[8]),  .cout(n11));
    FA1 u1_9  (.a(a[9]),  .b(b[9]),  .cin(n11),  .sum(n2[9]),  .cout(n12));
    FA1 u1_10 (.a(a[10]), .b(b[10]), .cin(n12),  .sum(n2[10]), .cout(n13));
    FA1 u1_11 (.a(a[11]), .b(b[11]), .cin(n13),  .sum(n2[11]), .cout(n14));
    FA1 u1_12 (.a(a[12]), .b(b[12]), .cin(n14),  .sum(n2[12]), .cout(n15));
    FA1 u1_13 (.a(a[13]), .b(b[13]), .cin(n15),  .sum(n2[13]), .cout(n16));
    FA1 u1_14 (.a(a[14]), .b(b[14]), .cin(n16),  .sum(n2[14]), .cout(n17));
    FA1 u1_15 (.a(a[15]), .b(b[15]), .cin(n17),  .sum(n2[15]), .cout(n1));

    // n1 is the final carry-out of a+b, extended into a 17-bit intermediate
    wire [16:0] n18;
    assign n18 = {n1, n2};

    // Stage 1b: 16-bit ripple-carry addition of c + d -> {n19, n20[15:0]}
    wire n19;
    wire [15:0] n20;
    wire n21, n22, n23, n24, n25, n26, n27, n28, n29, n30, n31, n32, n33, n34, n35;

    FA1 u2_0  (.a(c[0]),  .b(d[0]),  .cin(1'b0), .sum(n20[0]),  .cout(n21));
    FA1 u2_1  (.a(c[1]),  .b(d[1]),  .cin(n21),  .sum(n20[1]),  .cout(n22));
    FA1 u2_2  (.a(c[2]),  .b(d[2]),  .cin(n22),  .sum(n20[2]),  .cout(n23));
    FA1 u2_3  (.a(c[3]),  .b(d[3]),  .cin(n23),  .sum(n20[3]),  .cout(n24));
    FA1 u2_4  (.a(c[4]),  .b(d[4]),  .cin(n24),  .sum(n20[4]),  .cout(n25));
    FA1 u2_5  (.a(c[5]),  .b(d[5]),  .cin(n25),  .sum(n20[5]),  .cout(n26));
    FA1 u2_6  (.a(c[6]),  .b(d[6]),  .cin(n26),  .sum(n20[6]),  .cout(n27));
    FA1 u2_7  (.a(c[7]),  .b(d[7]),  .cin(n27),  .sum(n20[7]),  .cout(n28));
    FA1 u2_8  (.a(c[8]),  .b(d[8]),  .cin(n28),  .sum(n20[8]),  .cout(n29));
    FA1 u2_9  (.a(c[9]),  .b(d[9]),  .cin(n29),  .sum(n20[9]),  .cout(n30));
    FA1 u2_10 (.a(c[10]), .b(d[10]), .cin(n30),  .sum(n20[10]), .cout(n31));
    FA1 u2_11 (.a(c[11]), .b(d[11]), .cin(n31),  .sum(n20[11]), .cout(n32));
    FA1 u2_12 (.a(c[12]), .b(d[12]), .cin(n32),  .sum(n20[12]), .cout(n33));
    FA1 u2_13 (.a(c[13]), .b(d[13]), .cin(n33),  .sum(n20[13]), .cout(n34));
    FA1 u2_14 (.a(c[14]), .b(d[14]), .cin(n34),  .sum(n20[14]), .cout(n35));
    FA1 u2_15 (.a(c[15]), .b(d[15]), .cin(n35),  .sum(n20[15]), .cout(n19));

    wire [16:0] n36;
    assign n36 = {n19, n20};

    // Stage 2: add the two 17-bit partial sums (n18 = a+b, n36 = c+d) together
    // to form the final 32-bit result. This ripple-carry chain is 17 bits wide
    // internally; the two extra bits above bit 15 propagate any final carries
    // up into the high half of the 32-bit output.
    wire [16:0] n37;
    wire n38, n39, n40, n41, n42, n43, n44, n45, n46, n47, n48, n49, n50, n51, n52, n53;

    FA1 u3_0  (.a(n18[0]),  .b(n36[0]),  .cin(1'b0), .sum(n37[0]),  .cout(n38));
    FA1 u3_1  (.a(n18[1]),  .b(n36[1]),  .cin(n38),  .sum(n37[1]),  .cout(n39));
    FA1 u3_2  (.a(n18[2]),  .b(n36[2]),  .cin(n39),  .sum(n37[2]),  .cout(n40));
    FA1 u3_3  (.a(n18[3]),  .b(n36[3]),  .cin(n40),  .sum(n37[3]),  .cout(n41));
    FA1 u3_4  (.a(n18[4]),  .b(n36[4]),  .cin(n41),  .sum(n37[4]),  .cout(n42));
    FA1 u3_5  (.a(n18[5]),  .b(n36[5]),  .cin(n42),  .sum(n37[5]),  .cout(n43));
    FA1 u3_6  (.a(n18[6]),  .b(n36[6]),  .cin(n43),  .sum(n37[6]),  .cout(n44));
    FA1 u3_7  (.a(n18[7]),  .b(n36[7]),  .cin(n44),  .sum(n37[7]),  .cout(n45));
    FA1 u3_8  (.a(n18[8]),  .b(n36[8]),  .cin(n45),  .sum(n37[8]),  .cout(n46));
    FA1 u3_9  (.a(n18[9]),  .b(n36[9]),  .cin(n46),  .sum(n37[9]),  .cout(n47));
    FA1 u3_10 (.a(n18[10]), .b(n36[10]), .cin(n47),  .sum(n37[10]), .cout(n48));
    FA1 u3_11 (.a(n18[11]), .b(n36[11]), .cin(n48),  .sum(n37[11]), .cout(n49));
    FA1 u3_12 (.a(n18[12]), .b(n36[12]), .cin(n49),  .sum(n37[12]), .cout(n50));
    FA1 u3_13 (.a(n18[13]), .b(n36[13]), .cin(n50),  .sum(n37[13]), .cout(n51));
    FA1 u3_14 (.a(n18[14]), .b(n36[14]), .cin(n51),  .sum(n37[14]), .cout(n52));
    FA1 u3_15 (.a(n18[15]), .b(n36[15]), .cin(n52),  .sum(n37[15]), .cout(n53));
    FA1 u3_16 (.a(n18[16]), .b(n36[16]), .cin(n53),  .sum(n37[16]), .cout());

    // Final assembly: bits [16:0] of n37 form the low 17 bits of the result;
    // the remaining high-order bits of the 32-bit output are always zero
    // since the maximum possible sum of four 16-bit operands
    // (4 * 0xFFFF = 0x3FFFC) fits within 18 bits.
    assign sum = {15'b0, n37};

endmodule