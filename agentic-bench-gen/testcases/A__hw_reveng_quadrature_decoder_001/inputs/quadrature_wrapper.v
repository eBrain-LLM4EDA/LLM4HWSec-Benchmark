// =============================================================================
// quadrature_wrapper.v
//
// REFERENCE-ONLY. Do not modify. Do not submit this file.
//
// Obfuscated integration wrapper showing how the flattened gate-level
// netlist (quad_decoder_gates, see quadrature_netlist.v) plugs into a
// clk/rst/a/b/pos/dir/invalid-shaped boundary inside the larger harness.
// Signal names here are deliberately obscured/renamed and this module's
// port list is NOT the pinned interface -- it exists only to demonstrate
// integration context. Recovering the intended word-level behavior (not
// merely renaming these ports) is the actual task; see README.md and
// metadata.json for the pinned `quad_decoder` interface you must submit.
// =============================================================================

`timescale 1ns/1ps

module quad_decoder_wrapper (
    input  wire       sysClk,
    input  wire       sysRst,
    input  wire       netA,
    input  wire       netB,
    output wire [7:0] q0,
    output wire       q1,
    output wire       q2
);

    // Pure pass-through wiring into the flattened gate-level core.
    // No additional logic is added at this boundary.
    wire [7:0] core_pos;
    wire       core_dir;
    wire       core_invalid;

    quad_decoder_gates core_inst (
        .clk         (sysClk),
        .rst         (sysRst),
        .a           (netA),
        .b           (netB),
        .pos_out     (core_pos),
        .dir_out     (core_dir),
        .invalid_out (core_invalid)
    );

    assign q0 = core_pos;
    assign q1 = core_dir;
    assign q2 = core_invalid;

endmodule