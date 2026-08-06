// spn_top.v
// Top-level wrapper for the 16-bit, 4-round SPN cipher core.
//
// Instantiates spn_core and provides the external control/status
// handshake (start/done) used to drive one full encryption operation.
// This module is the intended entry point for simulation with
// iverilog/vvp.

module spn_top (
    input  wire        clk,
    input  wire         rst,
    input  wire         start,
    input  wire [15:0]  plaintext,
    input  wire [15:0]  key,
    output wire [15:0]  ciphertext,
    output wire         done
);

    // ------------------------------------------------------------------
    // Simple control FSM: IDLE -> RUN -> DONE -> IDLE
    //
    // IDLE: waiting for a start pulse.
    // RUN:  encryption in progress inside spn_core (core manages its
    //       own internal round counter over 4 clock cycles).
    // DONE: one-cycle pulse reflecting the core's done signal, then
    //       return to IDLE to accept the next start pulse.
    // ------------------------------------------------------------------
    localparam [1:0] ST_IDLE = 2'd0,
                      ST_RUN  = 2'd1,
                      ST_DONE = 2'd2;

    reg [1:0] state, state_n;

    wire core_done;
    wire [15:0] core_ciphertext;

    always @(*) begin
        state_n = state;
        case (state)
            ST_IDLE: if (start) state_n = ST_RUN;
            ST_RUN:  if (core_done) state_n = ST_DONE;
            ST_DONE: state_n = ST_IDLE;
            default: state_n = ST_IDLE;
        endcase
    end

    always @(posedge clk) begin
        if (rst)
            state <= ST_IDLE;
        else
            state <= state_n;
    end

    // ------------------------------------------------------------------
    // Core instantiation (named port connections only).
    // ------------------------------------------------------------------
    spn_core u_spn_core (
        .clk        (clk),
        .rst        (rst),
        .start      (start),
        .plaintext  (plaintext),
        .key        (key),
        .ciphertext (core_ciphertext),
        .done       (core_done)
    );

    assign ciphertext = core_ciphertext;
    assign done        = core_done;

endmodule