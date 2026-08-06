// debug_controller.v
// Compact debug controller with gated diagnostic paths.
// All debug functionality is enabled only when debug_enable is asserted.
// No hidden triggers or undocumented payloads.

module debug_controller (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        debug_enable,   // documented enable for debug features
    input  wire [7:0]  data_in,
    output reg  [7:0]  status_out,
    output reg         alert
);

    // Internal registers
    reg [15:0] counter;
    reg [7:0]  debug_reg;
    reg [3:0]  state;

    // Low-activity counter: increments only on specific data_in values
    wire counter_inc;
    assign counter_inc = (data_in == 8'hA5) || (data_in == 8'h5A);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            counter <= 16'd0;
        end else if (counter_inc) begin
            counter <= counter + 1;
        end
    end

    // State machine for debug operations
    localparam IDLE       = 4'd0;
    localparam CAPTURE    = 4'd1;
    localparam PROCESS    = 4'd2;
    localparam OUTPUT     = 4'd3;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state     <= IDLE;
            debug_reg <= 8'd0;
            status_out <= 8'd0;
            alert     <= 1'b0;
        end else begin
            case (state)
                IDLE: begin
                    alert <= 1'b0;
                    if (debug_enable && (data_in == 8'hDB)) begin
                        state <= CAPTURE;
                    end
                end

                CAPTURE: begin
                    if (debug_enable) begin
                        debug_reg <= data_in;
                        state <= PROCESS;
                    end else begin
                        state <= IDLE;
                    end
                end

                PROCESS: begin
                    if (debug_enable) begin
                        // Diagnostic processing: XOR with counter LSB
                        debug_reg <= debug_reg ^ counter[7:0];
                        state <= OUTPUT;
                    end else begin
                        state <= IDLE;
                    end
                end

                OUTPUT: begin
                    if (debug_enable) begin
                        status_out <= debug_reg;
                        // Rare alert condition: only when counter reaches a specific value
                        if (counter == 16'hDEAD) begin
                            alert <= 1'b1;
                        end
                        state <= IDLE;
                    end else begin
                        state <= IDLE;
                    end
                end

                default: state <= IDLE;
            endcase
        end
    end

endmodule