// design.v
// Flat gate-level netlist with hidden Trojan: trigger absorbed into AOI/OAI cells.
// The trigger is a rare condition formed by an AOI21 and an OAI22 whose outputs combine
// to drive an XOR payload cell that flips control_out.

module top (
    input  wire clk,
    input  wire rst_n,
    input  wire [3:0] in,
    output wire control_out
);

    // Internal nets
    wire n1, n2, n3, n4, n5, n6, n7, n8, n9, n10;
    wire n11, n12, n13, n14, n15, n16, n17, n18, n19, n20;
    wire n21, n22, n23, n24, n25, n26, n27, n28, n29, n30;
    wire n_trigger_internal;
    wire n_payload_out;

    // Legitimate logic: some DFFs and combinational gates
    DFF dff1 (.D(n1), .Q(n2), .CLK(clk), .RST(rst_n));
    DFF dff2 (.D(n3), .Q(n4), .CLK(clk), .RST(rst_n));
    DFF dff3 (.D(n5), .Q(n6), .CLK(clk), .RST(rst_n));
    DFF dff4 (.D(n7), .Q(n8), .CLK(clk), .RST(rst_n));

    INV inv1 (.A(in[0]), .Y(n1));
    INV inv2 (.A(in[1]), .Y(n3));
    INV inv3 (.A(in[2]), .Y(n5));
    INV inv4 (.A(in[3]), .Y(n7));

    XOR xor1 (.A(n2), .B(n4), .Y(n9));
    XOR xor2 (.A(n6), .B(n8), .Y(n10));

    AOI21 aoi_leg1 (.A0(n9), .A1(n10), .B0(in[0]), .Y(n11));
    OAI22 oai_leg1 (.A0(n11), .A1(in[1]), .B0(n2), .B1(n4), .Y(n12));

    // More legitimate logic
    DFF dff5 (.D(n12), .Q(n13), .CLK(clk), .RST(rst_n));
    DFF dff6 (.D(n13), .Q(n14), .CLK(clk), .RST(rst_n));

    INV inv5 (.A(n14), .Y(n15));
    XOR xor3 (.A(n15), .B(in[2]), .Y(n16));

    AOI21 aoi_leg2 (.A0(n16), .A1(in[3]), .B0(n13), .Y(n17));
    OAI22 oai_leg2 (.A0(n17), .A1(n14), .B0(n15), .B1(in[0]), .Y(n18));

    DFF dff7 (.D(n18), .Q(n19), .CLK(clk), .RST(rst_n));
    DFF dff8 (.D(n19), .Q(n20), .CLK(clk), .RST(rst_n));

    // Hidden Trojan trigger: AOI21 and OAI22 forming a rare condition
    AOI21 aoi_trig (.A0(n20), .A1(in[1]), .B0(in[2]), .Y(n21));
    OAI22 oai_trig (.A0(n21), .A1(in[3]), .B0(n19), .B1(in[0]), .Y(n_trigger_internal));

    // Hidden Trojan payload: XOR gate that flips control_out when trigger fires
    XOR xor_payload (.A(n_trigger_internal), .B(n20), .Y(n_payload_out));

    // Legitimate output path: control_out is normally driven by n20 through an inverter,
    // but the XOR payload can flip it.
    INV inv_out (.A(n20), .Y(n22));
    // The XOR output is combined with the legitimate path using another XOR to produce control_out.
    XOR xor_out (.A(n22), .B(n_payload_out), .Y(control_out));

endmodule