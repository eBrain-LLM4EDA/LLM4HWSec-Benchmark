//-----------------------------------------------------------------------------
// evaluation/tb_policy_sweep.v
//
// Policy-sweep testbench for nmi_arbiter. After a 2-cycle synchronous
// reset, sequentially drives all 16 combinations of nmi (1 bit) and
// irq[2:0] (3 bits), holding each combination for one full clock cycle,
// then samples the registered grant output on the following rising edge
// (respecting the documented one-cycle registered latency). Prints one
// deterministic line per vector:
//
//   VEC nmi=<b> irq=<3b> grant=<4b>
//
// evaluate.py parses these 16 lines to grade FR2/FR3 against the
// documented policy (computed independently in Python from the vector's
// nmi/irq values) and to build the ground-truth partition between the
// true Trojan trigger vector (nmi=1, irq=111) and the other 15 vectors,
// purely from observed simulation of inputs/nmi_arbiter.v.
//-----------------------------------------------------------------------------

`timescale 1ns/1ps

module tb_policy_sweep;

    reg        clk;
    reg        rst_n;
    reg        nmi;
    reg  [2:0] irq;
    wire [3:0] grant;

    nmi_arbiter dut (
        .clk   (clk),
        .rst_n (rst_n),
        .nmi   (nmi),
        .irq   (irq),
        .grant (grant)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    integer i;

    initial begin
        rst_n = 1'b0;
        nmi   = 1'b0;
        irq   = 3'b000;

        // Hold reset for two cycles.
        @(negedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        // One extra settle cycle post-reset before starting the sweep,
        // so the first driven vector is sampled from a clean, known state.
        @(negedge clk);

        // Sweep all 16 combinations of {nmi, irq[2:0]} in a fixed,
        // deterministic order: i = {nmi, irq2, irq1, irq0} as a 4-bit
        // counter from 0 to 15.
        for (i = 0; i < 16; i = i + 1) begin
            // Drive the vector on the negedge so it is stable well before
            // the next rising edge samples it.
            nmi = i[3];
            irq = i[2:0];

            // Wait for the rising edge that samples this vector, then the
            // following rising edge where the registered grant reflects it
            // (one-cycle registered latency: grant updates on the posedge
            // immediately after the vector was present at the preceding
            // posedge).
            @(posedge clk);
            @(posedge clk);
            #1;
            $display("VEC nmi=%b irq=%b grant=%b", nmi, irq, grant);

            // Return to negedge alignment before driving the next vector.
            @(negedge clk);
        end

        $finish;
    end

endmodule