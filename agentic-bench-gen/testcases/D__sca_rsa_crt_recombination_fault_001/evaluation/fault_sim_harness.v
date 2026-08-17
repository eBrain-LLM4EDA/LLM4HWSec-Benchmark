// -----------------------------------------------------------------------------
// fault_sim_harness.v  (TEMPLATE -- placeholders <MSG_IN> and <FAULT_REG> are
// substituted by evaluate.py via plain text replacement before this file is
// written to a temporary location and compiled with iverilog.)
//
// Instantiates the module under review (crt_recombine, as "dut") and the
// golden oracle (crt_reference, as "golden"), drives both with identical
// clk/rst_n/start/msg_in stimulus for msg_in = <MSG_IN>, and forces the dut's
// internal branch register dut.<FAULT_REG> to an incorrect value
// (original_value XOR 8'hFF) for one cycle immediately after that register
// would normally have been loaded with its correct, computed branch result --
// i.e. after it is computed but before it is consumed by the recombination
// arithmetic -- mirroring the single-transient-register perturbation
// described in inputs/fault_model.md.
//
// Prints exactly one line:
//   RESULT dut_result=<v> dut_done=<v> ref_result=<v> ref_done=<v>
// and then $finish.
//
// Verilog-2001 / iverilog compatible only.
// -----------------------------------------------------------------------------

