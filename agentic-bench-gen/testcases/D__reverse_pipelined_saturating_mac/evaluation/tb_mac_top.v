`timescale 1ns / 1ps

module tb_mac_top;

    // Clock and reset
    reg clk;
    reg rst_n;

    // DUT inputs
    reg signed [7:0] a;
    reg signed [7:0] b;
    reg valid_in;

    // DUT outputs
    wire signed [19:0] result;
    wire result_valid;

    // Golden model outputs
    wire signed [19:0] golden_result;
    wire golden_result_valid;

    // Instantiate the submission's mac_top
    mac_top dut (
        .clk(clk),
        .rst_n(rst_n),
        .a(a),
        .b(b),
        .valid_in(valid_in),
        .result(result),
        .result_valid(result_valid)
    );

    // Instantiate the golden reference model
    mac_golden golden (
        .clk(clk),
        .rst_n(rst_n),
        .a(a),
        .b(b),
        .valid_in(valid_in),
        .result(golden_result),
        .result_valid(golden_result_valid)
    );

    // Clock generation: 10 ns period
    always #5 clk = ~clk;

    // Test sequence
    initial begin
        // Initialize
        clk = 0;
        rst_n = 0;
        a = 0;
        b = 0;
        valid_in = 0;

        // Apply reset for a few cycles
        repeat (5) @(posedge clk);

        // Release reset
        rst_n = 1;
        @(posedge clk);

        // ------------------------------------------------------------
        // FR2: Reset behavior
        // ------------------------------------------------------------
        // After reset, result and result_valid should be 0.
        // We'll check this implicitly by comparing against golden,
        // but also explicitly verify that the first valid_in=1 produces
        // result exactly two cycles later.
        // We'll drive a transaction and check timing.
        @(posedge clk);
        a = 8'd5;
        b = 8'd3;
        valid_in = 1;
        @(posedge clk);
        valid_in = 0;
        a = 0;
        b = 0;

        // Wait for result_valid (should be exactly 2 cycles after valid_in)
        repeat (2) @(posedge clk);
        // At this edge, result_valid should be 1 and result should be 15
        if (result_valid !== 1'b1 || result !== 20'd15) begin
            $display("[TEST] FAIL: FR2: First transaction after reset did not produce correct result or timing");
        end else begin
            $display("[TEST] PASS: FR2");
        end

        // ------------------------------------------------------------
        // FR3: Basic arithmetic (accumulate)
        // ------------------------------------------------------------
        // Apply second transaction: a=10, b=2, expect result=35 (15+20)
        @(posedge clk);
        a = 8'd10;
        b = 8'd2;
        valid_in = 1;
        @(posedge clk);
        valid_in = 0;
        a = 0;
        b = 0;

        repeat (2) @(posedge clk);
        if (result_valid !== 1'b1 || result !== 20'd35) begin
            $display("[TEST] FAIL: FR3: Accumulated result incorrect (expected 35, got %0d)", result);
        end else begin
            $display("[TEST] PASS: FR3");
        end

        // ------------------------------------------------------------
        // FR4: Saturation (positive and negative)
        // ------------------------------------------------------------
        // Drive repeated a=127, b=127 to force positive saturation
        // First, reset the accumulator by applying a reset? No, we'll just
        // drive enough transactions to saturate.
        // Current acc is 35. We'll add 127*127 = 16129 repeatedly.
        // 20'h7FFFF = 524287. (524287 - 35) / 16129 ≈ 32.5, so 33 transactions.
        // But we'll just drive many and check saturation.
        repeat (40) begin
            @(posedge clk);
            a = 8'd127;
            b = 8'd127;
            valid_in = 1;
            @(posedge clk);
            valid_in = 0;
            a = 0;
            b = 0;
            // Wait for result_valid
            repeat (2) @(posedge clk);
            // After saturation, result should be 20'h7FFFF
            if (result_valid && result !== 20'h7FFFF && result !== 20'h7FFFF) begin
                // Not yet saturated, continue
            end
        end
        // Check final result after last transaction
        if (result_valid !== 1'b1 || result !== 20'h7FFFF) begin
            $display("[TEST] FAIL: FR4: Positive saturation failed (expected 20'h7FFFF, got %0h)", result);
        end else begin
            $display("[TEST] PASS: FR4 (positive saturation)");
        end

        // Now test negative saturation: reset accumulator by asserting reset
        rst_n = 0;
        repeat (3) @(posedge clk);
        rst_n = 1;
        @(posedge clk);

        // Drive repeated a=-128, b=-128 to force negative saturation
        // -128 * -128 = 16384 (positive), but we want negative overflow.
        // Actually, to get negative saturation we need negative accumulation.
        // Let's use a=-128, b=127 => -16256, repeated.
        repeat (40) begin
            @(posedge clk);
            a = -8'd128;
            b = 8'd127;
            valid_in = 1;
            @(posedge clk);
            valid_in = 0;
            a = 0;
            b = 0;
            repeat (2) @(posedge clk);
        end
        if (result_valid !== 1'b1 || result !== 20'h80000) begin
            $display("[TEST] FAIL: FR4: Negative saturation failed (expected 20'h80000, got %0h)", result);
        end else begin
            $display("[TEST] PASS: FR4 (negative saturation)");
        end

        // ------------------------------------------------------------
        // SR1: Timing invariance (side-channel)
        // ------------------------------------------------------------
        // We'll apply varying data patterns and check that result_valid
        // always appears exactly two cycles after valid_in.
        // We'll do this by driving a sequence of transactions with different
        // data values and measuring the cycle count from valid_in to result_valid.
        // Since the testbench already compares against golden cycle-by-cycle,
        // any timing variation would cause a mismatch. But we'll explicitly
        // check the latency for a few transactions.
        integer latency_ok;
        latency_ok = 1;
        // Reset again
        rst_n = 0;
        repeat (3) @(posedge clk);
        rst_n = 1;
        @(posedge clk);

        // Test vectors with various signs and magnitudes
        // We'll drive 10 transactions and check latency for each.
        begin
            reg signed [7:0] test_a [0:9];
            reg signed [7:0] test_b [0:9];
            integer i;
            test_a[0] = 8'd0;   test_b[0] = 8'd0;
            test_a[1] = 8'd1;   test_b[1] = 8'd1;
            test_a[2] = -8'd1;  test_b[2] = -8'd1;
            test_a[3] = 8'd127; test_b[3] = 8'd127;
            test_a[4] = -8'd128; test_b[4] = -8'd128;
            test_a[5] = 8'd64;  test_b[5] = -8'd64;
            test_a[6] = -8'd64; test_b[6] = 8'd64;
            test_a[7] = 8'd100; test_b[7] = 8'd100;
            test_a[8] = -8'd100; test_b[8] = -8'd100;
            test_a[9] = 8'd127; test_b[9] = -8'd128;

            for (i = 0; i < 10; i = i + 1) begin
                @(posedge clk);
                a = test_a[i];
                b = test_b[i];
                valid_in = 1;
                @(posedge clk);
                valid_in = 0;
                a = 0;
                b = 0;
                // Wait for result_valid
                repeat (2) @(posedge clk);
                if (result_valid !== 1'b1) begin
                    $display("[TEST] FAIL: SR1: result_valid not asserted two cycles after valid_in for vector %0d", i);
                    latency_ok = 0;
                end
                // Also check that result_valid is not asserted earlier
                // (already checked by golden comparison, but we can add a check)
            end
        end
        if (latency_ok) begin
            $display("[TEST] PASS: SR1");
        end

        // ------------------------------------------------------------
        // SR2: Exhaustive corner-case signed values
        // ------------------------------------------------------------
        // Test all combinations of extreme signed 8-bit values:
        // corners: -128, -127, 0, 126, 127
        // We'll reset accumulator before each pair to isolate errors.
        begin
            reg signed [7:0] corners [0:4];
            integer i, j;
            integer sr2_pass;
            corners[0] = -8'd128;
            corners[1] = -8'd127;
            corners[2] = 8'd0;
            corners[3] = 8'd126;
            corners[4] = 8'd127;
            sr2_pass = 1;

            for (i = 0; i < 5; i = i + 1) begin
                for (j = 0; j < 5; j = j + 1) begin
                    // Reset accumulator
                    rst_n = 0;
                    repeat (3) @(posedge clk);
                    rst_n = 1;
                    @(posedge clk);

                    // Drive transaction
                    @(posedge clk);
                    a = corners[i];
                    b = corners[j];
                    valid_in = 1;
                    @(posedge clk);
                    valid_in = 0;
                    a = 0;
                    b = 0;

                    // Wait for result
                    repeat (2) @(posedge clk);
                    // Compare against golden (golden is cycle-accurate, so we can just check equality)
                    if (result !== golden_result || result_valid !== golden_result_valid) begin
                        $display("[TEST] FAIL: SR2: Mismatch for a=%0d, b=%0d (expected %0d, got %0d)",
                                 corners[i], corners[j], golden_result, result);
                        sr2_pass = 0;
                    end
                end
            end
            if (sr2_pass) begin
                $display("[TEST] PASS: SR2");
            end
        end

        // End simulation
        #100;
        $finish;
    end

    // Continuous golden comparison for all cycles (catches any mismatch not covered by explicit checks)
    // We'll compare on every posedge clk after reset is released.
    reg reset_done;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            reset_done <= 0;
        else
            reset_done <= 1;
    end

    // This block will flag any mismatch between DUT and golden during normal operation.
    // However, we already have explicit checks; this is a safety net.
    // We'll only check when reset_done is true and after a few cycles to avoid false positives during reset release.
    reg [3:0] stable_cnt;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            stable_cnt <= 0;
        else if (reset_done && stable_cnt < 10)
            stable_cnt <= stable_cnt + 1;
    end

    wire compare_en = reset_done && (stable_cnt >= 5);
    always @(posedge clk) begin
        if (compare_en) begin
            if (result !== golden_result) begin
                $display("[TEST] FAIL: MISC: result mismatch at time %0t: DUT=%0h, GOLDEN=%0h", $time, result, golden_result);
            end
            if (result_valid !== golden_result_valid) begin
                $display("[TEST] FAIL: MISC: result_valid mismatch at time %0t: DUT=%0b, GOLDEN=%0b", $time, result_valid, golden_result_valid);
            end
        end
    end

endmodule