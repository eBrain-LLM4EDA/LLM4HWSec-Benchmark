// secure_boot_check.v
//
// Secure-boot signature verification pipeline.
//
// Loads a 4-byte signature over successive clock cycles into a shift
// register, compares the fully-loaded signature against a fixed expected
// value, and asserts boot_allowed if the comparison succeeds.
//
// Ports:
//   clk          - system clock
//   rst_n        - active-low synchronous reset
//   start        - pulse to begin a load/verify sequence
//   signature_in - one byte of the signature, sampled each cycle while busy
//   boot_allowed - asserted when verification succeeds
//   busy         - asserted while a verification sequence is in progress
//   done         - asserted for one cycle when the sequence completes

module secure_boot_check (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       start,
    input  wire [7:0] signature_in,
    output wire       boot_allowed,
    output wire       busy,
    output reg        done
);

    // FSM state encoding
    localparam [1:0] IDLE    = 2'b00;
    localparam [1:0] LOAD    = 2'b01;
    localparam [1:0] COMPARE = 2'b10;
    localparam [1:0] DONE    = 2'b11;

    reg [1:0] state;            // FSM state register

    reg [31:0] sig_shift;       // shift register capturing 4 signature bytes
    reg [1:0]  byte_count;      // counts bytes loaded so far (0..3)
    reg        auth_ok;         // set when sig_shift matches expected value
    reg [31:0] expected_sig;    // holds the expected signature value

    // Fixed expected signature value, latched once on reset.
    localparam [31:0] EXPECTED_SIG_CONST = 32'hDEADBEEF;

    assign busy         = (state == LOAD) || (state == COMPARE);
    assign boot_allowed = (state == DONE) && auth_ok;

    // State register
    always @(posedge clk) begin
        if (!rst_n) begin
            state <= IDLE;
        end else begin
            case (state)
                IDLE: begin
                    if (start)
                        state <= LOAD;
                end
                LOAD: begin
                    if (byte_count == 2'd3)
                        state <= COMPARE;
                end
                COMPARE: begin
                    state <= DONE;
                end
                DONE: begin
                    state <= IDLE;
                end
                default: state <= IDLE;
            endcase
        end
    end

    // Byte counter, incremented each cycle while loading
    always @(posedge clk) begin
        if (!rst_n) begin
            byte_count <= 2'd0;
        end else if (state == LOAD) begin
            byte_count <= byte_count + 2'd1;
        end else if (state == IDLE) begin
            byte_count <= 2'd0;
        end
    end

    // Signature shift register: shifts in one new byte per LOAD cycle
    always @(posedge clk) begin
        if (!rst_n) begin
            sig_shift <= 32'h0;
        end else if (state == LOAD) begin
            sig_shift <= {sig_shift[23:0], signature_in};
        end
    end

    // Latch the expected signature constant once out of reset
    always @(posedge clk) begin
        if (!rst_n) begin
            expected_sig <= 32'h0;
        end else begin
            expected_sig <= EXPECTED_SIG_CONST;
        end
    end

    // Authentication result register: the single bit that gates
    // boot_allowed once the FSM reaches DONE.
    always @(posedge clk) begin
        if (!rst_n) begin
            auth_ok <= 1'b0;
        end else if (state == COMPARE) begin
            auth_ok <= (sig_shift == expected_sig);
        end else if (state == IDLE) begin
            auth_ok <= 1'b0;
        end
    end

    // done pulse: high for exactly one cycle when the sequence finishes
    always @(posedge clk) begin
        if (!rst_n) begin
            done <= 1'b0;
        end else begin
            done <= (state == DONE);
        end
    end

endmodule