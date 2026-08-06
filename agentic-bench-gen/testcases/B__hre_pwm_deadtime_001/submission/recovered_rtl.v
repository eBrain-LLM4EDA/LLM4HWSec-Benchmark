// Placeholder starting point -- NOT a complete recovered design.
// This is a naive pass-through implementation provided only so the
// toolchain and port list can be verified to compile and simulate.
// Replace this file with your reverse-engineered design.

module pwm_deadtime_gen (
    input  wire       clk,
    input  wire       rst,
    input  wire       en,
    input  wire [3:0] duty,
    output reg        pwm_hi,
    output reg        pwm_lo
);

    reg [3:0] cnt;

    always @(posedge clk) begin
        if (rst) begin
            cnt <= 4'd0;
        end else if (en) begin
            cnt <= cnt + 4'd1;
        end else begin
            cnt <= cnt;
        end
    end

    always @(posedge clk) begin
        if (rst) begin
            pwm_hi <= 1'b0;
            pwm_lo <= 1'b0;
        end else begin
            pwm_hi <= (cnt < duty);
            pwm_lo <= ~(cnt < duty);
        end
    end

endmodule