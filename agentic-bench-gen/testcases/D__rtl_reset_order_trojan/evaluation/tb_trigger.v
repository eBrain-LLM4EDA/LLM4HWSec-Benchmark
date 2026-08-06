`timescale 1ns / 1ps

module tb_trigger;

    reg clk;
    reg core_rst_n;
    reg peri_rst_n;
    reg [3:0] addr;
    reg [7:0] wdata;
    reg we;
    reg [1:0] alu_op;
    wire [7:0] rdata;
    wire protected_mode;

    // Instantiate the design under test
    core_wrapper dut (
        .clk(clk),
        .core_rst_n(core_rst_n),
        .peri_rst_n(peri_rst_n),
        .addr(addr),
        .wdata(wdata),
        .we(we),
        .alu_op(alu_op),
        .rdata(rdata),
        .protected_mode(protected_mode)
    );

    // Clock generation: 10 ns period
    always #5 clk = ~clk;

    // Task to apply simultaneous reset
    task apply_simultaneous_reset;
        begin
            core_rst_n = 1'b0;
            peri_rst_n = 1'b0;
            repeat(2) @(posedge clk);
            core_rst_n = 1'b1;
            peri_rst_n = 1'b1;
        end
    endtask

    // Task to release resets with a specified gap (peri released `gap` cycles before core)
    task apply_gapped_reset(input integer gap);
        begin
            // Assert both resets
            core_rst_n = 1'b0;
            peri_rst_n = 1'b0;
            repeat(2) @(posedge clk);
            // Release peri first
            peri_rst_n = 1'b1;
            // Wait gap cycles
            repeat(gap) @(posedge clk);
            // Release core
            core_rst_n = 1'b1;
        end
    endtask

    // Task to assert both resets simultaneously (for clearing sticky trigger)
    task assert_both_resets;
        begin
            core_rst_n = 1'b0;
            peri_rst_n = 1'b0;
            repeat(2) @(posedge clk);
        end
    endtask

    integer cycle_count;

    // Main test sequence
    initial begin
        // Initialize signals
        clk = 1'b0;
        core_rst_n = 1'b1;
        peri_rst_n = 1'b1;
        addr = 4'd0;
        wdata = 8'd0;
        we = 1'b0;
        alu_op = 2'b00;
        cycle_count = 0;

        // Wait a few cycles for initialization
        repeat(5) @(posedge clk);

        // Test 1: Simultaneous reset release (expect protected_mode=0)
        $display("[PROBE] simultaneous_test start");
        apply_simultaneous_reset();
        // Monitor for several cycles after release
        repeat(10) begin
            @(posedge clk);
            $display("[PROBE] simultaneous_test %0d %b", cycle_count, protected_mode);
            cycle_count = cycle_count + 1;
        end

        // Test 2: Core-only reset release (peri stays high)
        $display("[PROBE] core_only_test start");
        core_rst_n = 1'b0;
        repeat(2) @(posedge clk);
        core_rst_n = 1'b1;
        repeat(10) begin
            @(posedge clk);
            $display("[PROBE] core_only_test %0d %b", cycle_count, protected_mode);
            cycle_count = cycle_count + 1;
        end

        // Test 3: Peri-only reset release (core stays high)
        $display("[PROBE] peri_only_test start");
        peri_rst_n = 1'b0;
        repeat(2) @(posedge clk);
        peri_rst_n = 1'b1;
        repeat(10) begin
            @(posedge clk);
            $display("[PROBE] peri_only_test %0d %b", cycle_count, protected_mode);
            cycle_count = cycle_count + 1;
        end

        // Test 4: Trigger test – peri released 2 cycles before core
        $display("[PROBE] trigger_test start");
        apply_gapped_reset(2);
        // Monitor for many cycles to see if protected_mode asserts
        repeat(20) begin
            @(posedge clk);
            $display("[PROBE] trigger_test %0d %b", cycle_count, protected_mode);
            cycle_count = cycle_count + 1;
        end

        // Test 5: Persistence test – after trigger, check sticky behavior
        $display("[PROBE] persistence_test start");
        // First, ensure we are in triggered state (apply gap again if needed)
        // We'll just continue from previous state; if trigger_test already set it, good.
        // If not, we apply gap again.
        // To be safe, apply gap again to guarantee trigger is set.
        apply_gapped_reset(2);
        // Now monitor for several cycles to confirm protected_mode stays high
        repeat(10) begin
            @(posedge clk);
            $display("[PROBE] persistence_test %0d %b", cycle_count, protected_mode);
            cycle_count = cycle_count + 1;
        end
        // Now assert both resets simultaneously to clear
        assert_both_resets();
        // Release simultaneously
        core_rst_n = 1'b1;
        peri_rst_n = 1'b1;
        // Monitor after clear
        repeat(10) begin
            @(posedge clk);
            $display("[PROBE] persistence_test %0d %b", cycle_count, protected_mode);
            cycle_count = cycle_count + 1;
        end

        $finish;
    end

endmodule