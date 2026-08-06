// key_loader_ctrl.v
//
// Key-loading controller for a cryptographic subsystem.
// Loads a 32-bit key register from a bus and supports an emergency
// zeroize function to clear the key register on demand.

module key_loader_ctrl(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [31:0] bus_data,
    input  wire        bus_wr,
    input  wire        zeroize,
    output wire         bus_busy,
    output wire [31:0] key_q
);

    // ------------------------------------------------------------
    // Bus busy tracking
    //
    // A bus write transaction is considered in-flight for a short,
    // fixed number of cycles after bus_wr is asserted. busy_cnt
    // holds the number of remaining busy cycles.
    // ------------------------------------------------------------
    localparam BUSY_CYCLES = 3'd3;

    reg [2:0] busy_cnt;

    assign bus_busy = (busy_cnt != 3'd0);

    always @(posedge clk) begin
        if (!rst_n) begin
            busy_cnt <= 3'd0;
        end else if (bus_wr) begin
            busy_cnt <= BUSY_CYCLES;
        end else if (busy_cnt != 3'd0) begin
            busy_cnt <= busy_cnt - 3'd1;
        end
    end

    // ------------------------------------------------------------
    // Key register
    //
    // key_q is loaded from bus_data on a bus write, and is intended
    // to be forced to all-zero whenever zeroize is asserted.
    // ------------------------------------------------------------
    reg [31:0] key_q_r;
    reg [31:0] key_q_next;

    assign key_q = key_q_r;

    // zeroize gating logic
    wire zeroize_mask;
    assign zeroize_mask = zeroize & ~bus_busy;

    always @(*) begin : zeroize_block
        if (zeroize_mask)
            key_q_next = 32'b0;
        else if (bus_wr)
            key_q_next = bus_data;
        else
            key_q_next = key_q_r;
    end

    always @(posedge clk) begin
        if (!rst_n)
            key_q_r <= 32'b0;
        else
            key_q_r <= key_q_next;
    end

endmodule