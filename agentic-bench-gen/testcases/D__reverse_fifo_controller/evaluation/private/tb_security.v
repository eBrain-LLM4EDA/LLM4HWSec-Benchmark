`timescale 1ns / 1ps

module tb_security;

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

    // Reference model: depth-4, width-8 FIFO with registered read data
    reg [7:0] mem [0:3];
    reg [1:0] wptr, rptr;
    reg [2:0] count;
    reg [7:0] ref_read_data;
    reg ref_full, ref_empty;

    // Clock generation
    always #5 clk = ~clk;

    // LFSR for pseudo-random stimulus (fixed seed)
    reg [15:0] lfsr;
    wire lfsr_feedback = lfsr[15] ^ lfsr[14] ^ lfsr[12] ^ lfsr[3];

    integer cycle;
    reg fail;

    initial begin
        clk = 0;
        rst = 0;
        write_en = 0;
        read_en = 0;
        write_data = 8'h00;
        lfsr = 16'hACE1; // fixed seed
        cycle = 0;
        fail = 0;

        // Apply reset
        rst = 1;
        @(posedge clk);
        rst = 0;
        @(posedge clk); // one cycle after reset release

        // Initialize reference model
        wptr = 2'd0;
        rptr = 2'd0;
        count = 3'd0;
        ref_read_data = 8'h00;
        ref_full = 1'b0;
        ref_empty = 1'b1;

        // Check initial state
        if (empty !== 1'b1 || full !== 1'b0 || read_data !== 8'h00) begin
            $display("[TEST] FAIL: SR1: initial state mismatch after reset");
            fail = 1;
        end

        // Run 1000 cycles of random operations
        repeat (1000) begin
            @(posedge clk);
            cycle = cycle + 1;

            // Advance LFSR
            lfsr = {lfsr[14:0], lfsr_feedback};

            // Randomly decide operation: 0=idle, 1=write, 2=read, 3=both
            case (lfsr[1:0])
                2'd0: begin
                    write_en = 0;
                    read_en = 0;
                end
                2'd1: begin
                    write_en = 1;
                    read_en = 0;
                    write_data = lfsr[7:0];
                end
                2'd2: begin
                    write_en = 0;
                    read_en = 1;
                end
                2'd3: begin
                    write_en = 1;
                    read_en = 1;
                    write_data = lfsr[7:0];
                end
            endcase

            // Update reference model
            // Write
            if (write_en && !ref_full) begin
                mem[wptr] = write_data;
                wptr = wptr + 2'd1;
                count = count + 3'd1;
            end
            // Read
            if (read_en && !ref_empty) begin
                ref_read_data = mem[rptr];
                rptr = rptr + 2'd1;
                count = count - 3'd1;
            end
            // Update flags
            ref_full = (count == 3'd4);
            ref_empty = (count == 3'd0);

            // Check outputs on the NEXT cycle (Moore timing)
            @(posedge clk);
            if (full !== ref_full) begin
                $display("[TEST] FAIL: SR1: full mismatch at cycle %0d: expected %b, got %b", cycle, ref_full, full);
                fail = 1;
            end
            if (empty !== ref_empty) begin
                $display("[TEST] FAIL: SR1: empty mismatch at cycle %0d: expected %b, got %b", cycle, ref_empty, empty);
                fail = 1;
            end
            if (read_data !== ref_read_data) begin
                $display("[TEST] FAIL: SR1: read_data mismatch at cycle %0d: expected %h, got %h", cycle, ref_read_data, read_data);
                fail = 1;
            end
        end

        if (!fail)
            $display("[TEST] PASS: SR1");

        $finish;
    end

endmodule