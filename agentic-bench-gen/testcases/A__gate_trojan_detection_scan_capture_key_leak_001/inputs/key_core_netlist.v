// =============================================================
// key_core_netlist.v
//
// Small structural (gate-level) netlist for a key-storage core
// with an integrated manufacturing-test scan chain.
//
// Primitive cell library (DFF, MUX2, AND2, OR2, NOT) is defined
// locally below so this file elaborates standalone.
// =============================================================

// -------------------------------------------------------------
// Primitive cell library
// -------------------------------------------------------------

module DFF (
    input  wire clk,
    input  wire rst_n,
    input  wire d,
    output reg  q
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q <= 1'b0;
        else
            q <= d;
    end
endmodule

module MUX2 (
    input  wire a,    // select = 0
    input  wire b,    // select = 1
    input  wire sel,
    output wire y
);
    assign y = sel ? b : a;
endmodule

module AND2 (
    input  wire a,
    input  wire b,
    output wire y
);
    assign y = a & b;
endmodule

module OR2 (
    input  wire a,
    input  wire b,
    output wire y
);
    assign y = a | b;
endmodule

module NOT (
    input  wire a,
    output wire y
);
    assign y = ~a;
endmodule

// -------------------------------------------------------------
// key_core
//
// Ports:
//   clk, rst_n     - clock / async active-low reset
//   scan_en        - 1 = scan shift mode, 0 = functional mode
//   scan_in        - scan chain serial input
//   scan_out       - scan chain serial output
//   load_key       - functional load enable for the key register
//   key_in         - 4-bit key input, loaded into key_ff0..key_ff3
//   data_valid     - functional data-valid input driving status flops
//   status_out     - functional status output (from status flops)
//
// Internal structure:
//   - u_ff_stat0..u_ff_stat3 : ordinary pipeline/status flops,
//     each preceded by a MUX2 selecting between its functional D
//     input and the previous scan-chain element's Q (scan shift),
//     chained together to form the visible scan path.
//   - key_ff0..key_ff3       : key storage flops, loaded from
//     key_in on load_key. Functionally these only feed
//     status/output logic, not the scan chain.
//   - u_smux_key0..u_smux_key3 : additional MUX2 instances spliced
//     into the scan chain between status flops. Each selects, on
//     scan_en, between the previous chain element's output and the
//     corresponding key flop's Q output, and its output feeds the
//     D input of the next scan-chain flop.
// -------------------------------------------------------------

module key_core (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       scan_en,
    input  wire       scan_in,
    output wire       scan_out,
    input  wire       load_key,
    input  wire [3:0] key_in,
    input  wire       data_valid,
    output wire       status_out
);

    // -----------------------------------------------------------
    // Functional D-inputs for the four status/pipeline flops.
    // Simple combinational status pipeline for illustration.
    // -----------------------------------------------------------
    wire func_d_stat0;
    wire func_d_stat1;
    wire func_d_stat2;
    wire func_d_stat3;

    AND2 u_and_stat0 (.a(data_valid), .b(rst_n), .y(func_d_stat0));

    wire q_stat0;
    NOT  u_not_stat1  (.a(q_stat0), .y(func_d_stat1));

    wire q_stat1;
    OR2  u_or_stat2   (.a(q_stat1), .b(data_valid), .y(func_d_stat2));

    wire q_stat2;
    AND2 u_and_stat3  (.a(q_stat2), .b(data_valid), .y(func_d_stat3));

    // -----------------------------------------------------------
    // Key register: loaded from key_in on load_key. Functionally
    // isolated -- only feeds internal status logic, never a
    // directly observable functional output on its own.
    // -----------------------------------------------------------
    wire key_d0, key_d1, key_d2, key_d3;
    wire q_key0, q_key1, q_key2, q_key3;

    MUX2 u_kmux0 (.a(q_key0), .b(key_in[0]), .sel(load_key), .y(key_d0));
    MUX2 u_kmux1 (.a(q_key1), .b(key_in[1]), .sel(load_key), .y(key_d1));
    MUX2 u_kmux2 (.a(q_key2), .b(key_in[2]), .sel(load_key), .y(key_d2));
    MUX2 u_kmux3 (.a(q_key3), .b(key_in[3]), .sel(load_key), .y(key_d3));

    DFF key_ff0 (.clk(clk), .rst_n(rst_n), .d(key_d0), .q(q_key0));
    DFF key_ff1 (.clk(clk), .rst_n(rst_n), .d(key_d1), .q(q_key1));
    DFF key_ff2 (.clk(clk), .rst_n(rst_n), .d(key_d2), .q(q_key2));
    DFF key_ff3 (.clk(clk), .rst_n(rst_n), .d(key_d3), .q(q_key3));

    // -----------------------------------------------------------
    // Scan chain wiring.
    //
    // Intended structure: scan_in -> stat0 -> stat1 -> stat2 ->
    // stat3 -> scan_out, with each status flop's scan-mode D input
    // selected by scan_en between its functional D and the
    // previous chain element's Q.
    //
    // Splice muxes u_smux_key0..u_smux_key3 are inserted between
    // the status flops. Each one is selected by scan_en and picks
    // between the previous chain element's Q (normal shift) and
    // the corresponding key flop's Q (key_ff0..key_ff3), feeding
    // its output into the D input of the next status flop's scan
    // mux. This routes the key flops onto the shift path whenever
    // scan_en is asserted.
    // -----------------------------------------------------------

    // stat0: first element in the chain, fed from scan_in.
    wire scanmux_d_stat0;
    MUX2 u_smux_stat0 (.a(func_d_stat0), .b(scan_in), .sel(scan_en), .y(scanmux_d_stat0));
    DFF  u_ff_stat0    (.clk(clk), .rst_n(rst_n), .d(scanmux_d_stat0), .q(q_stat0));

    // Splice key_ff0 between stat0 and stat1.
    wire spliced0;
    MUX2 u_smux_key0 (.a(q_stat0), .b(q_key0), .sel(scan_en), .y(spliced0));

    wire scanmux_d_stat1;
    MUX2 u_smux_stat1 (.a(func_d_stat1), .b(spliced0), .sel(scan_en), .y(scanmux_d_stat1));
    DFF  u_ff_stat1    (.clk(clk), .rst_n(rst_n), .d(scanmux_d_stat1), .q(q_stat1));

    // Splice key_ff1 between stat1 and stat2.
    wire spliced1;
    MUX2 u_smux_key1 (.a(q_stat1), .b(q_key1), .sel(scan_en), .y(spliced1));

    wire scanmux_d_stat2;
    MUX2 u_smux_stat2 (.a(func_d_stat2), .b(spliced1), .sel(scan_en), .y(scanmux_d_stat2));
    DFF  u_ff_stat2    (.clk(clk), .rst_n(rst_n), .d(scanmux_d_stat2), .q(q_stat2));

    // Splice key_ff2 between stat2 and stat3.
    wire spliced2;
    MUX2 u_smux_key2 (.a(q_stat2), .b(q_key2), .sel(scan_en), .y(spliced2));

    wire scanmux_d_stat3;
    MUX2 u_smux_stat3 (.a(func_d_stat3), .b(spliced2), .sel(scan_en), .y(scanmux_d_stat3));
    wire q_stat3;
    DFF  u_ff_stat3    (.clk(clk), .rst_n(rst_n), .d(scanmux_d_stat3), .q(q_stat3));

    // Splice key_ff3 after stat3, immediately before scan_out.
    wire spliced3;
    MUX2 u_smux_key3 (.a(q_stat3), .b(q_key3), .sel(scan_en), .y(spliced3));

    // Final scan chain output.
    assign scan_out = spliced3;

    // -----------------------------------------------------------
    // Functional status output: derived from the status flop
    // pipeline only.
    // -----------------------------------------------------------
    OR2 u_or_status_out (.a(q_stat3), .b(q_stat1), .y(status_out));

endmodule