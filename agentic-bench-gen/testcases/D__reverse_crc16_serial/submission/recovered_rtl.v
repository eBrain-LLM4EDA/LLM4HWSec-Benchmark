// Naive baseline submission for reverse_crc16_serial
// This module is intentionally incorrect: it implements a simple shift register
// with no CRC polynomial feedback, wrong seed (0x0000 instead of 0xFFFF),
// and no XOR network. It will fail all evaluation metrics.

module crc16_serial (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        enable,
    input  wire        data_in,
    output wire [15:0] crc_out
);

    reg [15:0] shift_reg;

    always @(posedge clk) begin
        if (!rst_n) begin
            shift_reg <= 16'h0000;  // Wrong seed: should be 16'hFFFF
        end else if (enable) begin
            // Simple shift: data_in enters LSB, bits shift left
            shift_reg <= {shift_reg[14:0], data_in};
        end
    end

    assign crc_out = shift_reg;

endmodule