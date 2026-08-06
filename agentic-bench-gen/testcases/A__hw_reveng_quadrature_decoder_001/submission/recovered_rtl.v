// =============================================================================
// submission/recovered_rtl.v
//
// PLACEHOLDER STARTER FILE -- REPLACE THIS ENTIRE FILE WITH YOUR RECOVERED
// DESIGN.
//
// This stub only exists to show the required file location, module name,
// and pinned port list. It does not attempt to track a/b transitions at
// all -- it just holds every output at zero forever. This is NOT a correct
// implementation of the quadrature decoder described in the design brief
// and pinned interface; replace the body below with your real
// reverse-engineered logic.
// =============================================================================

`timescale 1ns/1ps

module quad_decoder (
    input  wire        clk,
    input  wire        rst,
    input  wire         a,
    input  wire         b,
    output reg  signed [7:0] pos,
    output reg          dir,
    output reg          invalid
);

    // Placeholder behavior: outputs are unconditionally held at zero on
    // every clock edge, regardless of rst, a, or b. Replace with the real
    // Gray-code decode logic per the pinned interface specification.
    always @(posedge clk) begin
        pos     <= 8'sd0;
        dir     <= 1'b0;
        invalid <= 1'b0;
    end

endmodule