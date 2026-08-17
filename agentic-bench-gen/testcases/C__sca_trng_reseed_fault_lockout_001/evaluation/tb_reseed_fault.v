// -----------------------------------------------------------------------------
// tb_reseed_fault.v
//
// Optional corroboration testbench for the entropy_ready-held-low reseed
// fault scenario. Instantiates the DUT per the pinned public interface,
// drives reset, then holds entropy_ready low while asserting reseed_req for
// two cycles, and reports the resulting internal seed_reg value (via a
// hierarchical reference, since seed_reg is not a port) along with rand_out.
//
// evaluate.py parses the printed SEED_REG=0x%08x line and compares it
// against a constant it independently extracts from inputs/trng_postproc.v;
// no expected value is hardcoded here.
// -----------------------------------------------------------------------------

`timescale 1ns/1ps

module tb_reseed_fault;

    reg         clk;
    reg         rst_n;
    reg         entropy_ready;
    reg  [31:0] entropy_in;
    reg         reseed_req;
    wire [31:0] rand_out;
    wire        seed_valid;

    // Instantiate DUT per pinned interface names.
    trng_postproc dut (
        .clk           (clk),
        .rst_n         (rst_n),
        .entropy_ready (entropy_ready),
        .entropy_in    (entropy_in),
        .reseed_req    (reseed_req),
        .rand_out      (rand_out),
        .seed_valid    (seed_valid)
    );

    // Clock generation: 10ns period.
    initial clk = 1'b0;
    always #5 clk = ~clk;

    initial begin
        // Initialize inputs.
        rst_n         = 1'b0;
        entropy_ready = 1'b0;
        entropy_in    = 32'hA5A5A5A5; // irrelevant while entropy_ready is low
        reseed_req    = 1'b0;

        // Hold reset for 2 rising edges.
        @(posedge clk);
        @(posedge clk);

        // Release reset.
        rst_n = 1'b1;
        @(posedge clk);

        // Assert reseed_req while entropy_ready remains low, for 2 cycles.
        entropy_ready = 1'b0;
        entropy_in    = 32'hA5A5A5A5;
        reseed_req    = 1'b1;

        @(posedge clk); // first reseed edge with entropy_ready low
        @(posedge clk); // second reseed edge with entropy_ready still low

        // Deassert reseed_req.
        reseed_req = 1'b0;

        // Allow one more edge for any registered outputs (e.g. rand_out) to
        // settle based on the newly loaded seed_reg.
        @(posedge clk);

        // Small settle delay before sampling hierarchical signal / outputs.
        #1;

        $display("SEED_REG=0x%08x", dut.seed_reg);
        $display("RAND_OUT=0x%08x", rand_out);

        $finish;
    end

    // Safety timeout in case of a stuck simulation.
    initial begin
        #10000;
        $display("SEED_REG=0xdeadbeef");
        $display("RAND_OUT=0x00000000");
        $display("TIMEOUT: simulation did not complete in expected time");
        $finish;
    end

endmodule