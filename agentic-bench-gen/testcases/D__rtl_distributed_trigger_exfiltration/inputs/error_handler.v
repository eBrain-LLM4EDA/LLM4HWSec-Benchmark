module error_handler (
    input wire clk,
    input wire rst_n,
    input wire error_in,
    output reg sticky_error
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sticky_error <= 1'b0;
        end else if (error_in) begin
            sticky_error <= 1'b1;
        end
    end

endmodule