module crc16_serial (
    input wire clk,
    input wire rst_n,
    input wire enable,
    input wire data_in,
    output reg [15:0] crc_out
);

    // CRC-16/CCITT-FALSE: polynomial 0x1021, seed 0xFFFF, MSB-first, no reflection, no final XOR
    // Moore-type output: crc_out is the registered state, updated one cycle after enabled input

    reg [15:0] crc_state;

    always @(posedge clk) begin
        if (!rst_n) begin
            // Synchronous active-low reset: set state to seed 0xFFFF
            crc_state <= 16'hFFFF;
        end else if (enable) begin
            // MSB-first shift: new bit combined with MSB of current state
            // Polynomial: x^16 + x^12 + x^5 + 1 (0x1021)
            // Feedback = data_in ^ crc_state[15]
            // Shift left by 1, XOR polynomial if feedback is 1
            if (data_in ^ crc_state[15]) begin
                crc_state <= {crc_state[14:0], 1'b0} ^ 16'h1021;
            end else begin
                crc_state <= {crc_state[14:0], 1'b0};
            end
        end
        // else: hold state when enable is low
    end

    // crc_out always reflects the current registered state (Moore output)
    always @(posedge clk) begin
        crc_out <= crc_state;
    end

endmodule