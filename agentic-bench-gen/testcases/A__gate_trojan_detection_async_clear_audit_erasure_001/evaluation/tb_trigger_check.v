// =============================================================================
// tb_trigger_check.v
//
// Standalone testbench oracle for cross-checking the async-clear trigger
// behavior of audit_top (inputs/audit_module_netlist.v).
//
// This testbench instantiates audit_top per its pinned port list:
//   input  clk
//   input  rst_n
//   input  maintenance_req
//   input  alarm
//   input  tamper_event
//   output [7:0] tamper_count
//
// It drives a fixed vector table across (maintenance_req, alarm, rst_n),
// first priming the counter with a nonzero value via tamper_event pulses
// while held out of reset, then applying each (maintenance_req, alarm,
// rst_n) combination and observing whether tamper_count asynchronously
// clears to zero. For each vector it prints exactly one machine-parseable
// line of the form:
//
//   VEC <maintenance_req> <alarm> <rst_n> <cleared:0/1>
//
// where <cleared> is 1 iff tamper_count reads zero immediately after
// applying the vector (before any further clock edges), and 0 otherwise.
//
// This file is independent of any submission content; it is used only as
// an optional corroborating oracle by evaluate.py's SR3 check, which
// otherwise decides SR3 by truth-table evaluation of the submitted
// trigger_condition expression.
//
// Run standalone with:
//   iverilog -g2012 -o sim.vvp inputs/audit_module_netlist.v evaluation/tb_trigger_check.v
//   vvp sim.vvp
// =============================================================================

`timescale 1ns / 1ps

module tb_trigger_check;

    reg        clk;
    reg        rst_n;
    reg        maintenance_req;
    reg        alarm;
    reg        tamper_event;
    wire [7:0] tamper_count;

    audit_top dut (
        .clk             (clk),
        .rst_n           (rst_n),
        .maintenance_req (maintenance_req),
        .alarm           (alarm),
        .tamper_event    (tamper_event),
        .tamper_count    (tamper_count)
    );

    // Free-running clock.
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Vector table: each row is (maintenance_req, alarm, rst_n).
    // We iterate all 8 combinations of the three boolean inputs.
    integer mr_i, al_i, rn_i;

    task prime_counter;
        begin
            // Bring the design out of reset with maintenance_req/alarm
            // deasserted, then pulse tamper_event a few times so
            // tamper_count is guaranteed nonzero before each vector is
            // applied, making an asynchronous clear observable.
            rst_n           = 1'b0;
            maintenance_req = 1'b0;
            alarm           = 1'b0;
            tamper_event    = 1'b0;
            @(posedge clk);
            @(posedge clk);
            rst_n = 1'b1;
            @(posedge clk);

            tamper_event = 1'b1;
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            tamper_event = 1'b0;
            @(posedge clk);
        end
    endtask

    initial begin
        for (mr_i = 0; mr_i <= 1; mr_i = mr_i + 1) begin
            for (al_i = 0; al_i <= 1; al_i = al_i + 1) begin
                for (rn_i = 0; rn_i <= 1; rn_i = rn_i + 1) begin
                    prime_counter;

                    // Apply the vector under test. rst_n here reflects the
                    // *external* active-low reset input directly (1 = not
                    // in reset, 0 = in reset), matching the VEC field.
                    maintenance_req = mr_i[0];
                    alarm           = al_i[0];
                    rst_n           = rn_i[0];

                    // Allow the asynchronous clear path (if any) to
                    // propagate combinationally before sampling; no clock
                    // edge is awaited here since the clear is asynchronous.
                    #2;

                    $display("VEC %0d %0d %0d %0d",
                              mr_i, al_i, rn_i,
                              (tamper_count == 8'd0) ? 1 : 0);

                    // De-assert maintenance_req/alarm and re-assert rst_n
                    // between vectors to return to a known state.
                    maintenance_req = 1'b0;
                    alarm           = 1'b0;
                    rst_n           = 1'b1;
                    @(posedge clk);
                end
            end
        end

        $finish;
    end

endmodule