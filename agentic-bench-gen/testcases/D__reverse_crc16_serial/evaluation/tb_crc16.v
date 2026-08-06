`timescale 1ns / 1ps

module tb_crc16;

    reg clk;
    reg rst_n;
    reg enable;
    reg data_in;
    wire [15:0] crc_out_dut;
    wire [15:0] crc_out_ref;

    // Instantiate DUT
    crc16_serial dut (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .data_in(data_in),
        .crc_out(crc_out_dut)
    );

    // Reference model: CRC-16/CCITT-FALSE
    reg [15:0] ref_state;
    assign crc_out_ref = ref_state;

    always @(posedge clk) begin
        if (!rst_n) begin
            ref_state <= 16'hFFFF;
        end else if (enable) begin
            // MSB-first shift: feedback = data_in ^ ref_state[15]
            // Polynomial 0x1021: taps at bits 5 and 12 (0-indexed from MSB)
            // next_state[0] = feedback
            // next_state[1] = ref_state[0]
            // ...
            // next_state[5] = ref_state[4] ^ feedback
            // ...
            // next_state[12] = ref_state[11] ^ feedback
            // ...
            // next_state[15] = ref_state[14]
            reg feedback;
            feedback = data_in ^ ref_state[15];
            ref_state <= {
                ref_state[14:12],
                ref_state[11] ^ feedback,
                ref_state[10:5],
                ref_state[4] ^ feedback,
                ref_state[3:0],
                feedback
            };
        end
    end

    // Clock generation
    always #5 clk = ~clk;

    // Test sequence
    integer test_idx;
    integer bit_idx;
    reg [7:0] msg8;
    reg [15:0] msg16;
    reg [15:0] expected;

    // Include private vectors (defines an array of {message, length, expected_crc})
    `include "evaluation/private/tb_sr1_vectors.v"

    initial begin
        clk = 0;
        rst_n = 0;
        enable = 0;
        data_in = 0;
        test_idx = 0;

        // Apply reset and check FR1
        @(posedge clk);
        #1; // small delay to allow outputs to settle
        if (crc_out_dut !== 16'hFFFF) begin
            $display("[TEST] FAIL: FR1: crc_out after reset is %h, expected FFFF", crc_out_dut);
        end else begin
            $display("[TEST] PASS: FR1");
        end

        // Release reset
        @(posedge clk);
        rst_n <= 1;

        // FR2: message 0x31 (8 bits, MSB-first)
        msg8 = 8'h31;
        expected = 16'hC0A7;
        // Shift in 8 bits
        for (bit_idx = 7; bit_idx >= 0; bit_idx = bit_idx - 1) begin
            @(posedge clk);
            enable <= 1;
            data_in <= msg8[bit_idx];
        end
        // Hold enable low for one cycle to let output settle
        @(posedge clk);
        enable <= 0;
        @(posedge clk);
        #1;
        if (crc_out_dut !== expected) begin
            $display("[TEST] FAIL: FR2: crc_out after 0x31 is %h, expected %h", crc_out_dut, expected);
        end else begin
            $display("[TEST] PASS: FR2");
        end

        // Reset before next test
        @(posedge clk);
        rst_n <= 0;
        @(posedge clk);
        rst_n <= 1;

        // FR3: message 0x1234 (16 bits, MSB-first)
        msg16 = 16'h1234;
        expected = 16'hDFB3;
        for (bit_idx = 15; bit_idx >= 0; bit_idx = bit_idx - 1) begin
            @(posedge clk);
            enable <= 1;
            data_in <= msg16[bit_idx];
        end
        @(posedge clk);
        enable <= 0;
        @(posedge clk);
        #1;
        if (crc_out_dut !== expected) begin
            $display("[TEST] FAIL: FR3: crc_out after 0x1234 is %h, expected %h", crc_out_dut, expected);
        end else begin
            $display("[TEST] PASS: FR3");
        end

        // SR1: functional equivalence over all vectors (public + private)
        // Public vectors: FR2 and FR3 already tested above; we'll re-run them as part of the vector list
        // Private vectors are included from tb_sr1_vectors.v
        // The private file defines:
        //   integer sr1_num_vectors;
        //   reg [7:0] sr1_messages [0:255];   // up to 256 vectors, each up to 255 bytes
        //   reg [7:0] sr1_lengths [0:255];    // length in bytes
        //   reg [15:0] sr1_expected [0:255];  // expected CRC
        // We'll iterate over all vectors and compare DUT vs reference cycle by cycle.
        begin
            integer vec;
            integer byte_idx;
            integer bit_idx2;
            reg [7:0] byte_val;
            reg [15:0] dut_crc;
            reg [15:0] ref_crc;
            reg mismatch;

            mismatch = 0;

            // First, add the two public vectors to the list for completeness
            // We'll just run them again as part of the loop; the private file may also include them.
            // The private file is expected to contain all vectors (public + private) for SR1.
            // If not, we'll still check them separately below.

            // Run all vectors from the private file
            for (vec = 0; vec < sr1_num_vectors; vec = vec + 1) begin
                // Reset
                @(posedge clk);
                rst_n <= 0;
                @(posedge clk);
                rst_n <= 1;

                // Shift in message bytes MSB-first
                for (byte_idx = 0; byte_idx < sr1_lengths[vec]; byte_idx = byte_idx + 1) begin
                    byte_val = sr1_messages[vec * 256 + byte_idx]; // flattened 2D array access
                    for (bit_idx2 = 7; bit_idx2 >= 0; bit_idx2 = bit_idx2 - 1) begin
                        @(posedge clk);
                        enable <= 1;
                        data_in <= byte_val[bit_idx2];
                    end
                end

                // Hold enable low
                @(posedge clk);
                enable <= 0;
                @(posedge clk);
                #1;

                dut_crc = crc_out_dut;
                ref_crc = crc_out_ref;

                if (dut_crc !== ref_crc) begin
                    $display("[TEST] FAIL: SR1: functional equivalence failed at vector %0d (DUT=%h, REF=%h)", vec, dut_crc, ref_crc);
                    mismatch = 1;
                end
            end

            // Also explicitly re-check FR2 and FR3 vectors if they weren't in the private file
            // (The private file should include them, but we'll be safe)
            // FR2
            @(posedge clk);
            rst_n <= 0;
            @(posedge clk);
            rst_n <= 1;
            msg8 = 8'h31;
            for (bit_idx = 7; bit_idx >= 0; bit_idx = bit_idx - 1) begin
                @(posedge clk);
                enable <= 1;
                data_in <= msg8[bit_idx];
            end
            @(posedge clk);
            enable <= 0;
            @(posedge clk);
            #1;
            if (crc_out_dut !== 16'hC0A7) begin
                $display("[TEST] FAIL: SR1: functional equivalence failed on FR2 vector (DUT=%h, expected C0A7)", crc_out_dut);
                mismatch = 1;
            end

            // FR3
            @(posedge clk);
            rst_n <= 0;
            @(posedge clk);
            rst_n <= 1;
            msg16 = 16'h1234;
            for (bit_idx = 15; bit_idx >= 0; bit_idx = bit_idx - 1) begin
                @(posedge clk);
                enable <= 1;
                data_in <= msg16[bit_idx];
            end
            @(posedge clk);
            enable <= 0;
            @(posedge clk);
            #1;
            if (crc_out_dut !== 16'hDFB3) begin
                $display("[TEST] FAIL: SR1: functional equivalence failed on FR3 vector (DUT=%h, expected DFB3)", crc_out_dut);
                mismatch = 1;
            end

            if (!mismatch) begin
                $display("[TEST] PASS: SR1");
            end
        end

        $finish;
    end

endmodule