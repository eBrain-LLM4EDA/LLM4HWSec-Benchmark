// uart_tx_tb.v
// Reference testbench for uart_tx: exercises normal 8N1 transmissions
// with a variety of data bytes and checks that tx_busy / tx_done timing
// follows the documented framing (see inputs/design_brief.md).

`timescale 1ns/1ps

module uart_tx_tb;

    reg        clk;
    reg        rst_n;
    reg  [7:0] tx_data;
    reg        tx_start;

    wire       tx;
    wire       tx_busy;
    wire       tx_done;
    wire [3:0] status_dbg;

    integer    errors;
    integer    i;

    // Byte patterns exercised: a mix of MSB=0 and MSB=1 values, plus
    // a few edge patterns (all zeros, all ones).
    reg [7:0] test_bytes [0:5];

    uart_tx dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .tx_data    (tx_data),
        .tx_start   (tx_start),
        .tx         (tx),
        .tx_busy    (tx_busy),
        .tx_done    (tx_done),
        .status_dbg (status_dbg)
    );

    // 10ns period clock
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Monitor key signals for visual inspection during simulation.
    initial begin
        $display("time\tclk\trst_n\ttx_start\ttx_data\ttx\ttx_busy\ttx_done\tstatus_dbg");
        $monitor("%0t\t%b\t%b\t%b\t%h\t%b\t%b\t%b\t%h",
                  $time, clk, rst_n, tx_start, tx_data, tx, tx_busy, tx_done, status_dbg);
    end

    // Sends one byte: pulses tx_start for one clock while idle, then
    // waits for the transaction to complete (tx_busy deasserted and
    // tx_done pulsed), checking basic framing timing along the way.
    task send_byte(input [7:0] data_byte);
        integer bit_count;
        begin
            // Wait until idle (not busy) before starting a new frame.
            @(negedge clk);
            if (tx_busy !== 1'b0) begin
                $display("ERROR: expected tx_busy=0 before starting new frame at time %0t", $time);
                errors = errors + 1;
            end

            tx_data  = data_byte;
            tx_start = 1'b1;
            @(negedge clk);
            tx_start = 1'b0;

            // tx_busy should now be asserted for the duration of the frame.
            if (tx_busy !== 1'b1) begin
                $display("ERROR: expected tx_busy=1 right after tx_start at time %0t", $time);
                errors = errors + 1;
            end

            // Start bit: tx should be low.
            @(negedge clk);
            if (tx !== 1'b0) begin
                $display("ERROR: expected start bit (tx=0) at time %0t", $time);
                errors = errors + 1;
            end

            // 8 data bits, LSB first.
            bit_count = 0;
            while (bit_count < 8) begin
                @(negedge clk);
                if (tx !== data_byte[bit_count]) begin
                    $display("ERROR: data bit %0d mismatch: expected %b got %b at time %0t",
                              bit_count, data_byte[bit_count], tx, $time);
                    errors = errors + 1;
                end
                bit_count = bit_count + 1;
            end

            // Stop bit: tx should return high, tx_busy should deassert,
            // and tx_done should pulse for exactly this cycle.
            @(negedge clk);
            if (tx !== 1'b1) begin
                $display("ERROR: expected stop bit (tx=1) at time %0t", $time);
                errors = errors + 1;
            end
            if (tx_busy !== 1'b0) begin
                $display("ERROR: expected tx_busy=0 during stop bit at time %0t", $time);
                errors = errors + 1;
            end
            if (tx_done !== 1'b1) begin
                $display("ERROR: expected tx_done=1 pulse during stop bit at time %0t", $time);
                errors = errors + 1;
            end

            // One cycle later, tx_done should have deasserted again.
            @(negedge clk);
            if (tx_done !== 1'b0) begin
                $display("ERROR: expected tx_done=0 after stop bit pulse at time %0t", $time);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        errors   = 0;
        rst_n    = 1'b0;
        tx_data  = 8'h00;
        tx_start = 1'b0;

        test_bytes[0] = 8'h00; // MSB=0
        test_bytes[1] = 8'h55; // MSB=0, alternating
        test_bytes[2] = 8'h7F; // MSB=0, max low bits
        test_bytes[3] = 8'h80; // MSB=1
        test_bytes[4] = 8'hAA; // MSB=1, alternating
        test_bytes[5] = 8'hFF; // MSB=1, all ones

        // Hold reset for a few cycles.
        repeat (3) @(negedge clk);
        rst_n = 1'b1;
        repeat (2) @(negedge clk);

        for (i = 0; i < 6; i = i + 1) begin
            send_byte(test_bytes[i]);
            // Small idle gap between frames.
            repeat (2) @(negedge clk);
        end

        // Send a couple more frames back-to-back to further exercise
        // steady-state behavior after the initial bring-up frames.
        send_byte(8'h3C);
        send_byte(8'hC3);

        if (errors == 0) begin
            $display("TESTBENCH RESULT: PASS - all framing checks succeeded (%0d bytes sent)", 6 + 2);
        end else begin
            $display("TESTBENCH RESULT: FAIL - %0d framing check(s) failed", errors);
        end

        $finish;
    end

    // Safety timeout in case of unexpected hangs.
    initial begin
        #20000;
        $display("TESTBENCH RESULT: TIMEOUT - simulation did not finish in time");
        $finish;
    end

endmodule