// CRC-16/CCITT-FALSE serial generator (polynomial 0x1021, seed 0xFFFF, MSB-first, no reflection, no final XOR)
// Flattened gate-level netlist: XOR gates and D-type flip-flops with synchronous active-low reset

module crc16_serial (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        enable,
    input  wire        data_in,
    output wire [15:0] crc_out
);

    // Internal wires for flip-flop outputs (current state) and next-state logic
    wire [15:0] state;
    wire [15:0] next_state;

    // D-type flip-flops with synchronous active-low reset (seed = 0xFFFF)
    dff_sync_reset_low dff_0  (.clk(clk), .rst_n(rst_n), .d(next_state[0]),  .q(state[0]));
    dff_sync_reset_low dff_1  (.clk(clk), .rst_n(rst_n), .d(next_state[1]),  .q(state[1]));
    dff_sync_reset_low dff_2  (.clk(clk), .rst_n(rst_n), .d(next_state[2]),  .q(state[2]));
    dff_sync_reset_low dff_3  (.clk(clk), .rst_n(rst_n), .d(next_state[3]),  .q(state[3]));
    dff_sync_reset_low dff_4  (.clk(clk), .rst_n(rst_n), .d(next_state[4]),  .q(state[4]));
    dff_sync_reset_low dff_5  (.clk(clk), .rst_n(rst_n), .d(next_state[5]),  .q(state[5]));
    dff_sync_reset_low dff_6  (.clk(clk), .rst_n(rst_n), .d(next_state[6]),  .q(state[6]));
    dff_sync_reset_low dff_7  (.clk(clk), .rst_n(rst_n), .d(next_state[7]),  .q(state[7]));
    dff_sync_reset_low dff_8  (.clk(clk), .rst_n(rst_n), .d(next_state[8]),  .q(state[8]));
    dff_sync_reset_low dff_9  (.clk(clk), .rst_n(rst_n), .d(next_state[9]),  .q(state[9]));
    dff_sync_reset_low dff_10 (.clk(clk), .rst_n(rst_n), .d(next_state[10]), .q(state[10]));
    dff_sync_reset_low dff_11 (.clk(clk), .rst_n(rst_n), .d(next_state[11]), .q(state[11]));
    dff_sync_reset_low dff_12 (.clk(clk), .rst_n(rst_n), .d(next_state[12]), .q(state[12]));
    dff_sync_reset_low dff_13 (.clk(clk), .rst_n(rst_n), .d(next_state[13]), .q(state[13]));
    dff_sync_reset_low dff_14 (.clk(clk), .rst_n(rst_n), .d(next_state[14]), .q(state[14]));
    dff_sync_reset_low dff_15 (.clk(clk), .rst_n(rst_n), .d(next_state[15]), .q(state[15]));

    // Feedback term: data_in XOR state[15] (MSB of current state)
    wire feedback;
    xor_gate xor_fb (.a(data_in), .b(state[15]), .y(feedback));

    // Next-state logic for each bit (LFSR with polynomial 0x1021, MSB-first shifting)
    // next_state[0]  = feedback
    // next_state[1]  = state[0]
    // next_state[2]  = state[1]
    // next_state[3]  = state[2]
    // next_state[4]  = state[3]
    // next_state[5]  = state[4]  XOR feedback   (tap at bit 5)
    // next_state[6]  = state[5]
    // next_state[7]  = state[6]
    // next_state[8]  = state[7]
    // next_state[9]  = state[8]
    // next_state[10] = state[9]
    // next_state[11] = state[10]
    // next_state[12] = state[11] XOR feedback   (tap at bit 12)
    // next_state[13] = state[12]
    // next_state[14] = state[13]
    // next_state[15] = state[14]

    assign next_state[0]  = feedback;
    assign next_state[1]  = state[0];
    assign next_state[2]  = state[1];
    assign next_state[3]  = state[2];
    assign next_state[4]  = state[3];

    wire tap5;
    xor_gate xor_tap5 (.a(state[4]), .b(feedback), .y(tap5));
    assign next_state[5]  = tap5;

    assign next_state[6]  = state[5];
    assign next_state[7]  = state[6];
    assign next_state[8]  = state[7];
    assign next_state[9]  = state[8];
    assign next_state[10] = state[9];
    assign next_state[11] = state[10];

    wire tap12;
    xor_gate xor_tap12 (.a(state[11]), .b(feedback), .y(tap12));
    assign next_state[12] = tap12;

    assign next_state[13] = state[12];
    assign next_state[14] = state[13];
    assign next_state[15] = state[14];

    // Output is the current state (no final XOR)
    assign crc_out = state;

endmodule

// Synchronous D flip-flop with active-low reset (reset value = 1)
module dff_sync_reset_low (
    input  wire clk,
    input  wire rst_n,
    input  wire d,
    output reg  q
);
    always @(posedge clk) begin
        if (!rst_n)
            q <= 1'b1;
        else
            q <= d;
    end
endmodule

// 2-input XOR gate
module xor_gate (
    input  wire a,
    input  wire b,
    output wire y
);
    assign y = a ^ b;
endmodule