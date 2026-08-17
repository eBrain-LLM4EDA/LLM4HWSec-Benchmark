// =============================================================================
// field_datapath.v
//
// Multi-cycle field datapath shared by the scalar-multiplication controller.
// Implements two operations on a pair of 64-bit coordinate registers:
//
//   - DOUBLE (op_is_add == 0): produces a new (out_x, out_y) derived only
//     from (in_x, in_y). Takes DBL_CYCLES clock cycles to complete.
//
//   - ADD    (op_is_add == 1): produces a new (out_x, out_y) derived from
//     (in_x, in_y) and (add_x, add_y). Takes ADD_CYCLES clock cycles to
//     complete (intentionally more cycles than DOUBLE to model a more
//     complex operation).
//
// The arithmetic used here is a simplified, deterministic placeholder for a
// real elliptic-curve field operation: it combines the inputs with fixed
// shift/add/xor steps modulo a fixed constant so that results are
// reproducible and easy to check against a reference computation. It is not
// intended to model a specific curve.
// =============================================================================

module field_datapath (
    input  wire        clk,
    input  wire        rst_n,      // active-low, synchronous reset

    input  wire        op_start,   // 1-cycle pulse to begin an operation
    input  wire        op_is_add,  // 0 = DOUBLE, 1 = ADD (sampled at op_start)

    input  wire [63:0] in_x,
    input  wire [63:0] in_y,
    input  wire [63:0] add_x,      // used only when op_is_add == 1
    input  wire [63:0] add_y,      // used only when op_is_add == 1

    output reg  [63:0] out_x,
    output reg  [63:0] out_y,
    output reg          op_done     // 1-cycle pulse when result is valid
);

    // -------------------------------------------------------------------
    // Fixed latency for each operation kind.
    // -------------------------------------------------------------------
    localparam [3:0] DBL_CYCLES = 4'd3;
    localparam [3:0] ADD_CYCLES = 4'd4;

    // Fixed modulus-like constant used to keep intermediate values bounded.
    localparam [63:0] FIELD_MOD = 64'hFFFF_FFFF_FFFF_FFC5;

    // -------------------------------------------------------------------
    // Internal state
    // -------------------------------------------------------------------
    localparam S_IDLE = 1'b0;
    localparam S_BUSY = 1'b1;

    reg         busy_state;
    reg         latched_is_add;
    reg  [63:0] latched_in_x, latched_in_y;
    reg  [63:0] latched_add_x, latched_add_y;
    reg  [3:0]  cycle_ctr;
    reg  [3:0]  target_cycles;

    // -------------------------------------------------------------------
    // Combinational result computation (simplified deterministic update)
    // -------------------------------------------------------------------
    reg [63:0] comb_out_x;
    reg [63:0] comb_out_y;

    always @* begin
        if (latched_is_add) begin
            // ADD-style update: combine both point representations.
            comb_out_x = (latched_in_x + add_x + (latched_in_y ^ add_y)) % FIELD_MOD;
            comb_out_y = ((latched_in_y + add_y) ^ (latched_in_x + add_x)) % FIELD_MOD;
        end else begin
            // DOUBLE-style update: combine a point representation with itself.
            comb_out_x = ((latched_in_x << 1) + latched_in_y) % FIELD_MOD;
            comb_out_y = ((latched_in_y << 1) ^ latched_in_x) % FIELD_MOD;
        end
    end

    // -------------------------------------------------------------------
    // Sequential control
    // -------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            busy_state     <= S_IDLE;
            op_done        <= 1'b0;
            out_x          <= 64'd0;
            out_y          <= 64'd0;

            latched_is_add <= 1'b0;
            latched_in_x   <= 64'd0;
            latched_in_y   <= 64'd0;
            latched_add_x  <= 64'd0;
            latched_add_y  <= 64'd0;

            cycle_ctr      <= 4'd0;
            target_cycles  <= 4'd0;
        end else begin
            op_done <= 1'b0;

            case (busy_state)

                S_IDLE: begin
                    if (op_start) begin
                        latched_is_add <= op_is_add;
                        latched_in_x   <= in_x;
                        latched_in_y   <= in_y;
                        latched_add_x  <= add_x;
                        latched_add_y  <= add_y;

                        target_cycles  <= op_is_add ? ADD_CYCLES : DBL_CYCLES;
                        cycle_ctr      <= 4'd1;

                        busy_state     <= S_BUSY;
                    end
                end

                S_BUSY: begin
                    if (cycle_ctr >= target_cycles) begin
                        out_x      <= comb_out_x;
                        out_y      <= comb_out_y;
                        op_done    <= 1'b1;
                        busy_state <= S_IDLE;
                    end else begin
                        cycle_ctr <= cycle_ctr + 4'd1;
                    end
                end

                default: begin
                    busy_state <= S_IDLE;
                end

            endcase
        end
    end

endmodule