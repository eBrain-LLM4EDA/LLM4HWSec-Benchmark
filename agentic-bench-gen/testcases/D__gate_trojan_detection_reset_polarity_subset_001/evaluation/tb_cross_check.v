`timescale 1ns/1ps

// -----------------------------------------------------------------------
// tb_cross_check.v
//
// SR5 corroboration testbench. Instantiates the `top` module using the
// public port names pinned by public_spec.interface (CLK, RSTN, DIN,
// CTRL, DOUT). Drives several cycles of stimulus to move the control and
// datapath flip-flops to a mix of 0/1 values, and deliberately steers the
// privilege/lock-state next-state logic (priv_ff1_d = CTRL[2] | ctrl_ff2_q ;
// priv_ff2_d = CTRL[3] & priv_ff1_q, per gate_netlist.v) to a stable
// logic-1 value before the final pre-reset sample -- then records each
// canonical flip-flop's output value immediately before a reset pulse is
// applied, applies RSTN=0 for two clock edges, then records each flop's
// value again after RSTN is released.
//
// The design_brief (Section 4) pins the canonical role names for every
// state-holding flip-flop instance in this generated netlist:
//   u_ctrl_ff0, u_ctrl_ff1, u_ctrl_ff2, u_ctrl_ff3,
//   u_dp_ff4,   u_dp_ff5,
//   u_priv_ff1, u_priv_ff2
// gate_netlist.v instantiates exactly these instance names underneath the
// `top` module, so this testbench refers to their `.Q` outputs via fixed
// hierarchical references (dut.<name>.Q). This is independent of whatever
// the participant writes in submission/trojan_report.json -- it probes the
// fixed input netlist structure only, and evaluate.py parses the printed
// CROSSCHECK lines to determine, purely from simulation, which flops
// failed to clear to their documented reset value (logic 0) across the
// reset pulse.
// -----------------------------------------------------------------------

module tb_cross_check;

    reg        CLK;
    reg        RSTN;
    reg  [3:0] DIN;
    reg  [3:0] CTRL;
    wire [3:0] DOUT;

    top dut (
        .CLK  (CLK),
        .RSTN (RSTN),
        .DIN  (DIN),
        .CTRL (CTRL),
        .DOUT (DOUT)
    );

    initial CLK = 1'b0;
    always #5 CLK = ~CLK;

    // Pre-reset / post-reset snapshot storage for each canonical flop.
    reg pre_ctrl_ff0, pre_ctrl_ff1, pre_ctrl_ff2, pre_ctrl_ff3;
    reg pre_dp_ff4,   pre_dp_ff5;
    reg pre_priv_ff1, pre_priv_ff2;

    reg post_ctrl_ff0, post_ctrl_ff1, post_ctrl_ff2, post_ctrl_ff3;
    reg post_dp_ff4,   post_dp_ff5;
    reg post_priv_ff1, post_priv_ff2;

    initial begin
        RSTN = 1'b1;
        DIN  = 4'b0000;
        CTRL = 4'b0000;

        // Drive the design through a run-up sequence with varying
        // DIN/CTRL values on successive clock edges so the control and
        // datapath flops settle to a mix of 0/1 values (not all-zero),
        // making their post-reset clearing to 0 a non-trivial, observable
        // transition.
        @(negedge CLK);
        DIN  = 4'b1011;
        CTRL = 4'b1111;
        @(negedge CLK);
        CTRL = 4'b1010;
        DIN  = 4'b0111;
        @(negedge CLK);
        CTRL = 4'b1101;
        DIN  = 4'b1100;
        @(negedge CLK);
        CTRL = 4'b1001;
        DIN  = 4'b0110;
        @(negedge CLK);
        CTRL = 4'b1110;
        DIN  = 4'b1001;
        @(negedge CLK);
        CTRL = 4'b0011;
        DIN  = 4'b1101;
        @(negedge CLK);

        // Deliberately steer the privilege/lock-state chain to logic 1
        // and hold it there for two extra clock edges before sampling, so
        // priv_ff1_d = CTRL[2] | ctrl_ff2_q and priv_ff2_d = CTRL[3] &
        // priv_ff1_q are both driven to 1 and have settled through the
        // flops regardless of whatever transient value ctrl_ff2_q/
        // priv_ff1_q happened to hold from the run-up sequence above.
        // CTRL[2]=1 forces priv_ff1_d=1 unconditionally; once priv_ff1_q
        // becomes 1, CTRL[3]=1 forces priv_ff2_d=1 unconditionally on the
        // following edge. CTRL[0]/CTRL[1] are left toggling so the
        // control-path flops (which depend on CTRL[0..1] and prior
        // ctrl_ff state, not on CTRL[2..3] alone) continue to reflect a
        // mix of 0/1 values rather than being forced uniformly.
        CTRL = 4'b1101; // CTRL[0]=1, CTRL[2]=1, CTRL[3]=1
        DIN  = 4'b1111;
        @(negedge CLK); // priv_ff1_q <= priv_ff1_d (CTRL[2] | ctrl_ff2_q) = 1
        @(negedge CLK); // priv_ff2_q <= priv_ff2_d (CTRL[3] & priv_ff1_q) = 1

        // Snapshot pre-reset values of every canonical flop.
        pre_ctrl_ff0 = dut.u_ctrl_ff0.Q;
        pre_ctrl_ff1 = dut.u_ctrl_ff1.Q;
        pre_ctrl_ff2 = dut.u_ctrl_ff2.Q;
        pre_ctrl_ff3 = dut.u_ctrl_ff3.Q;
        pre_dp_ff4   = dut.u_dp_ff4.Q;
        pre_dp_ff5   = dut.u_dp_ff5.Q;
        pre_priv_ff1 = dut.u_priv_ff1.Q;
        pre_priv_ff2 = dut.u_priv_ff2.Q;

        // Apply the reset pulse for two full clock edges.
        RSTN = 1'b0;
        @(negedge CLK);
        @(negedge CLK);

        // Release reset and settle one more edge before sampling.
        RSTN = 1'b1;
        @(negedge CLK);

        // Snapshot post-reset values of every canonical flop.
        post_ctrl_ff0 = dut.u_ctrl_ff0.Q;
        post_ctrl_ff1 = dut.u_ctrl_ff1.Q;
        post_ctrl_ff2 = dut.u_ctrl_ff2.Q;
        post_ctrl_ff3 = dut.u_ctrl_ff3.Q;
        post_dp_ff4   = dut.u_dp_ff4.Q;
        post_dp_ff5   = dut.u_dp_ff5.Q;
        post_priv_ff1 = dut.u_priv_ff1.Q;
        post_priv_ff2 = dut.u_priv_ff2.Q;

        // Emit one machine-parseable line per canonical flop instance:
        //   CROSSCHECK <flopname>=<preval>,<postval>
        $display("CROSSCHECK u_ctrl_ff0=%0d,%0d", pre_ctrl_ff0, post_ctrl_ff0);
        $display("CROSSCHECK u_ctrl_ff1=%0d,%0d", pre_ctrl_ff1, post_ctrl_ff1);
        $display("CROSSCHECK u_ctrl_ff2=%0d,%0d", pre_ctrl_ff2, post_ctrl_ff2);
        $display("CROSSCHECK u_ctrl_ff3=%0d,%0d", pre_ctrl_ff3, post_ctrl_ff3);
        $display("CROSSCHECK u_dp_ff4=%0d,%0d",   pre_dp_ff4,   post_dp_ff4);
        $display("CROSSCHECK u_dp_ff5=%0d,%0d",   pre_dp_ff5,   post_dp_ff5);
        $display("CROSSCHECK u_priv_ff1=%0d,%0d", pre_priv_ff1, post_priv_ff1);
        $display("CROSSCHECK u_priv_ff2=%0d,%0d", pre_priv_ff2, post_priv_ff2);

        $finish;
    end

endmodule