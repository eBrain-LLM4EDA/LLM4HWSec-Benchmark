// =============================================================================
// scalar_mult_ctrl.v
//
// Double-and-add controller for a compact scalar-multiplication datapath.
//
// Processes a 16-bit scalar from bit index 15 down to bit index 0. For each
// bit index, the controller always performs a DOUBLE operation on the
// running accumulator. If the current scalar bit is 1, the controller also
// performs an ADD operation (accumulating a fixed base point into the
// running accumulator) before moving on to the next bit index. If the
// current scalar bit is 0, the controller proceeds directly to the next
// bit index without performing an ADD.
//
// Debug/analysis ports (state, cycle_count, cycle_count_valid) are provided
// purely to make the controller's internal behavior observable during
// simulation; they are not part of the production interface.
// =============================================================================

module scalar_mult_ctrl (
    input  wire        clk,
    input  wire        rst_n,        // active-low, synchronous reset
    input  wire        start,        // 1-cycle pulse while idle
    input  wire [15:0] scalar,       // MSB-first; bit 15 processed first

    output reg         done,         // 1-cycle Moore pulse
    output reg  [63:0] result_x,
    output reg  [63:0] result_y,

    // Debug / analysis-only outputs
    output reg  [2:0]  state,
    output reg  [15:0] cycle_count,
    output reg         cycle_count_valid
);

    // -------------------------------------------------------------------
    // FSM state encoding
    // -------------------------------------------------------------------
    localparam S_IDLE      = 3'd0;
    localparam S_DOUBLE    = 3'd1;
    localparam S_ADD       = 3'd2;
    localparam S_NEXT_BIT  = 3'd3;
    localparam S_DONE      = 3'd4;

    // -------------------------------------------------------------------
    // Internal registers
    // -------------------------------------------------------------------
    reg  [4:0]  bit_idx;       // 0..15, signed use via wrap; -1 detected via underflow flag
    reg         bit_idx_valid; // true while bit_idx is a valid 0..15 index

    reg  [63:0] acc_x, acc_y;      // running accumulator (result of DOUBLE/ADD chain)
    reg  [63:0] base_x, base_y;    // fixed base point fed to ADD

    // Handshake with field_datapath
    reg         dp_op_start;
    reg         dp_op_is_add;
    reg  [63:0] dp_in_x, dp_in_y;
    reg  [63:0] dp_add_x, dp_add_y;
    wire [63:0] dp_out_x, dp_out_y;
    wire        dp_op_done;

    wire cur_bit = bit_idx_valid ? scalar[bit_idx[3:0]] : 1'b0;

    // -------------------------------------------------------------------
    // Fixed base point used for ADD (illustrative constant, not secret)
    // -------------------------------------------------------------------
    localparam [63:0] BASE_X = 64'h0000_0000_0000_0005;
    localparam [63:0] BASE_Y = 64'h0000_0000_0000_0007;

    // -------------------------------------------------------------------
    // field_datapath instance: shared DOUBLE/ADD execution unit
    // -------------------------------------------------------------------
    field_datapath u_datapath (
        .clk       (clk),
        .rst_n      (rst_n),
        .op_start   (dp_op_start),
        .op_is_add  (dp_op_is_add),
        .in_x       (dp_in_x),
        .in_y       (dp_in_y),
        .add_x      (dp_add_x),
        .add_y      (dp_add_y),
        .out_x      (dp_out_x),
        .out_y      (dp_out_y),
        .op_done    (dp_op_done)
    );

    // -------------------------------------------------------------------
    // Main sequential FSM
    // -------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            state             <= S_IDLE;
            done              <= 1'b0;
            result_x          <= 64'd0;
            result_y          <= 64'd0;
            cycle_count       <= 16'd0;
            cycle_count_valid <= 1'b0;

            bit_idx           <= 5'd0;
            bit_idx_valid     <= 1'b0;

            acc_x             <= 64'd0;
            acc_y             <= 64'd0;
            base_x            <= 64'd0;
            base_y            <= 64'd0;

            dp_op_start       <= 1'b0;
            dp_op_is_add      <= 1'b0;
            dp_in_x           <= 64'd0;
            dp_in_y           <= 64'd0;
            dp_add_x          <= 64'd0;
            dp_add_y          <= 64'd0;
        end else begin
            // done and cycle_count_valid are pulsed for exactly one cycle
            done              <= 1'b0;
            cycle_count_valid <= 1'b0;
            dp_op_start       <= 1'b0;

            case (state)

                // -----------------------------------------------------
                S_IDLE: begin
                    if (start) begin
                        // Seed accumulator with an identity-like starting
                        // point and the fixed base point for ADD.
                        acc_x         <= 64'd1;
                        acc_y         <= 64'd1;
                        base_x        <= BASE_X;
                        base_y        <= BASE_Y;

                        bit_idx       <= 5'd15;
                        bit_idx_valid <= 1'b1;

                        cycle_count   <= 16'd1;

                        // Kick off DOUBLE for bit 15
                        dp_op_start   <= 1'b1;
                        dp_op_is_add  <= 1'b0;
                        dp_in_x       <= 64'd1;
                        dp_in_y       <= 64'd1;
                        dp_add_x      <= BASE_X;
                        dp_add_y      <= BASE_Y;

                        state         <= S_DOUBLE;
                    end
                end

                // -----------------------------------------------------
                // DOUBLE is performed unconditionally for every bit index.
                S_DOUBLE: begin
                    cycle_count <= cycle_count + 16'd1;

                    if (dp_op_done) begin
                        acc_x <= dp_out_x;
                        acc_y <= dp_out_y;

                        if (cur_bit) begin
                            // Scalar bit is set: perform the ADD operation
                            // this bit index.
                            dp_op_start  <= 1'b1;
                            dp_op_is_add <= 1'b1;
                            dp_in_x      <= dp_out_x;
                            dp_in_y      <= dp_out_y;
                            dp_add_x     <= base_x;
                            dp_add_y     <= base_y;
                            state        <= S_ADD;
                        end else begin
                            // Scalar bit is clear: skip ADD entirely and
                            // proceed directly to the next bit index.
                            state <= S_NEXT_BIT;
                        end
                    end
                end

                // -----------------------------------------------------
                // ADD is performed only when the current scalar bit is 1.
                S_ADD: begin
                    cycle_count <= cycle_count + 16'd1;

                    if (dp_op_done) begin
                        acc_x <= dp_out_x;
                        acc_y <= dp_out_y;
                        state <= S_NEXT_BIT;
                    end
                end

                // -----------------------------------------------------
                S_NEXT_BIT: begin
                    cycle_count <= cycle_count + 16'd1;

                    if (bit_idx == 5'd0) begin
                        // Just processed bit index 0; nothing left to do.
                        bit_idx_valid <= 1'b0;
                        state         <= S_DONE;
                    end else begin
                        bit_idx <= bit_idx - 5'd1;

                        // Kick off DOUBLE for the next bit index.
                        dp_op_start  <= 1'b1;
                        dp_op_is_add <= 1'b0;
                        dp_in_x      <= acc_x;
                        dp_in_y      <= acc_y;
                        dp_add_x     <= base_x;
                        dp_add_y     <= base_y;

                        state <= S_DOUBLE;
                    end
                end

                // -----------------------------------------------------
                S_DONE: begin
                    result_x          <= acc_x;
                    result_y          <= acc_y;
                    done              <= 1'b1;
                    cycle_count_valid <= 1'b1;
                    state             <= S_IDLE;
                end

                default: begin
                    state <= S_IDLE;
                end

            endcase
        end
    end

endmodule