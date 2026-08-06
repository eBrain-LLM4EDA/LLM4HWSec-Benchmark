// ============================================================
// Independently authored golden reference design.
// Module: reference_pwm_deadtime_gen
//
// Implements the timing contract pinned in public_spec.interface:
//   - 4-bit free-running counter cnt[3:0], period = 16 cycles.
//   - cnt increments on posedge clk when en=1, holds when en=0.
//   - Synchronous active-high reset, one-cycle latency: when rst is
//     sampled high at a rising edge, cnt becomes 0 and pwm_hi=0,
//     pwm_lo=0 are registered on the NEXT rising edge.
//   - pwm_hi(t+1) = 1 iff cnt(t) is in [2, duty-1]  (only when duty>=3;
//     otherwise pwm_hi never asserts for that duty).
//   - pwm_lo(t+1) = 1 iff cnt(t) is in [duty+2, 15] (only when duty<=13;
//     otherwise pwm_lo never asserts for that duty).
//   - Both outputs are registered (Moore) — one cycle latency behind
//     the cnt(t)/duty condition that determines them.
//
// This module is written independently of any obfuscated/gate-level
// artifact and serves purely as the ground-truth behavioral reference
// against which the submission is compared cycle-by-cycle.
// ============================================================

module reference_pwm_deadtime_gen (
    input  wire       clk,
    input  wire       rst,
    input  wire       en,
    input  wire [3:0] duty,
    output reg        pwm_hi,
    output reg        pwm_lo
);

    reg [3:0] cnt;

    // hi-side window candidate: cnt >= 2 AND cnt < duty (only meaningful if duty>=3)
    wire hi_next = (cnt >= 4'd2) && (cnt < duty);

    // lo-side window candidate: cnt >= duty+2 (only meaningful if duty<=13);
    // compute using a 5-bit sum to avoid 4-bit wraparound issues at duty=14,15
    wire [4:0] duty_plus2 = {1'b0, duty} + 5'd2;
    wire lo_next = ({1'b0, cnt} >= duty_plus2);

    always @(posedge clk) begin
        if (rst) begin
            cnt    <= 4'd0;
            pwm_hi <= 1'b0;
            pwm_lo <= 1'b0;
        end else begin
            // counter update
            if (en)
                cnt <= cnt + 4'd1;
            else
                cnt <= cnt;

            // registered outputs: function of cnt(t)/duty(t) sampled THIS edge,
            // observable starting the NEXT edge (Moore, one-cycle latency)
            pwm_hi <= hi_next;
            pwm_lo <= lo_next;
        end
    end

endmodule