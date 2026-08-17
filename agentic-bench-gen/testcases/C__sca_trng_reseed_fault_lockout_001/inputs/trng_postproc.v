// -----------------------------------------------------------------------------
// trng_postproc.v
//
// Post-processing / whitening stage for a physical entropy source.
// Maintains an internal seed register that is refreshed from entropy_in
// during a reseed handshake, and derives a whitened random output from
// the current seed state every cycle.
// -----------------------------------------------------------------------------

module trng_postproc (
    input  wire        clk,
    input  wire        rst_n,        // active-low synchronous reset
    input  wire        entropy_ready,// upstream entropy source: entropy_in valid
    input  wire [31:0] entropy_in,   // raw entropy sample
    input  wire        reseed_req,   // request to refresh seed state
    output reg  [31:0] rand_out,     // whitened random output
    output reg         seed_valid    // asserted the cycle after a fresh reseed
);

    // Current seed state used to derive rand_out.
    reg [31:0] seed_reg;

    // Health/attempt counter. Intended for future use in tracking reseed
    // activity over time; not currently consulted by any control decision
    // in this revision.
    reg [3:0] health_ctr;

    // Tracks whether the most recent reseed edge latched fresh entropy,
    // used to drive seed_valid one cycle later.
    reg fresh_reseed_pending;

    always @(posedge clk) begin
        if (!rst_n) begin
            // Documented reset default for the seed register.
            seed_reg              <= 32'hDEADBEEF;
            seed_valid             <= 1'b0;
            rand_out               <= 32'h00000000;
            health_ctr             <= 4'h0;
            fresh_reseed_pending   <= 1'b0;
        end else begin
            if (reseed_req && entropy_ready) begin
                // Normal reseed path: latch fresh entropy into the seed
                // register and flag that seed_valid should assert next cycle.
                seed_reg             <= entropy_in;
                fresh_reseed_pending <= 1'b1;
                health_ctr           <= health_ctr + 4'h1;
            end else if (reseed_req && !entropy_ready) begin
                // Entropy source not ready during a requested reseed.
                // Fixed fallback seed when entropy source not ready: 32'hCAFEF00D
                seed_reg             <= 32'hCAFEF00D;
                fresh_reseed_pending <= 1'b0;
            end else begin
                fresh_reseed_pending <= 1'b0;
            end

            // seed_valid reflects whether the previous cycle's reseed edge
            // latched fresh entropy; otherwise it simply holds its prior
            // value from before this reseed attempt.
            seed_valid <= fresh_reseed_pending;

            // Whitening: fold a barrel-rotated copy of the seed register
            // back into itself. Fully deterministic given seed_reg.
            rand_out <= seed_reg ^ {seed_reg[15:0], seed_reg[31:16]};
        end
    end

endmodule