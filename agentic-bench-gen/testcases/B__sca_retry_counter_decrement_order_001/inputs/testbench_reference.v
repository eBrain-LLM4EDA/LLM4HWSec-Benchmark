//----------------------------------------------------------------------------
// testbench_reference.v
//
// Reference fault-free testbench for pin_check_fsm.
//
// Exercises the documented 3-attempt lockout policy with no fault
// injection: three consecutive incorrect PIN guesses followed by one
// correct-PIN guess after lockout, observing that lockout suppresses
// auth_ok even for a correct PIN.
//
// This testbench only reports observations via $display/$monitor; it
// does not use $stop/$finish-on-mismatch assertions, so it can be run
// unmodified against any RTL variant that preserves the documented
// port list and fault-free behavior.
//
// Port order instantiated below matches pin_check_fsm.v exactly:
//   pin_check_fsm(
//       .clk(clk),
//       .rst_n(rst_n),
//       .pin_in(pin_in),
//       .pin_valid(pin_valid),
//       .auth_ok(auth_ok),
//       .locked_out(locked_out),
//       .attempts_left(attempts_left)
//   );
//----------------------------------------------------------------------------

`timescale 1ns/1ps

module testbench_reference;

    reg        clk;
    reg        rst_n;
    reg [7:0]  pin_in;
    reg        pin_valid;
    wire       auth_ok;
    wire       locked_out;
    wire [3:0] attempts_left;

    // Device under test. Port order matches pin_check_fsm.v declaration.
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

    // Continuous observation log.
    always @(posedge clk) begin
        $display("t=%0t state_visible: attempts_left=%0d locked_out=%0b auth_ok=%0b pin_valid=%0b pin_in=%02h",
                  $time, attempts_left, locked_out, auth_ok, pin_valid, pin_in);
    end

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

        $display("---- Reset released. Expect attempts_left == 3 ----");

        // Attempt #1: incorrect PIN (secret is 8'hA5 per design brief; use
        // a value guaranteed incorrect for the documented device).
        $display("---- Attempt 1: incorrect PIN ----");
        present_pin(8'h11);

        // Allow the comparison/bookkeeping to fully settle before the
        // next strobe (a few idle cycles).
        repeat (4) @(posedge clk);
        $display("---- After attempt 1: expect attempts_left == 2 ----");

        // Attempt #2: incorrect PIN.
        $display("---- Attempt 2: incorrect PIN ----");
        present_pin(8'h22);
        repeat (4) @(posedge clk);
        $display("---- After attempt 2: expect attempts_left == 1 ----");

        // Attempt #3: incorrect PIN. This should exhaust the retry budget
        // and assert locked_out.
        $display("---- Attempt 3: incorrect PIN ----");
        present_pin(8'h33);
        repeat (4) @(posedge clk);
        $display("---- After attempt 3: expect attempts_left == 0, locked_out == 1 ----");

        // Attempt #4: correct PIN presented after lockout. auth_ok must
        // remain 0 because the device is locked out.
        $display("---- Attempt 4: correct PIN, but device should be locked out ----");
        present_pin(8'hA5);
        repeat (4) @(posedge clk);
        $display("---- After attempt 4: expect auth_ok == 0 (locked_out == 1 held) ----");

        // Hold a bit longer to confirm locked_out remains asserted.
        repeat (10) @(posedge clk);
        $display("---- Final check: expect locked_out == 1 still held ----");

        $display("---- Simulation complete ----");
        $finish;
    end

endmodule