`timescale 1ns / 1ps

module precharge_bus_wrapper (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       load,
    input  wire [7:0] data_in,
    output reg  [7:0] dbus,
    output reg        valid
);

    // Simple 3-state transfer sequencer.
    localparam ST_IDLE      = 2'b00;
    localparam ST_PRECHARGE = 2'b01;
    localparam ST_EVALUATE  = 2'b10;

    reg [1:0] state;
    reg [7:0] data_latched;

    always @(posedge clk) begin
        if (!rst_n) begin
            state        <= ST_IDLE;
            dbus         <= 8'h00;
            valid        <= 1'b0;
            data_latched <= 8'h00;
        end else begin
            case (state)
                ST_IDLE: begin
                    valid <= 1'b0;
                    if (load) begin
                        data_latched <= data_in;
                        state        <= ST_PRECHARGE;
                    end
                end

                ST_PRECHARGE: begin
                    dbus  <= 8'h00;
                    valid <= 1'b0;
                    state <= ST_EVALUATE;
                end

                ST_EVALUATE: begin
                    dbus  <= data_latched;
                    valid <= 1'b1;
                    state <= ST_IDLE;
                end

                default: begin
                    state <= ST_IDLE;
                end
            endcase
        end
    end

endmodule