`timescale 1ns / 1ps

module design_tb;

    reg [7:0] data_in;
    wire parity_error;

    // Instantiate the design under test
    top uut (
        .data_in(data_in),
        .parity_error(parity_error)
    );

    initial begin
        $dumpfile("design_tb.vcd");
        $dumpvars(0, design_tb);

        // Test vectors that exercise normal parity behavior
        // None of these vectors match the hidden trigger pattern

        // All zeros -> even parity (0 ones) -> parity_error should be 0
        data_in = 8'b00000000;
        #10;

        // Single one -> odd parity -> parity_error should be 1
        data_in = 8'b00000001;
        #10;

        // Two ones -> even parity -> parity_error should be 0
        data_in = 8'b00000011;
        #10;

        // Three ones -> odd parity -> parity_error should be 1
        data_in = 8'b00000111;
        #10;

        // Four ones -> even parity -> parity_error should be 0
        data_in = 8'b00001111;
        #10;

        // Five ones -> odd parity -> parity_error should be 1
        data_in = 8'b00011111;
        #10;

        // Six ones -> even parity -> parity_error should be 0
        data_in = 8'b00111111;
        #10;

        // Seven ones -> odd parity -> parity_error should be 1
        data_in = 8'b01111111;
        #10;

        // Eight ones -> even parity -> parity_error should be 0
        data_in = 8'b11111111;
        #10;

        // Additional random-looking vectors that do not trigger the Trojan
        data_in = 8'b01010101;
        #10;
        data_in = 8'b00110011;
        #10;
        data_in = 8'b11001100;
        #10;
        data_in = 8'b10000000;
        #10;
        data_in = 8'b01000000;
        #10;
        data_in = 8'b00100000;
        #10;
        data_in = 8'b00010000;
        #10;
        data_in = 8'b00001000;
        #10;
        data_in = 8'b00000100;
        #10;
        data_in = 8'b00000010;
        #10;

        $finish;
    end

endmodule