// =============================================================================
// tb_quad_decoder.v
//
// Self-checking-free stimulus testbench for the pinned `quad_decoder`
// interface. This testbench does NOT itself judge pass/fail; it only drives
// a fixed, deterministic stimulus sequence and prints one PROBE line per
// sampled cycle after reset release. evaluate.py computes the independently
// derived expected values from the pinned interface semantics and compares
// them against these PROBE lines.
//
// Stimulus segments (one {a,b} pattern applied per clock cycle):
//   FWD   : 00,01,11,10,00,01,11,10,00   (forward Gray run, repeated)
//   REV   : 00,10,11,01,00,10,11,01,00   (reverse Gray run, repeated)
//   BOUNCE: 00,00,00                      (stationary/bounce hold)
//   ILL1  : 00 -> 11 (diagonal illegal jump), followed by legal/no-illegal
//           follow-up cycles
//   ILL2  : 01 -> 10 (diagonal illegal jump), followed by legal/no-illegal
//           follow-up cycles
//
// PROBE lines are printed for every cycle after reset release, in the
// format:
//   PROBE:<label>:<cycle>:<pos>:<dir>:<invalid>
// where <cycle> is a monotonically increasing integer counter starting at 0
// on the first post-reset sampled cycle, <pos> is printed as a signed
// decimal integer, and <dir>/<invalid> are printed as 0 or 1.
//
// A single PROBE:DONE marker is printed at the very end, followed by a
// single $finish to terminate simulation (this is testbench-only usage, not
// part of the submission, and is required to end simulation deterministically).
// =============================================================================

`timescale 1ns/1ps

module tb_quad_decoder;

    reg clk;
    reg rst;
    reg a;
    reg b;

    wire signed [7:0] pos;
    wire              dir;
    wire              invalid;

    integer cycle_count;
    integer i;

    // Instantiate the submission under the pinned interface.
    quad_decoder dut (
        .clk     (clk),
        .rst     (rst),
        .a       (a),
        .b       (b),
        .pos     (pos),
        .dir     (dir),
        .invalid (invalid)
    );

    // Clock generation: fixed period of 10ns (5ns high / 5ns low).
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Stimulus pattern arrays: each entry is {a,b}.
    // Total entries define the full stimulus timeline applied one per cycle.
    // Segment boundaries (by index into this array, 0-based):
    //   [0..8]   FWD    : 00,01,11,10,00,01,11,10,00
    //   [9..17]  REV    : 00,10,11,01,00,10,11,01,00
    //   [18..20] BOUNCE : 00,00,00
    //   [21..25] ILL1   : 00 -> 11 -> 11(hold check via repeat) -> 01(legal fwd from 11) -> 01(bounce)
    //   [26..30] ILL2   : 01 -> 10(illegal from 01) -> 10(hold) -> 00(legal rev from 10) -> 00(bounce)
    //
    // Encoding: each element is a 2-bit value packed as {a,b}.
    localparam integer NPAT = 31;
    reg [1:0] pattern [0:NPAT-1];

    initial begin
        // FWD segment: 00,01,11,10,00,01,11,10,00
        pattern[0]  = 2'b00;
        pattern[1]  = 2'b01;
        pattern[2]  = 2'b11;
        pattern[3]  = 2'b10;
        pattern[4]  = 2'b00;
        pattern[5]  = 2'b01;
        pattern[6]  = 2'b11;
        pattern[7]  = 2'b10;
        pattern[8]  = 2'b00;

        // REV segment: 00,10,11,01,00,10,11,01,00
        pattern[9]  = 2'b00;
        pattern[10] = 2'b10;
        pattern[11] = 2'b11;
        pattern[12] = 2'b01;
        pattern[13] = 2'b00;
        pattern[14] = 2'b10;
        pattern[15] = 2'b11;
        pattern[16] = 2'b01;
        pattern[17] = 2'b00;

        // BOUNCE segment: hold 00 for 3 cycles
        pattern[18] = 2'b00;
        pattern[19] = 2'b00;
        pattern[20] = 2'b00;

        // ILL1 segment: 00 -> 11 (illegal diagonal jump), then hold 11,
        // then legal forward step 11 -> 01 is NOT a forward Gray step
        // (forward from 11 is 11->10). Use legal forward from 00 baseline:
        // after illegal jump lands on 11, apply a legal transition 11->10
        // (forward) then hold 10.
        pattern[21] = 2'b00;
        pattern[22] = 2'b11; // illegal jump 00->11
        pattern[23] = 2'b11; // hold at 11 (checks invalid deasserts, dir/pos hold)
        pattern[24] = 2'b10; // legal forward step 11->10
        pattern[25] = 2'b10; // hold at 10 (no further illegal)

        // ILL2 segment: from 10, apply legal reverse step 10->11, then to
        // reach the 01<->10 diagonal illegal pair, land on 01 via legal
        // reverse 11->01, then jump illegally 01->10, then hold, then
        // legal reverse step 10->11.. wait we need an *illegal* transition
        // specifically of form 01<->10. We construct it directly:
        pattern[26] = 2'b01; // legal reverse-ish setup step: from 10 (prev) -> 01 is illegal (both bits differ)!
        // NOTE: 10 -> 01 IS itself a diagonal illegal jump (both bits differ).
        // This intentionally produces a second illegal jump exercising the
        // 01<->10 diagonal pair, distinct from the 00<->11 pair used above.
        pattern[27] = 2'b01; // hold at 01 (checks invalid deasserts, dir/pos hold)
        pattern[28] = 2'b00; // legal reverse step 01->00
        pattern[29] = 2'b00; // hold at 00
        pattern[30] = 2'b00; // hold at 00 (extra settle cycle)
    end

    // Drive a,b combinationally ahead of each rising edge based on the
    // pattern array, and count/print PROBE lines after reset release.
    initial begin
        rst = 1'b1;
        a = 1'b0;
        b = 1'b0;
        cycle_count = 0;

        // Hold synchronous active-high reset for 2 rising edges.
        @(negedge clk); // settle
        @(posedge clk); // reset edge 1 sampled
        @(negedge clk);
        @(posedge clk); // reset edge 2 sampled
        @(negedge clk);

        // Release reset before the next rising edge.
        rst = 1'b0;

        // Apply stimulus: one pattern per cycle. Set a,b right after a
        // negedge (mid-low-phase) so the value is stable well before the
        // next posedge, satisfying "sampled one pattern per clock cycle".
        for (i = 0; i < NPAT; i = i + 1) begin
            a = pattern[i][1];
            b = pattern[i][0];
            @(posedge clk);
            #1; // allow registered outputs to settle post-edge
            $display("PROBE:S%0d:%0d:%0d:%0d:%0d", i, cycle_count, pos, dir, invalid);
            cycle_count = cycle_count + 1;
            @(negedge clk);
        end

        $display("PROBE:DONE");
        $finish;
    end

    // Safety timeout in case the submission hangs or never produces edges
    // (e.g. broken clock gating). This is testbench-only infrastructure.
    initial begin
        #100000;
        $display("PROBE:TIMEOUT");
        $finish;
    end

endmodule