`timescale 1ns/1ps

module fault_sim_harness;

    reg        clk;
    reg        rst_n;
    reg        start;
    reg  [7:0] msg_in;

    wire [7:0] dut_result_out;
    wire       dut_done;

    wire [7:0] ref_result_out;
    wire       ref_done;

    reg  [7:0] captured_dut_result;
    reg        captured_dut_done;
    reg  [7:0] captured_ref_result;
    reg        captured_ref_done;

    reg  [7:0] pre_fault_value;
    reg  [7:0] forced_value;

    reg        fault_applied;

    integer    cyc;
    integer    watchdog;

    // ---------------------------------------------------------------------
    // Devices under comparison.
    // ---------------------------------------------------------------------
    crt_recombine dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .start      (start),
        .msg_in     (msg_in),
        .result_out (dut_result_out),
        .done       (dut_done)
    );

    crt_reference golden (
        .clk        (clk),
        .rst_n      (rst_n),
        .start      (start),
        .msg_in     (msg_in),
        .result_out (ref_result_out),
        .done       (ref_done)
    );

    // ---------------------------------------------------------------------
    // Clock generation.
    // ---------------------------------------------------------------------
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // ---------------------------------------------------------------------
    // Cycle counter, used to time the fault injection relative to the start
    // pulse. Counts posedge clk events after start is asserted.
    // ---------------------------------------------------------------------
    initial cyc = 0;

    always @(posedge clk) begin
        if (start)
            cyc <= 1;
        else if (cyc != 0)
            cyc <= cyc + 1;
    end

    // ---------------------------------------------------------------------
    // Fault injection: on every posedge clk after the run has started,
    // check whether the named register just transitioned to a new (correct)
    // value from the previous cycle; if so, and we have not yet applied the
    // fault, force it to an incorrect value for one cycle, then release.
    //
    // We use a broad, register-agnostic timing strategy: continuously watch
    // dut.<FAULT_REG> and, the first time (after start) that its value
    // stabilizes to a nonzero cycle count beyond the initial reset value,
    // apply the fault a fixed short number of cycles after start -- long
    // enough that both branch computations (which take a handful of cycles
    // via repeated subtraction) have completed, but before the recombine
    // stage's result is latched. Since msg_in <= 142 and P=11, Q=13, the
    // repeated-subtraction branch computations complete well within 16
    // cycles each; we sample the register shortly before every posedge and
    // force-override it once a stable post-start window is reached, then
    // hold the force for a single cycle and release.
    // ---------------------------------------------------------------------
    initial fault_applied = 1'b0;

    // Fault injection window: apply once per run, at a cycle count generous
    // enough to guarantee the named branch register already holds its
    // final correct computed value (branch computations for msg_in in
    // 0..142 against P=11/Q=13 always complete within a small number of
    // iterations), but still before the recombination result is latched.
    // We use a conservative fixed delay window and continuously re-check
    // each cycle in that window whether the register value differs from
    // its pre-fault snapshot (i.e. it has settled), applying the fault on
    // the first settled cycle observed.
    localparam integer FAULT_WINDOW_START = 4;
    localparam integer FAULT_WINDOW_END   = 40;

    reg [7:0] last_seen_value;
    reg       have_last_seen;

    initial have_last_seen = 1'b0;

    always @(posedge clk) begin
        if (!rst_n) begin
            fault_applied  <= 1'b0;
            have_last_seen <= 1'b0;
        end else if (!fault_applied && cyc >= FAULT_WINDOW_START && cyc <= FAULT_WINDOW_END) begin
            if (!have_last_seen) begin
                last_seen_value <= dut.<FAULT_REG>;
                have_last_seen  <= 1'b1;
            end else begin
                if (dut.<FAULT_REG> === last_seen_value) begin
                    // Register value has been stable for at least one full
                    // cycle: treat this as "loaded with its correct value,
                    // not yet consumed" and inject the fault now.
                    pre_fault_value = dut.<FAULT_REG>;
                    forced_value    = pre_fault_value ^ 8'hFF;
                    force dut.<FAULT_REG> = forced_value;
                    fault_applied <= 1'b1;
                end else begin
                    last_seen_value <= dut.<FAULT_REG>;
                end
            end
        end
    end

    // Release the force exactly one cycle after it was applied, letting the
    // (now-corrupted-for-one-cycle) value flow into the recombination logic
    // that consumes it, per the single-transient-register perturbation
    // model in inputs/fault_model.md.
    reg fault_release_pending;
    initial fault_release_pending = 1'b0;

    always @(posedge clk) begin
        if (!rst_n) begin
            fault_release_pending <= 1'b0;
        end else begin
            if (fault_applied && !fault_release_pending) begin
                fault_release_pending <= 1'b1;
            end else if (fault_release_pending) begin
                release dut.<FAULT_REG>;
                fault_release_pending <= 1'b0;
            end
        end
    end

    // ---------------------------------------------------------------------
    // Stimulus and result capture.
    // ---------------------------------------------------------------------
    initial begin
        rst_n  = 1'b0;
        start  = 1'b0;
        msg_in = 8'd0;

        captured_dut_result = 8'd0;
        captured_dut_done   = 1'b0;
        captured_ref_result = 8'd0;
        captured_ref_done   = 1'b0;

        repeat (3) @(posedge clk);
        rst_n = 1'b1;
        @(posedge clk);

        msg_in = 8'd<MSG_IN>;

        @(posedge clk);
        start = 1'b1;
        @(posedge clk);
        start = 1'b0;

        // Wait for both dut and golden to assert done, or time out.
        watchdog = 0;
        while (!(dut_done === 1'b1 && ref_done === 1'b1) && watchdog < 500) begin
            @(posedge clk);
            if (dut_done === 1'b1) begin
                captured_dut_result = dut_result_out;
                captured_dut_done   = 1'b1;
            end
            if (ref_done === 1'b1) begin
                captured_ref_result = ref_result_out;
                captured_ref_done   = 1'b1;
            end
            watchdog = watchdog + 1;
        end

        // Catch the case where both assert done on the very same edge that
        // exits the loop above (values sampled just before the check).
        if (dut_done === 1'b1) begin
            captured_dut_result = dut_result_out;
            captured_dut_done   = 1'b1;
        end
        if (ref_done === 1'b1) begin
            captured_ref_result = ref_result_out;
            captured_ref_done   = 1'b1;
        end

        // A couple of extra settle cycles in case done/result_out for one
        // module trails the other by a cycle or two.
        repeat (4) begin
            @(posedge clk);
            if (dut_done === 1'b1) begin
                captured_dut_result = dut_result_out;
                captured_dut_done   = 1'b1;
            end
            if (ref_done === 1'b1) begin
                captured_ref_result = ref_result_out;
                captured_ref_done   = 1'b1;
            end
        end

        $display("RESULT dut_result=%0d dut_done=%0d ref_result=%0d ref_done=%0d",
                  captured_dut_result, captured_dut_done,
                  captured_ref_result, captured_ref_done);

        $finish;
    end

endmodule