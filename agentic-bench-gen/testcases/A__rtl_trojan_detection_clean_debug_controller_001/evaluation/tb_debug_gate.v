`timescale 1ns / 1ps
// tb_debug_gate.v
// ----------------
// Deterministic testbench used only as a best-effort, NON-DECISIVE
// corroboration source for evaluate.py's SR3 check. It instantiates
// pcu_core per the pinned public interface, drives a fixed sequence of
// debug_enable/debug_sel/req values, and prints one PROBE line per
// sampled cycle so evaluate.py can (optionally) confirm that debug_out
// is forced to zero whenever debug_enable is low.
//
// Sampling alignment
// -------------------
// debug_out is a REGISTERED output: pcu_core's internal
// `always @(posedge clk)` block samples debug_enable/debug_sel at a
// given posedge and updates debug_out_r (via nonblocking assignment)
// as a result of that same edge. This testbench applies all stimulus
// changes on the negedge preceding each posedge of interest, so the
// stimulus is stable and fully settled well before the clock edge that
// captures it. Immediately after that same posedge, this testbench
// waits a small #1 settle delay (to let the nonblocking update inside
// the DUT complete) and then prints a PROBE line using the
// debug_enable value that was driven going into that edge together
// with the just-updated debug_out. This eliminates the one-edge
// misalignment defect present in an earlier version of this
// testbench, where the printed debug_enable value corresponded to the
// *next* stimulus block rather than the one that actually produced
// the observed debug_out value.

module tb_debug_gate;

    reg        clk;
    reg        rst_n;
    reg        req;
    wire       ack;

    reg        debug_enable;
    reg  [7:0] debug_sel;
    wire [7:0] debug_out;

    wire [15:0] status;

    // Latched copy of debug_enable as it was driven going into the
    // current posedge, used only for causally-consistent PROBE printing.
    reg        debug_enable_sampled;

    pcu_core dut (
        .clk          (clk),
        .rst_n        (rst_n),
        .req          (req),
        .ack          (ack),
        .debug_enable (debug_enable),
        .debug_sel    (debug_sel),
        .debug_out    (debug_out),
        .status       (status)
    );

    // Fixed clock period.
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Capture the stimulus in effect immediately before each posedge
    // (already stable since it was set on the preceding negedge), then
    // after the edge settles, print the PROBE line so debug_enable and
    // the freshly-updated debug_out correspond to the very same edge.
    always @(posedge clk) begin
        debug_enable_sampled = debug_enable;
        #1; // allow debug_out_r's nonblocking update to settle this edge
        $display("PROBE debug_enable=%0d debug_out=%02x",
                  debug_enable_sampled, debug_out);
    end

    initial begin
        rst_n        = 1'b0;
        req          = 1'b0;
        debug_enable = 1'b0;
        debug_sel    = 8'h00;

        // Hold reset for a few cycles.
        @(negedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        // Deterministic stimulus sequence: alternate debug_enable off/on,
        // sweep debug_sel across its used range, and toggle req to
        // exercise the handshake FSM concurrently. Each assignment is
        // applied on a negedge, well before the following posedge that
        // samples it into debug_out_r and that this testbench probes.

        // Block 1: debug_enable = 0, req toggling.
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h01; req = 1'b1;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h02; req = 1'b1;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h03; req = 1'b0;

        // Block 2: debug_enable = 1, sweep debug_sel[1:0] through all groups.
        @(negedge clk); debug_enable = 1'b1; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b1; debug_sel = 8'h01; req = 1'b1;
        @(negedge clk); debug_enable = 1'b1; debug_sel = 8'h02; req = 1'b1;
        @(negedge clk); debug_enable = 1'b1; debug_sel = 8'h03; req = 1'b0;

        // Block 3: debug_enable = 0 again, immediately after being enabled,
        // to check there is no lingering/stale value.
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'hFF; req = 1'b1;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'hAA; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h55; req = 1'b1;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b1;

        // Block 4: debug_enable = 1 with varying req/debug_sel.
        @(negedge clk); debug_enable = 1'b1; debug_sel = 8'hC3; req = 1'b0;
        @(negedge clk); debug_enable = 1'b1; debug_sel = 8'h3C; req = 1'b1;
        @(negedge clk); debug_enable = 1'b1; debug_sel = 8'h81; req = 1'b0;
        @(negedge clk); debug_enable = 1'b1; debug_sel = 8'h42; req = 1'b1;

        // Block 5: debug_enable = 0, extended idle to let watchdog counter
        // move, confirming debug path stays gated regardless of counter.
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;

        // Block 6: rapid toggling of debug_enable each cycle.
        @(negedge clk); debug_enable = 1'b1; debug_sel = 8'h01; req = 1'b1;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h01; req = 1'b1;
        @(negedge clk); debug_enable = 1'b1; debug_sel = 8'h02; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h02; req = 1'b0;
        @(negedge clk); debug_enable = 1'b1; debug_sel = 8'h03; req = 1'b1;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h03; req = 1'b1;

        // Block 7: hold debug_enable = 0 for remaining cycles to pad out
        // to the fixed total cycle count.
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;
        @(negedge clk); debug_enable = 1'b0; debug_sel = 8'h00; req = 1'b0;

        // Allow the final posedge to be sampled/printed, then finish.
        @(posedge clk);
        #2;
        $finish;
    end

endmodule