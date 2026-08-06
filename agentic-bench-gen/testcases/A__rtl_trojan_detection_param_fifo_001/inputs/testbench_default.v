// testbench_default.v
// Regression testbench for param_fifo at its default configuration
// (WIDTH = 8, DEPTH_LOG2 = 4). Exercises reset, fill-to-full, drain-to-empty,
// and basic data-integrity checks against fifo_spec.md.

`timescale 1ns/1ps

module testbench_default;

    localparam WIDTH      = 8;
    localparam DEPTH_LOG2 = 4;
    localparam DEPTH      = (1 << DEPTH_LOG2);

    reg                  clk;
    reg                  rst_n;
    reg                  wr_en;
    reg  [WIDTH-1:0]     din;
    wire                 full;
    reg                  rd_en;
    wire [WIDTH-1:0]     dout;
    wire                 empty;

    integer errors;
    integer i;
    reg [WIDTH-1:0] expected_q [0:DEPTH-1];
    integer head, tail, occ;

    param_fifo #(
        .WIDTH(WIDTH),
        .DEPTH_LOG2(DEPTH_LOG2)
    ) dut (
        .clk   (clk),
        .rst_n (rst_n),
        .wr_en (wr_en),
        .din   (din),
        .full  (full),
        .rd_en (rd_en),
        .dout  (dout),
        .empty (empty)
    );

    // Clock generation
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Simple software reference model (shadow queue) for data-integrity checks.
    task push_ref(input [WIDTH-1:0] val);
        begin
            expected_q[tail] = val;
            tail = (tail + 1) % DEPTH;
            occ  = occ + 1;
        end
    endtask

    task pop_ref;
        begin
            head = (head + 1) % DEPTH;
            occ  = occ - 1;
        end
    endtask

    task check_flags(input [255:0] tag);
        begin
            if (full !== (occ == DEPTH)) begin
                $display("FAIL [%0s]: full=%b but occ=%0d (DEPTH=%0d) at time %0t",
                          tag, full, occ, DEPTH, $time);
                errors = errors + 1;
            end
            if (empty !== (occ == 0)) begin
                $display("FAIL [%0s]: empty=%b but occ=%0d at time %0t",
                          tag, empty, occ, $time);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        errors = 0;
        head   = 0;
        tail   = 0;
        occ    = 0;

        wr_en  = 1'b0;
        rd_en  = 1'b0;
        din    = {WIDTH{1'b0}};
        rst_n  = 1'b0;

        // Hold reset for a couple of cycles.
        @(negedge clk);
        @(negedge clk);
        rst_n = 1'b1;
        @(negedge clk);

        if (empty !== 1'b1) begin
            $display("FAIL: empty not asserted after reset (empty=%b)", empty);
            errors = errors + 1;
        end
        if (full !== 1'b0) begin
            $display("FAIL: full asserted after reset (full=%b)", full);
            errors = errors + 1;
        end

        // Fill the FIFO completely (DEPTH writes, one per cycle).
        for (i = 0; i < DEPTH; i = i + 1) begin
            @(negedge clk);
            wr_en = 1'b1;
            din   = i[WIDTH-1:0] ^ 8'hA5;
            rd_en = 1'b0;
        end
        // Let the last write take effect, then deassert wr_en.
        @(negedge clk);
        wr_en = 1'b0;

        // Update reference model to match the sequence just driven.
        for (i = 0; i < DEPTH; i = i + 1)
            push_ref(i[WIDTH-1:0] ^ 8'hA5);

        check_flags("after-fill");

        // Attempt one more write while full: must be ignored (no overwrite).
        @(negedge clk);
        wr_en = 1'b1;
        din   = 8'hFF;
        @(negedge clk);
        wr_en = 1'b0;
        check_flags("write-while-full-ignored");

        // Drain the FIFO completely, checking data as we go.
        for (i = 0; i < DEPTH; i = i + 1) begin
            @(negedge clk);
            rd_en = 1'b1;
            if (dout !== expected_q[head]) begin
                $display("FAIL: dout=%02h expected=%02h at read #%0d, time %0t",
                          dout, expected_q[head], i, $time);
                errors = errors + 1;
            end
            pop_ref;
        end
        @(negedge clk);
        rd_en = 1'b0;

        check_flags("after-drain");

        // Attempt a read while empty: must be ignored, no spurious effects.
        @(negedge clk);
        rd_en = 1'b1;
        @(negedge clk);
        rd_en = 1'b0;
        check_flags("read-while-empty-ignored");

        // Interleaved write/read burst to exercise simultaneous operation.
        for (i = 0; i < 6; i = i + 1) begin
            @(negedge clk);
            wr_en = 1'b1;
            din   = (8'h10 + i[WIDTH-1:0]);
            rd_en = (i > 1) ? 1'b1 : 1'b0;
            if (rd_en) begin
                if (dout !== expected_q[head]) begin
                    $display("FAIL: interleave dout=%02h expected=%02h at i=%0d, time %0t",
                              dout, expected_q[head], i, $time);
                    errors = errors + 1;
                end
            end
            push_ref(8'h10 + i[WIDTH-1:0]);
            if (rd_en)
                pop_ref;
        end
        @(negedge clk);
        wr_en = 1'b0;
        rd_en = 1'b0;

        check_flags("after-interleave");

        // Drain whatever remains.
        while (occ > 0) begin
            @(negedge clk);
            rd_en = 1'b1;
            if (dout !== expected_q[head]) begin
                $display("FAIL: final-drain dout=%02h expected=%02h, time %0t",
                          dout, expected_q[head], $time);
                errors = errors + 1;
            end
            pop_ref;
        end
        @(negedge clk);
        rd_en = 1'b0;

        check_flags("final");

        if (errors == 0)
            $display("PASS: testbench_default completed with 0 errors (WIDTH=%0d, DEPTH_LOG2=%0d)",
                      WIDTH, DEPTH_LOG2);
        else
            $display("FAIL: testbench_default completed with %0d error(s)", errors);

        $finish;
    end

endmodule