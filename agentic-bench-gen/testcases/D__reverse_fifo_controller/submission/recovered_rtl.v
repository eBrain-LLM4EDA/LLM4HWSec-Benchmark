// Naive baseline submission for reverse_fifo_controller
// This is a trivial, non-functional implementation that will fail evaluation.
// Participants must replace this with their reconstructed RTL.

module fifo_controller (
    input         clk,
    input         rst,
    input  [7:0]  write_data,
    input         write_en,
    input         read_en,
    output [7:0]  read_data,
    output        full,
    output        empty
);

    assign read_data = 8'b0;
    assign full      = 1'b0;
    assign empty     = 1'b0;

endmodule