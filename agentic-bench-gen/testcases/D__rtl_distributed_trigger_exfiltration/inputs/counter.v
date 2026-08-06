module counter (
    input wire clk,
    input wire rst_n,
    input wire enable,
    output wire terminal_count
);

    reg [7:0] count;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= 8'h00;
        end else if (enable) begin
            count <= count + 1;
        end
    end

    assign terminal_count = (count == 8'hFF);

endmodule