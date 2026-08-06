`timescale 1ns / 1ps

module tb_fifo;

    reg clk;
    reg rst;
    reg [7:0] write_data;
    reg write_en;
    reg read_en;
    wire [7:0] read_data;
    wire full;
    wire empty;

    // Instantiate the submission
    fifo_controller uut (
        .clk(clk),
        .rst(rst),
        .write_data(write_data),
        .write_en(write_en),
        .read_en(read_en),
        .read_data(read_data),
        .full(full),
        .empty(empty)
    );

    // Clock generation: 10ns period
    always #5 clk = ~clk;

    // Task to apply reset
    task apply_reset;
        begin
            rst = 1;
            write_en = 0;
            read_en = 0;
            write_data = 8'h00;
            @(posedge clk);
            rst = 0;
            @(posedge clk); // one cycle after reset release, outputs should reflect reset state
        end
    endtask

    // Task to perform a write (assumes not full)
    task do_write;
        input [7:0] data;
        begin
            write_en = 1;
            write_data = data;
            @(posedge clk);
            write_en = 0;
        end
    endtask

    // Task to perform a read (assumes not empty)
    task do_read;
        begin
            read_en = 1;
            @(posedge clk);
            read_en = 0;
        end
    endtask

    // Task to perform simultaneous write and read
    task do_simultaneous;
        input [7:0] data;
        begin
            write_en = 1;
            read_en = 1;
            write_data = data;
            @(posedge clk);
            write_en = 0;
            read_en = 0;
        end
    endtask

    // Helper to check a condition and print result
    task check;
        input [255:0] desc;
        input condition;
        input [7:0] req_id;
        begin
            if (condition)
                $display("[TEST] PASS: %s", req_id);
            else
                $display("[TEST] FAIL: %s: %s", req_id, desc);
        end
    endtask

    // Main test sequence
    initial begin
        clk = 0;
        rst = 0;
        write_en = 0;
        read_en = 0;
        write_data = 8'h00;

        // Apply reset
        apply_reset();

        // After reset, check initial state: empty=1, full=0, read_data=0
        check("After reset, empty should be 1", empty === 1'b1, "FR1");
        check("After reset, full should be 0", full === 1'b0, "FR1");
        check("After reset, read_data should be 0", read_data === 8'h00, "FR1");

        // --- FR1: Write when empty ---
        // Write 0xAA when empty
        do_write(8'hAA);
        // Next cycle: empty should deassert, full still 0
        @(posedge clk);
        check("FR1: empty deasserted after write", empty === 1'b0, "FR1");
        check("FR1: full still 0 after one write", full === 1'b0, "FR1");

        // --- Fill FIFO to full (three more writes) ---
        do_write(8'hBB);
        @(posedge clk);
        do_write(8'hCC);
        @(posedge clk);
        do_write(8'hDD); // occupancy becomes 4
        @(posedge clk);
        // Now full should be asserted
        check("FR2: full asserted after fourth write", full === 1'b1, "FR2");

        // --- FR2: Read when full ---
        // Read when full: oldest data (0xAA) should appear on read_data next cycle, full deasserts
        do_read();
        @(posedge clk);
        check("FR2: read_data is oldest (0xAA) after read from full", read_data === 8'hAA, "FR2");
        check("FR2: full deasserted after read from full", full === 1'b0, "FR2");

        // --- FR4: Write when full ---
        // Attempt write when full (currently not full, so fill again)
        // We have 3 entries now (0xBB, 0xCC, 0xDD). Write one more to become full.
        do_write(8'hEE);
        @(posedge clk);
        check("FR4 prep: full asserted", full === 1'b1, "FR4");
        // Now attempt write when full
        write_en = 1;
        write_data = 8'hFF;
        @(posedge clk);
        write_en = 0;
        // State should not change: full still 1, read_data unchanged (still 0xAA from last read)
        @(posedge clk);
        check("FR4: full remains 1 after write when full", full === 1'b1, "FR4");
        check("FR4: read_data unchanged after write when full", read_data === 8'hAA, "FR4");

        // --- FR4: Read when empty ---
        // Empty the FIFO
        do_read(); // reads 0xBB
        @(posedge clk);
        do_read(); // reads 0xCC
        @(posedge clk);
        do_read(); // reads 0xDD
        @(posedge clk);
        do_read(); // reads 0xEE, now empty
        @(posedge clk);
        check("FR4 prep: empty asserted after last read", empty === 1'b1, "FR4");
        // Attempt read when empty
        read_en = 1;
        @(posedge clk);
        read_en = 0;
        // State should not change: empty still 1, read_data unchanged (last value 0xEE)
        @(posedge clk);
        check("FR4: empty remains 1 after read when empty", empty === 1'b1, "FR4");
        check("FR4: read_data unchanged after read when empty", read_data === 8'hEE, "FR4");

        // --- FR3: Simultaneous write and read when neither full nor empty ---
        // Write one entry to leave FIFO not empty
        do_write(8'h11);
        @(posedge clk);
        check("FR3 prep: not empty", empty === 1'b0, "FR3");
        check("FR3 prep: not full", full === 1'b0, "FR3");
        // Simultaneous write and read
        do_simultaneous(8'h22);
        @(posedge clk);
        // After simultaneous op: read_data should be the oldest (0x11), new data (0x22) stored, occupancy unchanged (still 1)
        check("FR3: read_data is oldest (0x11) after simultaneous op", read_data === 8'h11, "FR3");
        // Occupancy unchanged means empty still 0, full still 0
        check("FR3: empty still 0 after simultaneous op", empty === 1'b0, "FR3");
        check("FR3: full still 0 after simultaneous op", full === 1'b0, "FR3");
        // Next read should get 0x22
        do_read();
        @(posedge clk);
        check("FR3: subsequent read gets new data (0x22)", read_data === 8'h22, "FR3");

        // --- Additional edge: simultaneous when occupancy=1, leaving empty ---
        // Write one entry
        do_write(8'h33);
        @(posedge clk);
        // Simultaneous read and write: occupancy stays 1, read_data gets 0x33
        do_simultaneous(8'h44);
        @(posedge clk);
        check("FR3 edge: read_data is 0x33 after sim op with occupancy=1", read_data === 8'h33, "FR3");
        // Now read to get 0x44
        do_read();
        @(posedge clk);
        check("FR3 edge: read gets 0x44", read_data === 8'h44, "FR3");

        // --- Additional edge: simultaneous when occupancy=3, leaving full ---
        // Fill to occupancy=3
        do_write(8'h55);
        @(posedge clk);
        do_write(8'h66);
        @(posedge clk);
        do_write(8'h77);
        @(posedge clk);
        check("FR3 edge prep: occupancy=3, not full", full === 1'b0, "FR3");
        // Simultaneous write and read: occupancy stays 3, read_data gets 0x55
        do_simultaneous(8'h88);
        @(posedge clk);
        check("FR3 edge: read_data is 0x55 after sim op with occupancy=3", read_data === 8'h55, "FR3");
        // Now write one more to become full (occupancy 4)
        do_write(8'h99);
        @(posedge clk);
        check("FR3 edge: full after final write", full === 1'b1, "FR3");

        // --- Reset test: after reset, empty=1, full=0, read_data=0 ---
        apply_reset();
        @(posedge clk);
        check("Reset: empty=1 after reset", empty === 1'b1, "FR1");
        check("Reset: full=0 after reset", full === 1'b0, "FR1");
        check("Reset: read_data=0 after reset", read_data === 8'h00, "FR1");

        $finish;
    end

endmodule