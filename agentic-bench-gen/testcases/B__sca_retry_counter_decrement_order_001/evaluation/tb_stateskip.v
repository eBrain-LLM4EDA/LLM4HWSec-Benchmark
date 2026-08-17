//----------------------------------------------------------------------------
// tb_stateskip.v
//
// Optional corroboration testbench (informational only).
//
// Instantiates pin_check_fsm and forces the internal state register
// (hierarchical path dut.state) to skip directly from COMPARE (2'd1) to
// IDLE (2'd0) on the cycle following an incorrect PIN submission, mimicking
// a single-event-transient state-skip fault that bypasses CHECK_DONE
// entirely. Reports attempts_left immediately before and after the forced
// skip via a single machine-parseable line:
//
//     STATESKIP attempts_before=<n> attempts_after=<n>
//
// This testbench does NOT gate PASS/FAIL on the submitted report; it is
// used only as best-effort corroboration by evaluate.py. It relies only on
// the pinned public port list of pin_check_fsm and the state encoding
// documented in the RTL (IDLE=2'd0, COMPARE=2'd1, CHECK_DONE=2'd2,
// LOCKOUT=2'd3); if a submitted RTL variant uses a different internal state
// register name/width, this testbench may fail to compile or force
// correctly, which is acceptable since it is purely corroborative and does
// not affect the graded verdicts in evaluate.py.
//----------------------------------------------------------------------------

`timescale 1ns/1ps

module tb_stateskip;

    reg        clk;
    reg        rst_n;
    reg [7:0]  pin_in;
    reg        pin_valid;
    wire       auth_ok;
    wire       locked_out;
    wire [3:0] attempts_left;

    reg [3:0] attempts_before;
    reg [3:0] attempts_after;

    // Device under test. Port order/names match the pinned public interface.
    pin_check_fsm dut (
        .clk           (clk),
        .rst_n         (rst_n),
        .pin_in        (pin_in),
        .pin_valid     (pin_valid),
        .auth_ok       (auth_ok),
        .locked_out    (locked_out),
        .attempts_left (attempts_left)
    );

    // 10ns period clock.
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Presents a candidate PIN for exactly one clock cycle via pin_valid.
    task present_pin(input [7:0] candidate);
        begin
            @(posedge clk);
            pin_in    = candidate;
            pin_valid = 1'b1;
            @(posedge clk);
            pin_valid = 1'b0;
        end
    endtask

    initial begin
        // Initialize
        rst_n     = 1'b0;
        pin_in    = 8'h00;
        pin_valid = 1'b0;

        // Hold reset for a couple of cycles.
        repeat (3) @(posedge clk);
        rst_n = 1'b1;
        @(posedge clk);

        // Record the baseline attempts_left before injecting any fault.
        attempts_before = attempts_left;

        // Present an incorrect PIN. The DUT will move IDLE -> COMPARE on the
        // next edge, latch the (failing) comparison result while in
        // COMPARE, and would normally move COMPARE -> CHECK_DONE (where the
        // decrement happens) on the following edge.
        present_pin(8'h11);

        // Wait one cycle so the DUT is now sitting in COMPARE (comparison
        // in flight / about to be latched).
        @(posedge clk);

        // At this point the DUT should be in COMPARE (dut.state == 2'd1)
        // about to transition into CHECK_DONE on the next edge. Force a
        // single-event-transient state-skip: instead of landing in
        // CHECK_DONE, force the state register directly to IDLE (2'd0),
        // emulating a fault that skips CHECK_DONE (and therefore skips the
        // decrement logic gated on state == CHECK_DONE).
        force dut.state = 2'd0; // IDLE
        @(posedge clk);
        release dut.state;

        // Allow a few idle cycles for any registered outputs to settle.
        repeat (4) @(posedge clk);

        attempts_after = attempts_left;

        $display("STATESKIP attempts_before=%0d attempts_after=%0d",
                  attempts_before, attempts_after);

        $display("---- State-skip corroboration complete ----");
        $finish;
    end

endmodule