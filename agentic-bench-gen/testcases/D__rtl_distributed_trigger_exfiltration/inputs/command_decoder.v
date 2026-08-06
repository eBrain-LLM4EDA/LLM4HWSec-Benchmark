module command_decoder (
    input wire [3:0] command,
    output wire match,
    output wire [3:0] decoded
);

    assign match = (command == 4'b1010);
    assign decoded = command;

endmodule