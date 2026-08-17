// tb_skip.v
//
// Testbench that cross-simulates mode_sequencer.v under a single-step
// instruction-skip fault. The fault is modeled by forcing priv_reg to hold
// its previous value (suppressing the write) for exactly the one clock
// edge on which the FSM is in the targeted state (state == SKIP code),
// while leaving the state-sequencing logic completely untouched.
//
// Usage:
//   vvp sim.vvp +SKIP=<state_code>
//
// State encoding (from design_brief.md):
//   IDLE=0, CHECK=1, DEMOTE=2, SETTLE=3, DONE=4,
//   PCHECK=5, PROMOTE=6, PSETTLE=7, PDONE=8
//
// If +SKIP is not provided, defaults to -1 (no skip), i.e. a fault-free
// baseline run.
//
// Prints:
//   FINAL_PRIV=<2-bit binary>
//   DONE_SEEN=1   (only if 'done' was observed asserted during the run)

`timescale 1ns/1ps

module tb_skip;

    reg clk;
    reg rst_n;
    reg req_demote;
    reg req_promote;
    wire [1:0] priv_reg;
    wire [3:0] state;
    wire done;

    integer skip_code;
    integer got_skip;
    reg done_seen;
    reg have_forced_this_pass;

    mode_sequencer dut (
        .clk(clk),
        .rst_n(rst_n),
        .req_demote(req_demote),
        .req_promote(req_promote),
        .priv_reg(priv_reg),
        .state(state),
        .done(done)
    );

    // Clock generation: 10ns period
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Watch for 'done' assertion
    always @(posedge clk) begin
        if (done)
            done_seen = 1'b1;
    end

    // Fault injection: on the clock edge where the FSM currently occupies
    // the targeted skip state, force priv_reg to retain its pre-edge value
    // (suppressing whatever write that state's cycle would otherwise
    // perform), then release the force immediately afterward so that all
    // other sequencing/registers proceed completely normally.
    reg [1:0] pre_edge_priv;

    always @(posedge clk) begin
        pre_edge_priv = priv_reg;
    end

    always @(negedge clk) begin
        if (!have_forced_this_pass && skip_code >= 0 && state == skip_code[3:0]) begin
            // We are currently in the targeted state; suppress the write
            // that would occur on the upcoming posedge by forcing priv_reg
            // to hold its current (pre-edge) value across that edge.
            force dut.priv_reg = pre_edge_priv;
            have_forced_this_pass = 1'b1;
            #1;
            // Wait past the next posedge (where the write would have been
            // suppressed), then release the force so subsequent states'
            // writes proceed normally.
            @(posedge clk);
            #1;
            release dut.priv_reg;
        end
    end

    initial begin
        // Read the +SKIP=<n> plusarg; default to -1 (no skip / fault-free
        // baseline run) if not provided.
        if (!$value$plusargs("SKIP=%d", skip_code)) begin
            skip_code = -1;
        end

        got_skip = skip_code;
        done_seen = 1'b0;
        have_forced_this_pass = 1'b0;

        req_demote = 1'b0;
        req_promote = 1'b0;
        rst_n = 1'b0;

        // Apply async reset for a couple of cycles.
        @(negedge clk);
        @(negedge clk);
        rst_n = 1'b1;
        @(negedge clk);

        // Assert req_demote for one cycle to kick off the demotion
        // sequence (IDLE -> CHECK -> DEMOTE -> SETTLE -> DONE -> IDLE).
        req_demote = 1'b1;
        @(negedge clk);
        req_demote = 1'b0;

        // Run for enough cycles to complete the full demotion sequence
        // and observe 'done'.
        repeat (20) @(negedge clk);

        $display("FINAL_PRIV=%b", priv_reg);
        if (done_seen)
            $display("DONE_SEEN=1");
        else
            $display("DONE_SEEN=0");

        $finish;
    end

    // Safety timeout in case something hangs.
    initial begin
        #2000;
        $display("FINAL_PRIV=%b", priv_reg);
        $display("DONE_SEEN=0");
        $finish;
    end

endmodule