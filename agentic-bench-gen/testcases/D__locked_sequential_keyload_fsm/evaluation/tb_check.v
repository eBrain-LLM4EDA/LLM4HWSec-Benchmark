`timescale 1ns / 1ps

module tb_check;

    reg clk;
    reg rst_n;
    reg key_in;
    reg data_in;
    wire data_out;

    // Instantiate the design under test
    top dut (
        .clk(clk),
        .rst_n(rst_n),
        .key_in(key_in),
        .data_in(data_in),
        .data_out(data_out)
    );

    // Clock generation: 10 ns period
    always #5 clk = ~clk;

    // Read the key from plusarg
    reg [3:0] key_bits;
    initial begin
        reg [1023:0] key_str;
        if ($value$plusargs("KEY=%s", key_str)) begin
            // Convert string to 4-bit vector
            key_bits[3] = (key_str[0] == "1") ? 1'b1 : 1'b0;
            key_bits[2] = (key_str[1] == "1") ? 1'b1 : 1'b0;
            key_bits[1] = (key_str[2] == "1") ? 1'b1 : 1'b0;
            key_bits[0] = (key_str[3] == "1") ? 1'b1 : 1'b0;
        end else begin
            $display("ERROR: KEY plusarg not provided");
            $finish;
        end
    end

    // Main test sequence
    integer i;
    initial begin
        // Initialize
        clk = 0;
        rst_n = 0;
        key_in = 0;
        data_in = 0;

        // Apply reset for a few cycles
        #20 rst_n = 1;  // de-assert reset after 20 ns

        // Wait one clock edge before starting key loading
        @(posedge clk);

        // Load the 4-bit key, LSB first (as per design brief)
        for (i = 0; i < 4; i = i + 1) begin
            key_in = key_bits[i];
            @(posedge clk);
        end

        // After loading, key_in is don't-care; set to 0
        key_in = 0;

        // Now toggle data_in and observe data_out
        // We'll drive a simple pattern: 0, 1, 0, 1, 1, 0, 1, 1
        // and print data_out at each posedge
        repeat(2) @(posedge clk); // wait a couple cycles

        data_in = 1; @(posedge clk);
        $display("[SR2_CROSSCHECK] %b", data_out);
        data_in = 0; @(posedge clk);
        $display("[SR2_CROSSCHECK] %b", data_out);
        data_in = 1; @(posedge clk);
        $display("[SR2_CROSSCHECK] %b", data_out);
        data_in = 1; @(posedge clk);
        $display("[SR2_CROSSCHECK] %b", data_out);
        data_in = 0; @(posedge clk);
        $display("[SR2_CROSSCHECK] %b", data_out);
        data_in = 1; @(posedge clk);
        $display("[SR2_CROSSCHECK] %b", data_out);
        data_in = 1; @(posedge clk);
        $display("[SR2_CROSSCHECK] %b", data_out);
        data_in = 0; @(posedge clk);
        $display("[SR2_CROSSCHECK] %b", data_out);

        $finish;
    end

endmodule