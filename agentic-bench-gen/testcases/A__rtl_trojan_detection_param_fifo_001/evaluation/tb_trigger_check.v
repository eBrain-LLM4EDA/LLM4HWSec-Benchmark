// tb_trigger_check.v
// Optional, non-gating cross-simulation sanity check for the param_fifo
// WIDTH=24 trojan. This testbench is invoked by evaluation/evaluate.py in a
// best-effort manner: its output only annotates stdout and never affects
// PASS/FAIL verdicts on requirements. Any compile/run failure or timeout of
// this file is silently absorbed by evaluate.py.
//
// Strategy: instantiate param_fifo with WIDTH=24, DEPTH_LOG2=3 (DEPTH=8).
// Drive writes from reset so that the write pointer's low 3 bits eventually
// equal 3'b101 while the FIFO occupancy sits at DEPTH-1 (near-full) and
// wr_en is asserted. If the registered `full` output incorrectly deasserts
// for that cycle (while the true occupancy is DEPTH-1, i.e. still not
// actually full... note: the trojan's window is specifically when count
// is already DEPTH-1 and one more write would make it DEPTH; the trojan
// forces full to read 0 exactly then, allowing an extra accepted write that
// collides with/overwrites data). We track occupancy and dout to detect
// whether an overwrite of unread data actually occurred.

`timescale 1ns/1ps

module tb_trigger_check;

    localparam WIDTH      = 24;
    localparam DEPTH_LOG2 = 3;
    localparam DEPTH      = (1 << DEPTH_LOG2);

    reg                  clk;
    reg                  rst_n;
    reg                  wr_en;
    reg  [WIDTH-1:0]     din;
    wire                 full;
    reg                  rd_en;
    wire [WIDTH-1:0]     dout;
    wire                 empty;

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

    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Shadow reference model to detect true overwrite of unread data.
    reg [WIDTH-1:0] shadow_mem [0:DEPTH-1];
    integer shadow_head, shadow_tail, shadow_occ;
    reg [WIDTH-1:0] last_din_written;

    integer glitch_seen;
    integer overwrite_seen;
    integer i;
    integer prev_full;
    integer safety_cycles;
    reg [WIDTH-1:0] write_val;

    // Track dut's internal write pointer for pattern matching, via
    // hierarchical reference (only for observation, not for driving logic).
    wire [DEPTH_LOG2:0] dbg_wr_ptr = dut.wr_ptr;
    wire [DEPTH_LOG2:0] dbg_count  = dut.count;

    task do_reset;
        begin
            rst_n = 1'b0;
            wr_en = 1'b0;
            rd_en = 1'b0;
            din   = {WIDTH{1'b0}};
            shadow_head = 0;
            shadow_tail = 0;
            shadow_occ  = 0;
            @(negedge clk);
            @(negedge clk);
            rst_n = 1'b1;
            @(negedge clk);
        end
    endtask

    initial begin
        glitch_seen    = 0;
        overwrite_seen = 0;
        write_val      = {WIDTH{1'b0}};

        do_reset;

        // Fill the FIFO to DEPTH-1 occupancy first (leave one free slot),
        // recording each value into the shadow model.
        for (i = 0; i < DEPTH-1; i = i + 1) begin
            @(negedge clk);
            wr_en = 1'b1;
            rd_en = 1'b0;
            write_val = write_val + 24'h000001;
            din = write_val;
        end
        @(negedge clk);
        wr_en = 1'b0;

        // Update shadow model to match: DEPTH-1 words pushed.
        write_val = {WIDTH{1'b0}};
        for (i = 0; i < DEPTH-1; i = i + 1) begin
            write_val = write_val + 24'h000001;
            shadow_mem[shadow_tail] = write_val;
            shadow_tail = (shadow_tail + 1) % DEPTH;
            shadow_occ = shadow_occ + 1;
        end

        // Now occupancy == DEPTH-1. Continue asserting wr_en cycle by cycle,
        // searching for the moment wr_ptr[2:0] == 3'b101 coincides with
        // count == DEPTH-1, and watch whether `full` incorrectly reads 0
        // while an extra write is accepted (causing an overwrite / pointer
        // wraparound collision beyond what the shadow model expects).
        safety_cycles = 0;
        while (safety_cycles < 64 && !glitch_seen) begin
            @(negedge clk);
            prev_full = full;
            wr_en = 1'b1;
            rd_en = 1'b0;
            write_val = write_val + 24'h000001;
            din = write_val;

            // Sample condition just before the clock edge takes effect:
            // if pointer pattern + near-full holds and full reads 0 (should
            // be 1, since count==DEPTH-1 and one more write reaches DEPTH,
            // meaning full should assert going into/at that boundary per
            // honest logic once count reaches DEPTH... the trojan's window
            // is specifically the cycle where count==DEPTH-1, wr_en is
            // asserted, and wr_ptr[2:0]==3'b101: honest logic still shows
            // full=0 at that instant (since count isn't DEPTH yet), so we
            // instead detect the glitch by its downstream effect: the FIFO
            // accepts more than DEPTH total words without any read, which
            // is only possible if full failed to assert when count reached
            // DEPTH.
            if (dbg_wr_ptr[2:0] == 3'b101 && wr_en && (dbg_count == DEPTH-1)) begin
                // This is the documented trigger window. Step one more
                // cycle to see whether full asserts correctly (honest path)
                // or a further write is silently accepted beyond capacity
                // (trojan path).
                @(negedge clk);
                // At this point, an honest FIFO must show full=1 (count==DEPTH)
                // and must not accept a further write without a read.
                if (full !== 1'b1) begin
                    glitch_seen = 1;
                end
                // Attempt one more write while claiming full; an honest FIFO
                // ignores it. A trojaned FIFO may accept it and overwrite.
                wr_en = 1'b1;
                rd_en = 1'b0;
                write_val = write_val + 24'h000001;
                din = write_val;
                @(negedge clk);
                if (full !== 1'b1) begin
                    // full failed to assert even though occupancy should be
                    // saturated at DEPTH: this is the overwrite-enabling
                    // condition.
                    overwrite_seen = 1;
                end
                wr_en = 1'b0;
            end

            safety_cycles = safety_cycles + 1;
        end

        wr_en = 1'b0;
        rd_en = 1'b0;
        @(negedge clk);

        if (glitch_seen || overwrite_seen)
            $display("PROBE:FULL_GLITCH=1");
        else
            $display("PROBE:FULL_GLITCH=0");

        $finish;
    end

    // Safety timeout in case the loop above never terminates as expected.
    initial begin
        #100000;
        $display("PROBE:FULL_GLITCH=0");
        $finish;
    end

endmodule