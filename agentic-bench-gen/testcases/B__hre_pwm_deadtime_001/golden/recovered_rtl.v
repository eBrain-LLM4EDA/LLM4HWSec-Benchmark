// ============================================================
// pwm_deadtime_gen
//
// Recovered word-level reconstruction of the legacy half-bridge
// gate-driver PWM block described in gate_netlist.v / obfuscated_rtl.v.
//
// Behavior (per design_brief.md / pinned interface contract):
//   - Free-running 4-bit counter cnt[3:0], period = 16 cycles.
//   - Synchronous active-high reset: on rst=1 sampled at a posedge,
//     the NEXT posedge sets cnt=0, pwm_hi=0, pwm_lo=0 (one cycle
//     reset latency).
//   - Counter increments every cycle when en=1; holds when en=0.
//   - pwm_hi and pwm_lo are Moore (registered) outputs: they are a
//     registered function of the CURRENT cnt/duty, i.e. they change
//     one cycle after the counter condition is sampled.
//       stateA (hi-side window) = (cnt >= 2) && (cnt < duty)
//       stateB (lo-side window) = (cnt >= duty + 2)
//     These are exactly the stateA/stateB definitions recovered from
//     obfuscated_rtl.v (n1: cnt>=2, n2: cnt<duty, stateA=n1&n2;
//     n3: cnt>=duty+2, n4: cnt<=15 (always true for 4-bit cnt),
//     stateB = n3 & n4 = n3), reproduced here at the word level
//     instead of the flattened single-bit nets.
//   - This yields exactly two dead-time cycles at the top of the
//     period (cnt=0,1) before pwm_hi can assert, and exactly two
//     dead-time cycles after pwm_hi's window closes (cnt=duty,
//     duty+1) before pwm_lo can assert.
//   - For duty<=2, pwm_hi never asserts. For duty>=14, pwm_lo never
//     asserts (duty+2 computed in 5-bit arithmetic to avoid wraparound
//     aliasing at duty=14,15).
// ============================================================

module pwm_deadtime_gen (
    input  wire       clk,
    input  wire       rst,
    input  wire       en,
    input  wire [3:0] duty,
    output reg        pwm_hi,
    output reg        pwm_lo
);

    reg [3:0] cnt;

    // Combinational window conditions based on the CURRENT (this-cycle)
    // counter value and duty. These feed the registered outputs below,
    // giving the required one-cycle Moore latency.
    wire stateA; // hi-side window candidate
    wire stateB; // lo-side window candidate

    // Use 5-bit arithmetic for duty+2 so no wraparound aliasing occurs
    // at duty=14 (16, always > any 4-bit cnt -> stateB never true) or
    // duty=15 (17, likewise never true).
    wire [4:0] duty_plus2 = {1'b0, duty} + 5'd2;

    assign stateA = (cnt >= 4'd2) && (cnt < duty);
    assign stateB = ({1'b0, cnt} >= duty_plus2);

    // Counter update: synchronous reset, hold on !en, increment on en.
    always @(posedge clk) begin
        if (rst) begin
            cnt <= 4'd0;
        end else if (en) begin
            cnt <= cnt + 4'd1;
        end else begin
            cnt <= cnt;
        end
    end

    // Registered (Moore) output stage: one cycle behind stateA/stateB.
    always @(posedge clk) begin
        if (rst) begin
            pwm_hi <= 1'b0;
            pwm_lo <= 1'b0;
        end else begin
            pwm_hi <= stateA;
            pwm_lo <= stateB;
        end
    end

endmodule