`timescale 1ns/1ps

module tb_regfile;

    reg        clk;
    reg        rst;
    reg        we;
    reg  [1:0] waddr;
    reg  [7:0] wdata;
    reg  [1:0] raddr0;
    reg  [1:0] raddr1;
    wire [7:0] rdata0;
    wire [7:0] rdata1;

    reg_file_recovered dut (
        .clk    (clk),
        .rst    (rst),
        .we     (we),
        .waddr  (waddr),
        .wdata  (wdata),
        .raddr0 (raddr0),
        .raddr1 (raddr1),
        .rdata0 (rdata0),
        .rdata1 (rdata1)
    );

    // clock generation: 10ns period, toggle every 5ns
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // ------------------------------------------------------------------
    // Stimulus file format (produced by evaluate.py):
    //   line 1: <num_cycles>
    //   lines 2..N+1: <rst> <we> <waddr> <wdata> <raddr0> <raddr1>
    // ------------------------------------------------------------------
    integer num_cycles;
    integer stim_rst    [0:1023];
    integer stim_we     [0:1023];
    integer stim_waddr  [0:1023];
    integer stim_wdata  [0:1023];
    integer stim_raddr0 [0:1023];
    integer stim_raddr1 [0:1023];

    reg [4095:0] stimfile_name;
    integer fh;
    integer i;
    integer rc;

    // ------------------------------------------------------------------
    // Single initial block: load stimulus fully, THEN drive/probe.
    // This avoids any race between file loading and DUT driving --
    // everything is sequenced with blocking statements in program order,
    // so stimulus arrays are guaranteed fully populated before cycle 0
    // is driven or probed. There is no second initial/always block that
    // touches rst/we/waddr/wdata/raddr0/raddr1, so there is no
    // simulation-time window in which the drive loop could start before
    // the $fscanf loop below has finished populating the stim_* arrays.
    // ------------------------------------------------------------------
    initial begin
        if (!$value$plusargs("STIMFILE=%s", stimfile_name)) begin
            $display("ERROR: +STIMFILE=<path> not provided");
            $finish;
        end

        fh = $fopen(stimfile_name, "r");
        if (fh == 0) begin
            $display("ERROR: could not open stimulus file");
            $finish;
        end
        rc = $fscanf(fh, "%d\n", num_cycles);
        for (i = 0; i < num_cycles; i = i + 1) begin
            rc = $fscanf(fh, "%d %d %d %d %d %d\n",
                         stim_rst[i], stim_we[i], stim_waddr[i],
                         stim_wdata[i], stim_raddr0[i], stim_raddr1[i]);
        end
        $fclose(fh);

        // initialize all drive signals to stim[0] ahead of the first edge,
        // still within this same initial block / same time step, so the
        // very first posedge clk sees fully-valid cycle-0 stimulus.
        rst    = stim_rst[0];
        we     = stim_we[0];
        waddr  = stim_waddr[0];
        wdata  = stim_wdata[0];
        raddr0 = stim_raddr0[0];
        raddr1 = stim_raddr1[0];

        for (i = 0; i < num_cycles; i = i + 1) begin
            // drive current cycle's inputs (already set for i==0; for i>0
            // they were set at the end of the previous iteration's MID step)
            rst    = stim_rst[i];
            we     = stim_we[i];
            waddr  = stim_waddr[i];
            wdata  = stim_wdata[i];
            raddr0 = stim_raddr0[i];
            raddr1 = stim_raddr1[i];

            // wait for the rising edge that commits this cycle's write/reset
            @(posedge clk);
            // small delta to let combinational logic settle post-edge
            #1;

            $display("PROBE %0d %02h %02h", i, rdata0, rdata1);

            // Mid-cycle address toggle test (SR1): if there is a next
            // cycle, toggle raddr0/raddr1 to that cycle's addresses right
            // now, well before the next posedge, and sample combinationally.
            if (i + 1 < num_cycles) begin
                raddr0 = stim_raddr0[i + 1];
                raddr1 = stim_raddr1[i + 1];
                #1;
                $display("PROBE_MID %0d %02h %02h", i, rdata0, rdata1);
            end
        end

        $display("DONE");
        $finish;
    end

endmodule