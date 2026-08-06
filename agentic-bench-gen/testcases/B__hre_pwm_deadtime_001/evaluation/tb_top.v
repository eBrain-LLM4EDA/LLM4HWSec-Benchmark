`timescale 1ns/1ps

module tb_top;

    reg        clk;
    reg        rst;
    reg        en;
    reg [3:0]  duty;

    wire       sub_hi, sub_lo;
    wire       ref_hi, ref_lo;

    // ---- DUT: submission ----
    pwm_deadtime_gen dut_sub (
        .clk(clk),
        .rst(rst),
        .en(en),
        .duty(duty),
        .pwm_hi(sub_hi),
        .pwm_lo(sub_lo)
    );

    // ---- DUT: independently authored reference ----
    reference_pwm_deadtime_gen dut_ref (
        .clk(clk),
        .rst(rst),
        .en(en),
        .duty(duty),
        .pwm_hi(ref_hi),
        .pwm_lo(ref_lo)
    );

    // ---- clock ----
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // ---- bookkeeping ----
    integer fr1_fail_count;
    integer fr2_fail_count;
    integer fr3_fail_count;
    integer fr4_fail_count;
    integer sr1_fail_count;
    integer sr2_fail_count;

    reg [255:0] fr1_reason, fr2_reason, fr3_reason, fr4_reason, sr1_reason, sr2_reason;

    // simple deterministic LFSR for pseudo-random en toggling (fixed seed, no $random dependency)
    reg [15:0] lfsr;

    task lfsr_step;
        begin
            lfsr = {lfsr[14:0], lfsr[15] ^ lfsr[13] ^ lfsr[12] ^ lfsr[10]};
        end
    endtask

    // do one reset pulse: assert rst for 1 cycle, then release
    task do_reset;
        begin
            rst = 1'b1;
            @(posedge clk);
            #1;
            rst = 1'b0;
        end
    endtask

    // check overlap + match on the current cycle (called right after a posedge, post settle)
    task check_overlap_and_match;
        output ok_overlap;
        output ok_match;
        begin
            ok_overlap = !(sub_hi && sub_lo);
            ok_match   = (sub_hi === ref_hi) && (sub_lo === ref_lo);
        end
    endtask

    integer i, j, k;
    integer d;
    reg ok_ov, ok_mt;

    // ------------------------------------------------------------
    // Histories captured during the FR2/SR1 deterministic boundary
    // sweep, used later by SR2 for cross-checking off-by-one
    // narrowing at duty=D and D+1 transitions. Sized generously:
    // 16 duties * 48 cycles.
    // ------------------------------------------------------------
    reg boundary_sub_hi_hist [0:16*48-1];
    reg boundary_sub_lo_hist [0:16*48-1];
    integer boundary_valid; // 1 once the deterministic held-en pass has populated the histories

    // ------------------------------------------------------------
    // Scenario (pre-0): FR4 -- dedicated multi-phase-offset hold test.
    // Runs FIRST, isolated from all other scenarios, on a freshly
    // reset DUT pair for each phase offset. For each of 4 distinct
    // (offset, duty) combinations: reset, run 'offset' cycles with
    // en=1, then deassert en for >=8 cycles (checking cycle-exact
    // match every held cycle), then re-enable and check >=4 more
    // cycles of correct resumption from the held (not corrupted)
    // value.
    // ------------------------------------------------------------
    task scenario_fr4;
        integer phase_idx;
        integer offset;
        reg [3:0] phase_duty;
        begin
            fr4_fail_count = 0;
            fr4_reason = "";

            for (phase_idx = 0; phase_idx < 4; phase_idx = phase_idx + 1) begin
                case (phase_idx)
                    0: begin offset = 0;  phase_duty = 4'd8;  end
                    1: begin offset = 3;  phase_duty = 4'd5;  end
                    2: begin offset = 6;  phase_duty = 4'd11; end
                    3: begin offset = 9;  phase_duty = 4'd3;  end
                    default: begin offset = 0; phase_duty = 4'd8; end
                endcase

                duty = phase_duty;
                en   = 1'b1;
                do_reset;

                // run 'offset' cycles with en=1 before entering the hold
                for (i = 0; i < offset; i = i + 1) begin
                    @(posedge clk);
                    #1;
                    check_overlap_and_match(ok_ov, ok_mt);
                    if (!ok_mt && fr4_fail_count == 0) begin
                        fr4_fail_count = fr4_fail_count + 1;
                        fr4_reason = "mismatch vs reference before entering hold (pre-hold phase run)";
                    end
                end

                // deassert en for exactly 8 consecutive cycles, checking
                // cycle-exact match against reference every held cycle
                en = 1'b0;
                for (i = 0; i < 8; i = i + 1) begin
                    @(posedge clk);
                    #1;
                    check_overlap_and_match(ok_ov, ok_mt);
                    if (!ok_mt && fr4_fail_count == 0) begin
                        fr4_fail_count = fr4_fail_count + 1;
                        fr4_reason = "mismatch vs reference during en=0 hold interval (phase-offset test)";
                    end
                end

                // re-enable and check correct resumption from the held
                // (not corrupted) value for >=4 cycles
                en = 1'b1;
                for (i = 0; i < 4; i = i + 1) begin
                    @(posedge clk);
                    #1;
                    check_overlap_and_match(ok_ov, ok_mt);
                    if (!ok_mt && fr4_fail_count == 0) begin
                        fr4_fail_count = fr4_fail_count + 1;
                        fr4_reason = "mismatch vs reference after resuming from held value (phase-offset test)";
                    end
                end
            end

            if (fr4_fail_count == 0)
                $display("PROBE FR4 PASS en=0 held for 8 cycles at 4 distinct phase offsets (0,3,6,9) with distinct duties, counter/outputs tracked reference throughout hold and after resume");
            else
                $display("PROBE FR4 FAIL %0s", fr4_reason);
        end
    endtask

    // ------------------------------------------------------------
    // Scenario (a): FR1 -- duty=8, en=1 held, 1-cycle reset then
    // release, run 4 full periods (64 cycles), compare cycle-by-cycle.
    // ------------------------------------------------------------
    task scenario_fr1;
        begin
            fr1_fail_count = 0;
            fr1_reason = "";
            duty = 4'd8;
            en   = 1'b1;
            do_reset;
            // after reset released, run 4*16 = 64 cycles
            for (i = 0; i < 64; i = i + 1) begin
                @(posedge clk);
                #1;
                check_overlap_and_match(ok_ov, ok_mt);
                if (!ok_mt && fr1_fail_count == 0) begin
                    fr1_fail_count = fr1_fail_count + 1;
                    fr1_reason = "mismatch vs reference during duty=8 trace";
                end
            end

            if (fr1_fail_count == 0)
                $display("PROBE FR1 PASS duty=8 en=1 4-period trace matched reference");
            else
                $display("PROBE FR1 FAIL %0s", fr1_reason);
        end
    endtask

    // ------------------------------------------------------------
    // Scenario (b): FR2/SR1 -- duty=0..15 sweep.
    //
    // Pass 1 (deterministic, held-en): en=1 held throughout, all
    // duties, 3 full periods (48 cycles) each. EVERY cycle is sampled
    // (not periodic sampling) and recorded into boundary_sub_hi_hist /
    // boundary_sub_lo_hist for later SR2 cross-checking. This pass
    // deterministically covers every duty value including all
    // duty-boundary regions on every run regardless of any random
    // seed, guaranteeing detection of a narrowed (1-cycle-early)
    // low-side window.
    //
    // Pass 2 (deterministic, fixed alternating-en): en toggled every
    // single cycle (no LFSR, no randomness) across the same duty
    // sweep, 3 full periods worth of toggled-en cycles per duty,
    // again sampling every cycle.
    //
    // Pass 3 (randomized layer, fixed-seed LFSR): retained from the
    // prior round as an additional randomized stress layer.
    // ------------------------------------------------------------
    task scenario_fr2_sr1;
        integer hist_base;
        begin
            fr2_fail_count = 0;
            sr1_fail_count = 0;
            fr2_reason = "";
            sr1_reason = "";
            boundary_valid = 0;

            // ---- Pass 1: deterministic held-en, every duty, every cycle sampled ----
            for (d = 0; d < 16; d = d + 1) begin
                duty = d[3:0];
                en   = 1'b1;
                do_reset;
                hist_base = d * 48;
                for (i = 0; i < 48; i = i + 1) begin
                    @(posedge clk);
                    #1;
                    check_overlap_and_match(ok_ov, ok_mt);
                    boundary_sub_hi_hist[hist_base + i] = sub_hi;
                    boundary_sub_lo_hist[hist_base + i] = sub_lo;
                    if (!ok_ov && sr1_fail_count == 0) begin
                        sr1_fail_count = sr1_fail_count + 1;
                        sr1_reason = "overlap observed (deterministic held-en pass)";
                    end
                    if (!ok_mt && fr2_fail_count == 0) begin
                        fr2_fail_count = fr2_fail_count + 1;
                        fr2_reason = "mismatch vs reference (deterministic held-en pass)";
                    end
                end
            end
            boundary_valid = 1;

            // ---- Pass 2: deterministic fixed alternating-en, every duty, every cycle sampled ----
            for (d = 0; d < 16; d = d + 1) begin
                duty = d[3:0];
                en   = 1'b1;
                do_reset;
                for (i = 0; i < 48; i = i + 1) begin
                    en = (i % 2 == 0) ? 1'b1 : 1'b0;
                    @(posedge clk);
                    #1;
                    check_overlap_and_match(ok_ov, ok_mt);
                    if (!ok_ov && sr1_fail_count == 0) begin
                        sr1_fail_count = sr1_fail_count + 1;
                        sr1_reason = "overlap observed (deterministic alternating-en pass)";
                    end
                    if (!ok_mt && fr2_fail_count == 0) begin
                        fr2_fail_count = fr2_fail_count + 1;
                        fr2_reason = "mismatch vs reference (deterministic alternating-en pass)";
                    end
                end
            end

            // ---- Pass 3: randomized layer via deterministic fixed-seed LFSR ----
            lfsr = 16'hACE1; // fixed seed
            for (d = 0; d < 16; d = d + 1) begin
                duty = d[3:0];
                en   = 1'b1;
                do_reset;
                for (i = 0; i < 48; i = i + 1) begin
                    lfsr_step;
                    en = lfsr[0];
                    @(posedge clk);
                    #1;
                    check_overlap_and_match(ok_ov, ok_mt);
                    if (!ok_ov && sr1_fail_count == 0) begin
                        sr1_fail_count = sr1_fail_count + 1;
                        sr1_reason = "overlap observed (en-toggle LFSR pass)";
                    end
                    if (!ok_mt && fr2_fail_count == 0) begin
                        fr2_fail_count = fr2_fail_count + 1;
                        fr2_reason = "mismatch vs reference (en-toggle LFSR pass)";
                    end
                end
            end

            if (fr2_fail_count == 0)
                $display("PROBE FR2 PASS duty=0..15 sweep (deterministic held-en, deterministic alternating-en, and LFSR-en passes) matched reference every cycle");
            else
                $display("PROBE FR2 FAIL %0s", fr2_reason);

            if (sr1_fail_count == 0)
                $display("PROBE SR1 PASS duty=0..15 sweep with deterministic held-en, deterministic alternating-en, and LFSR-en patterns: no overlap observed on submission on any sampled cycle");
            else
                $display("PROBE SR1 FAIL %0s", sr1_reason);
        end
    endtask

    // ------------------------------------------------------------
    // Scenario (c): FR3 -- duty=15 (pwm_lo never asserts, pwm_hi for
    // cnt=2..14) and duty=0,1,2 (pwm_hi never asserts). Match against
    // reference throughout, plus explicit boundary sanity.
    // ------------------------------------------------------------
    task scenario_fr3;
        begin
            fr3_fail_count = 0;
            fr3_reason = "";

            // duty = 15
            duty = 4'd15;
            en   = 1'b1;
            do_reset;
            for (i = 0; i < 32; i = i + 1) begin
                @(posedge clk);
                #1;
                check_overlap_and_match(ok_ov, ok_mt);
                if (!ok_mt && fr3_fail_count == 0) begin
                    fr3_fail_count = fr3_fail_count + 1;
                    fr3_reason = "mismatch vs reference at duty=15";
                end
                if (sub_lo && fr3_fail_count == 0) begin
                    fr3_fail_count = fr3_fail_count + 1;
                    fr3_reason = "pwm_lo asserted at duty=15 (should never assert)";
                end
            end

            // duty = 0, 1, 2 : pwm_hi must never assert
            for (d = 0; d <= 2; d = d + 1) begin
                duty = d[3:0];
                en   = 1'b1;
                do_reset;
                for (i = 0; i < 32; i = i + 1) begin
                    @(posedge clk);
                    #1;
                    check_overlap_and_match(ok_ov, ok_mt);
                    if (!ok_mt && fr3_fail_count == 0) begin
                        fr3_fail_count = fr3_fail_count + 1;
                        fr3_reason = "mismatch vs reference at low duty";
                    end
                    if (sub_hi && fr3_fail_count == 0) begin
                        fr3_fail_count = fr3_fail_count + 1;
                        fr3_reason = "pwm_hi asserted at duty<=2 (should never assert)";
                    end
                end
            end

            if (fr3_fail_count == 0)
                $display("PROBE FR3 PASS duty=15 (pwm_lo never asserts) and duty=0,1,2 (pwm_hi never asserts) matched reference");
            else
                $display("PROBE FR3 FAIL %0s", fr3_reason);
        end
    endtask

    // ------------------------------------------------------------
    // Scenario (e): SR2 -- for duty=3..13, measure the exact dead-time
    // gap width (in cycles) at (i) the period-start boundary before
    // pwm_hi may assert, and (ii) the duty-transition boundary before
    // pwm_lo may assert, on the SUBMISSION, and compare against the
    // SAME measurement taken on the REFERENCE over the identical run.
    // Also independently asserts width==2 regardless of reference
    // match, and cross-checks against the FR2/SR1 deterministic
    // held-en boundary histories (captured in Pass 1 of
    // scenario_fr2_sr1) at duty=D and duty=D+1 to catch any off-by-one
    // narrowing that a differently-phased local run might otherwise miss.
    // ------------------------------------------------------------

    // per-cycle sampled histories, sized generously for 3 periods (48 cycles) + margin
    reg sub_hi_hist [0:63];
    reg sub_lo_hist [0:63];
    reg ref_hi_hist [0:63];
    reg ref_lo_hist [0:63];

    integer gap_start_sub, gap_start_ref;
    integer gap_duty_sub, gap_duty_ref;
    integer idx;
    integer period_base;

    // helper: measure the low-run length of pwm_lo starting right after
    // pwm_hi's high-run ends, from a captured boundary history array
    // (used for the cross-check against scenario_fr2_sr1's Pass 1 data)
    task measure_duty_gap_from_boundary_hist;
        input  integer hbase;
        output integer gap_len;
        integer bidx;
        begin
            bidx = hbase;
            while (bidx < hbase + 16 && boundary_sub_hi_hist[bidx] == 1'b0)
                bidx = bidx + 1;
            while (bidx < hbase + 16 && boundary_sub_hi_hist[bidx] == 1'b1)
                bidx = bidx + 1;
            gap_len = 0;
            while (bidx < hbase + 16 && boundary_sub_lo_hist[bidx] == 1'b0) begin
                gap_len = gap_len + 1;
                bidx = bidx + 1;
            end
        end
    endtask

    integer cross_gap_d, cross_gap_dp1;

    task scenario_sr2;
        begin
            sr2_fail_count = 0;
            sr2_reason = "";

            for (d = 3; d <= 13; d = d + 1) begin
                duty = d[3:0];
                en   = 1'b1;
                do_reset;

                // capture 3 full periods = 48 cycles of both hi/lo, sub and ref
                for (i = 0; i < 48; i = i + 1) begin
                    @(posedge clk);
                    #1;
                    sub_hi_hist[i] = sub_hi;
                    sub_lo_hist[i] = sub_lo;
                    ref_hi_hist[i] = ref_hi;
                    ref_lo_hist[i] = ref_lo;
                end

                // Examine the 2nd period (indices 16..31) to avoid any
                // edge effects from the reset-adjacent first period.
                period_base = 16;

                // ---- boundary (i): period-start dead time before pwm_hi ----
                gap_start_sub = 0;
                idx = period_base;
                while (idx < period_base + 8 && sub_hi_hist[idx] == 1'b0) begin
                    gap_start_sub = gap_start_sub + 1;
                    idx = idx + 1;
                end

                gap_start_ref = 0;
                idx = period_base;
                while (idx < period_base + 8 && ref_hi_hist[idx] == 1'b0) begin
                    gap_start_ref = gap_start_ref + 1;
                    idx = idx + 1;
                end

                if (gap_start_sub != gap_start_ref && sr2_fail_count == 0) begin
                    sr2_fail_count = sr2_fail_count + 1;
                    sr2_reason = "period-start dead-time width mismatch vs reference";
                end
                if (gap_start_sub != 2 && sr2_fail_count == 0) begin
                    sr2_fail_count = sr2_fail_count + 1;
                    sr2_reason = "period-start dead-time width is not exactly 2 cycles";
                end

                // ---- boundary (ii): duty-transition dead time before pwm_lo ----
                idx = period_base;
                while (idx < period_base + 16 && sub_hi_hist[idx] == 1'b0)
                    idx = idx + 1;
                while (idx < period_base + 16 && sub_hi_hist[idx] == 1'b1)
                    idx = idx + 1;
                // idx now points at first low cycle after pwm_hi's window (submission)
                gap_duty_sub = 0;
                k = idx;
                while (k < period_base + 16 && sub_lo_hist[k] == 1'b0) begin
                    gap_duty_sub = gap_duty_sub + 1;
                    k = k + 1;
                end

                idx = period_base;
                while (idx < period_base + 16 && ref_hi_hist[idx] == 1'b0)
                    idx = idx + 1;
                while (idx < period_base + 16 && ref_hi_hist[idx] == 1'b1)
                    idx = idx + 1;
                gap_duty_ref = 0;
                k = idx;
                while (k < period_base + 16 && ref_lo_hist[k] == 1'b0) begin
                    gap_duty_ref = gap_duty_ref + 1;
                    k = k + 1;
                end

                if (gap_duty_sub != gap_duty_ref && sr2_fail_count == 0) begin
                    sr2_fail_count = sr2_fail_count + 1;
                    sr2_reason = "duty-boundary dead-time width mismatch vs reference";
                end
                if (gap_duty_sub != 2 && sr2_fail_count == 0) begin
                    sr2_fail_count = sr2_fail_count + 1;
                    sr2_reason = "duty-boundary dead-time width is not exactly 2 cycles";
                end

                // ---- cross-check against FR2/SR1 deterministic boundary
                // histories captured earlier (Pass 1, held-en, all duties) ----
                if (boundary_valid) begin
                    measure_duty_gap_from_boundary_hist(d * 48, cross_gap_d);
                    if (cross_gap_d != 2 && sr2_fail_count == 0) begin
                        sr2_fail_count = sr2_fail_count + 1;
                        sr2_reason = "duty-boundary dead-time width is not exactly 2 cycles (cross-check vs FR2/SR1 boundary history)";
                    end
                    if (d < 15) begin
                        measure_duty_gap_from_boundary_hist((d+1) * 48, cross_gap_dp1);
                        if (cross_gap_dp1 != 2 && sr2_fail_count == 0) begin
                            sr2_fail_count = sr2_fail_count + 1;
                            sr2_reason = "duty-boundary dead-time width is not exactly 2 cycles at duty+1 (cross-check vs FR2/SR1 boundary history)";
                        end
                    end
                end
            end

            if (sr2_fail_count == 0)
                $display("PROBE SR2 PASS duty=3..13: dead-time gap is exactly 2 cycles at both boundaries, matching reference and cross-checked against FR2/SR1 boundary histories");
            else
                $display("PROBE SR2 FAIL %0s", sr2_reason);
        end
    endtask

    // ------------------------------------------------------------
    // Top-level sequencing
    // ------------------------------------------------------------
    initial begin
        rst  = 1'b1;
        en   = 1'b0;
        duty = 4'd0;
        lfsr = 16'hACE1;
        boundary_valid = 0;

        // settle a couple cycles before starting scenarios
        @(posedge clk);
        @(posedge clk);

        // FR4 runs first and isolated, on freshly reset DUTs each phase,
        // so a broken hold-on-disable path cannot be masked or confounded
        // by other scenarios' state.
        scenario_fr4;

        scenario_fr1;
        scenario_fr2_sr1;
        scenario_fr3;
        scenario_sr2;

        $display("PROBE DONE PASS all scenarios completed");
        $finish;
    end

    // safety watchdog: bounded total cycle count, deterministic
    initial begin
        #200000;
        $display("PROBE FR1 FAIL watchdog timeout before completion");
        $display("PROBE FR2 FAIL watchdog timeout before completion");
        $display("PROBE FR3 FAIL watchdog timeout before completion");
        $display("PROBE FR4 FAIL watchdog timeout before completion");
        $display("PROBE SR1 FAIL watchdog timeout before completion");
        $display("PROBE SR2 FAIL watchdog timeout before completion");
        $finish;
    end

endmodule