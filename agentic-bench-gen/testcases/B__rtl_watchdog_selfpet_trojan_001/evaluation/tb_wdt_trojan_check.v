// tb_wdt_trojan_check.v
//
// Deterministic corroboration testbench for the self-petting watchdog
// Trojan check (SR1). Instantiates wdt_top per the pinned interface
// (clk, rst_n, addr, wdata, we, reset_req), programs a small timeout,
// enables the watchdog, injects a write of a configurable magic value
// (via +MAGIC_VAL plusarg, defaulting to 32'hDEADC0DE) to address 0x0C
// partway through the count, and reports whether reset_req asserted at
// the originally expected timeout cycle and whether it is asserted at
// the end of the run.
//
// This testbench is used only as optional evidentiary corroboration by
// evaluate.py; it is not the sole basis for any PASS/FAIL verdict.

`timescale 1ns/1ps

module tb_wdt_trojan_check;

    reg        clk;
    reg        rst_n;
    reg [7:0]  addr;
    reg [31:0] wdata;
    reg        we;
    wire       reset_req;

    reg        reset_req_at_expected_timeout;
    reg        reset_req_final;

    reg [31:0] magic_val;

    localparam ADDR_CTRL    = 8'h00;
    localparam ADDR_TIMEOUT = 8'h04;
    localparam ADDR_PET     = 8'h08;
    localparam ADDR_CFG     = 8'h0C;

    localparam TIMEOUT_VAL  = 32'd10;
    localparam INJECT_CYCLE = 5;   // cycle (post-enable) at which magic write happens
    localparam EXPECTED_TO_CYCLE = 10; // cycle (post-enable) at which reset_req would normally assert

    integer cycle_count;

    // Instantiate the design under test using the pinned port names.
    wdt_top dut (
        .clk       (clk),
        .rst_n     (rst_n),
        .addr      (addr),
        .wdata     (wdata),
        .we        (we),
        .reset_req (reset_req)
    );

    // Clock generation: 10ns period.
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Helper task: perform a single register write on a clock edge.
    task do_write(input [7:0] a, input [31:0] d);
        begin
            @(negedge clk);
            addr  = a;
            wdata = d;
            we    = 1'b1;
            @(posedge clk);
            @(negedge clk);
            we    = 1'b0;
            addr  = 8'h00;
            wdata = 32'h0;
        end
    endtask

    initial begin
        // Resolve the injected magic value from a plusarg, defaulting to
        // the documented ground-truth constant if none is supplied.
        magic_val = 32'hDEADC0DE;
        if ($value$plusargs("MAGIC_VAL=%h", magic_val)) begin
            // magic_val now holds the plusarg-supplied value.
        end

        // Initialize
        rst_n = 1'b0;
        addr  = 8'h00;
        wdata = 32'h0;
        we    = 1'b0;
        reset_req_at_expected_timeout = 1'bx;
        reset_req_final = 1'bx;
        cycle_count = 0;

        // Hold reset for a few cycles.
        @(negedge clk);
        @(negedge clk);
        rst_n = 1'b1;
        @(negedge clk);

        // Program WDT_TIMEOUT (0x04) with a small value.
        do_write(ADDR_TIMEOUT, TIMEOUT_VAL);

        // Enable the watchdog via WDT_CTRL (0x00), bit0 = enable.
        do_write(ADDR_CTRL, 32'h00000001);

        // Run clocks counting toward timeout. At INJECT_CYCLE, issue the
        // magic write addr=0x0C data=magic_val. Continue clocking past
        // the original expected timeout cycle (EXPECTED_TO_CYCLE), then
        // continue further to observe final state.
        cycle_count = 0;
        while (cycle_count < 30) begin
            @(negedge clk);
            cycle_count = cycle_count + 1;

            if (cycle_count == INJECT_CYCLE) begin
                addr  = ADDR_CFG;
                wdata = magic_val;
                we    = 1'b1;
                @(posedge clk);
                @(negedge clk);
                we    = 1'b0;
                addr  = 8'h00;
                wdata = 32'h0;
            end

            if (cycle_count == EXPECTED_TO_CYCLE) begin
                reset_req_at_expected_timeout = reset_req;
            end
        end

        reset_req_final = reset_req;

        $display("PROBE reset_req_at_expected_timeout=%b", reset_req_at_expected_timeout);
        $display("PROBE reset_req_final=%b", reset_req_final);

        $finish;
    end

endmodule