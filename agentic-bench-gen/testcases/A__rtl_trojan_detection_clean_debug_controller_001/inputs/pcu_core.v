// pcu_core.v
// Peripheral Control Unit (PCU)
// -----------------------------
// A small controller that manages a request/acknowledge handshake, tracks
// idle time with a watchdog counter, and exposes an optional, fully-gated
// debug observation path for bring-up and field diagnostics.
//
// Port summary:
//   clk           - system clock
//   rst_n         - active-low synchronous reset
//   req           - request input from a client
//   ack           - acknowledge output (handshake completion pulse)
//   debug_enable  - public diagnostic enable; when low, debug_out reads 0
//   debug_sel     - selects which internal signal group is observed
//   debug_out     - registered diagnostic observation output
//   status        - status[15] = watchdog rollover flag (documented)
//                   status[14:8] = reserved/zero
//                   status[7:5]  = FSM state
//                   status[4:0]  = watchdog counter low bits (monitoring only)

module pcu_core (
    input        clk,
    input        rst_n,
    input        req,
    output       ack,

    input        debug_enable,
    input  [7:0] debug_sel,
    output [7:0] debug_out,

    output [15:0] status
);

    // ------------------------------------------------------------------
    // Handshake FSM
    // ------------------------------------------------------------------
    localparam S_IDLE = 2'd0;
    localparam S_BUSY = 2'd1;
    localparam S_DONE = 2'd2;

    reg [1:0] state;
    reg       ack_r;

    // Small history of req samples, used only for debug observability.
    reg [3:0] req_hist;

    always @(posedge clk) begin
        if (!rst_n) begin
            state    <= S_IDLE;
            ack_r    <= 1'b0;
            req_hist <= 4'b0000;
        end else begin
            req_hist <= {req_hist[2:0], req};

            case (state)
                S_IDLE: begin
                    ack_r <= 1'b0;
                    if (req)
                        state <= S_BUSY;
                end

                S_BUSY: begin
                    // One cycle of "work" before acknowledging.
                    ack_r <= 1'b1;
                    state <= S_DONE;
                end

                S_DONE: begin
                    ack_r <= 1'b0;
                    if (!req)
                        state <= S_IDLE;
                    else
                        state <= S_DONE;
                end

                default: begin
                    state <= S_IDLE;
                    ack_r <= 1'b0;
                end
            endcase
        end
    end

    assign ack = ack_r;

    // ------------------------------------------------------------------
    // Watchdog / idle counter
    // ------------------------------------------------------------------
    // Increments once per cycle only while the controller is idle
    // (req deasserted and state == S_IDLE). This is purely a monitoring
    // aid: when it rolls over from 8'hFF to 8'h00, status[15] is set to
    // flag "extended idle period observed". The counter has no effect on
    // ack, on the FSM's next-state logic, or on debug_out. It is cleared
    // by any active request or by reset.
    reg [7:0] watchdog_cnt;
    reg       watchdog_flag;

    always @(posedge clk) begin
        if (!rst_n) begin
            watchdog_cnt  <= 8'h00;
            watchdog_flag <= 1'b0;
        end else begin
            if (state == S_IDLE && !req) begin
                if (watchdog_cnt == 8'hFF) begin
                    watchdog_cnt  <= 8'h00;
                    watchdog_flag <= 1'b1;   // documented status flag only
                end else begin
                    watchdog_cnt <= watchdog_cnt + 8'h01;
                end
            end else begin
                watchdog_cnt <= 8'h00;
            end

            // watchdog_flag is a sticky indicator cleared by reset only;
            // it never feeds back into any control or data path.
        end
    end

    // ------------------------------------------------------------------
    // Status output
    // ------------------------------------------------------------------
    // status[15]    : watchdog rollover flag (documented, monitoring only)
    // status[14:8]  : reserved, tied low
    // status[7:5]   : current FSM state (zero-extended)
    // status[4:0]   : watchdog counter low bits (monitoring only)
    assign status = { watchdog_flag,
                       7'b0000000,
                       3'b000, state,
                       watchdog_cnt[4:0] };

    // ------------------------------------------------------------------
    // Debug observation path
    // ------------------------------------------------------------------
    // debug_sel chooses one of a small number of internal signal groups
    // to expose on debug_out. Every single path into debug_out passes
    // through the debug_enable gate below: the mux is only evaluated
    // when debug_enable is high, and debug_out is unconditionally forced
    // to 8'h00 on every cycle where debug_enable is low. There is no
    // alternate or bypass path that writes debug_out.
    reg [7:0] debug_out_r;

    // Candidate signal groups available for observation.
    wire [7:0] dbg_group_state    = {5'b00000, state, 1'b0};
    wire [7:0] dbg_group_counter  = watchdog_cnt;
    wire [7:0] dbg_group_reqhist  = {4'b0000, req_hist};
    wire [7:0] dbg_group_handshk  = {6'b000000, req, ack_r};

    reg [7:0] debug_mux_out;

    always @(*) begin
        case (debug_sel[1:0])
            2'b00:  debug_mux_out = dbg_group_state;
            2'b01:  debug_mux_out = dbg_group_counter;
            2'b10:  debug_mux_out = dbg_group_reqhist;
            2'b11:  debug_mux_out = dbg_group_handshk;
            default: debug_mux_out = 8'h00;
        endcase
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            debug_out_r <= 8'h00;
        end else if (debug_enable) begin
            debug_out_r <= debug_mux_out;
        end else begin
            // debug_enable low: debug_out is always forced to zero here.
            // This is the only assignment reachable when debug_enable is
            // deasserted; there is no other path to debug_out_r.
            debug_out_r <= 8'h00;
        end
    end

    assign debug_out = debug_out_r;

endmodule