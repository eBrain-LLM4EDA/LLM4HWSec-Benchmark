// testbench_harness.v
// Self-contained reference testbench for signature_compare.
// Runs 17 cases (full match + mismatch at each of 16 byte positions),
// printing a description and the measured cycle count (cycles elapsed
// from the cycle after `start` until `done` first asserts) for each.
//
// Provided for optional reference/cross-checking only via:
//   iverilog -g2012 -o sim inputs/signature_compare.v inputs/testbench_harness.v
//   vvp sim

`timescale 1ns/1ps

module testbench_harness;

    reg        clk;
    reg        rst_n;
    reg        start;
    reg  [7:0] expected_byte;
    reg  [7:0] received_byte;
    reg        byte_valid;
    wire       done;
    wire       match;

    integer cycle_count;
    integer i;
    integer mismatch_pos; // -1 means full match, else 0..15

    signature_compare dut (
        .clk           (clk),
        .rst_n         (rst_n),
        .start         (start),
        .expected_byte (expected_byte),
        .received_byte (received_byte),
        .byte_valid    (byte_valid),
        .done          (done),
        .match         (match)
    );

    // Clock generation: 10ns period
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Runs one full comparison case, streaming 16 byte pairs and
    // injecting a mismatch at byte position `mpos` (or none if mpos < 0).
    task run_case;
        input integer mpos;
        input [8*32-1:0] label;
        begin
            // Reset
            rst_n         = 1'b0;
            start         = 1'b0;
            byte_valid    = 1'b0;
            expected_byte = 8'h00;
            received_byte = 8'h00;
            @(posedge clk);
            @(posedge clk);
            rst_n = 1'b1;
            @(posedge clk);

            // Issue one-cycle start pulse
            start = 1'b1;
            @(posedge clk);
            start = 1'b0;

            cycle_count = 0;

            // Stream 16 byte pairs, one per cycle, counting cycles
            // until done asserts.
            for (i = 0; i < 16; i = i + 1) begin
                if (i == mpos) begin
                    expected_byte = 8'hA5;
                    received_byte = 8'h5A;
                end
                else begin
                    expected_byte = i[7:0];
                    received_byte = i[7:0];
                end
                byte_valid = 1'b1;
                @(posedge clk);
                cycle_count = cycle_count + 1;
                if (done) begin
                    byte_valid = 1'b0;
                    i = 16; // break
                end
            end

            // In case done asserts exactly on/after the last streamed
            // byte, keep clocking (with byte_valid low) until done is
            // observed, bounded to avoid infinite loop.
            byte_valid = 1'b0;
            while (!done && cycle_count < 64) begin
                @(posedge clk);
                cycle_count = cycle_count + 1;
            end

            $display("%-28s cycles_to_done=%0d match=%0d", label, cycle_count, match);
        end
    endtask

    initial begin
        run_case(-1, "full_match");
        run_case(0,  "mismatch_pos_0");
        run_case(1,  "mismatch_pos_1");
        run_case(2,  "mismatch_pos_2");
        run_case(3,  "mismatch_pos_3");
        run_case(4,  "mismatch_pos_4");
        run_case(5,  "mismatch_pos_5");
        run_case(6,  "mismatch_pos_6");
        run_case(7,  "mismatch_pos_7");
        run_case(8,  "mismatch_pos_8");
        run_case(9,  "mismatch_pos_9");
        run_case(10, "mismatch_pos_10");
        run_case(11, "mismatch_pos_11");
        run_case(12, "mismatch_pos_12");
        run_case(13, "mismatch_pos_13");
        run_case(14, "mismatch_pos_14");
        run_case(15, "mismatch_pos_15");

        $finish;
    end

endmodule