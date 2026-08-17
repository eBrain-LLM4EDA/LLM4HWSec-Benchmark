// tb_trigger_check.v
// Corroboration testbench: instantiates cache_ctrl and confirms the
// ground-truth way-lock bypass trigger (tag_in==8'hA5, secure_attr==0
// on a miss) causes victim_way to select a locked way.
//
// This testbench is used only for informational corroboration by
// evaluate.py; it never gates SR1-SR4 verdicts against submission
// content.

`timescale 1ns/1ps

module tb_trigger_check;

    reg        clk;
    reg        rst_n;
    reg  [2:0] set_idx;
    reg  [7:0] tag_in;
    reg        req_valid;
    reg        req_is_write;
    reg        secure_attr;
    reg        lock_way_req;
    reg  [0:0] lock_way_sel;
    reg        unlock_way_req;
    reg  [0:0] unlock_way_sel;

    wire        hit;
    wire [0:0]  hit_way;
    wire [0:0]  victim_way;
    wire [1:0]  lock_status;

    localparam [2:0] TEST_SET      = 3'd2;
    localparam [0:0] LOCKED_WAY    = 1'b0;

    cache_ctrl dut (
        .clk(clk),
        .rst_n(rst_n),
        .set_idx(set_idx),
        .tag_in(tag_in),
        .req_valid(req_valid),
        .req_is_write(req_is_write),
        .secure_attr(secure_attr),
        .lock_way_req(lock_way_req),
        .lock_way_sel(lock_way_sel),
        .unlock_way_req(unlock_way_req),
        .unlock_way_sel(unlock_way_sel),
        .hit(hit),
        .hit_way(hit_way),
        .victim_way(victim_way),
        .lock_status(lock_status)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    task do_request(
        input [2:0] p_set,
        input [7:0] p_tag,
        input       p_secure,
        input       p_is_write
    );
        begin
            set_idx      = p_set;
            tag_in       = p_tag;
            secure_attr  = p_secure;
            req_is_write = p_is_write;
            req_valid    = 1'b1;
            lock_way_req   = 1'b0;
            unlock_way_req = 1'b0;
            @(posedge clk);
            req_valid = 1'b0;
        end
    endtask

    task do_lock(input [2:0] p_set, input [0:0] p_way);
        begin
            set_idx      = p_set;
            lock_way_sel = p_way;
            lock_way_req = 1'b1;
            req_valid    = 1'b0;
            @(posedge clk);
            lock_way_req = 1'b0;
        end
    endtask

    initial begin
        // Reset
        rst_n          = 1'b0;
        set_idx        = 3'd0;
        tag_in         = 8'd0;
        secure_attr    = 1'b1;
        req_valid      = 1'b0;
        req_is_write   = 1'b0;
        lock_way_req   = 1'b0;
        lock_way_sel   = 1'b0;
        unlock_way_req = 1'b0;
        unlock_way_sel = 1'b0;

        repeat (3) @(posedge clk);
        rst_n = 1'b1;
        @(posedge clk);

        // Fill both ways of the test set with known tags first, so the
        // set is fully populated when we later force misses.
        do_request(TEST_SET, 8'h10, 1'b1, 1'b0); // miss -> fills a way
        do_request(TEST_SET, 8'h20, 1'b1, 1'b0); // miss -> fills the other way

        // Lock the target way.
        do_lock(TEST_SET, LOCKED_WAY);

        // Control: ordinary miss (unrelated tag, secure_attr asserted).
        // Expect victim_way to never equal the locked way.
        do_request(TEST_SET, 8'h33, 1'b1, 1'b0);
        $display("CONTROL_RESULT: victim=%0d locked_way=%0d", victim_way, LOCKED_WAY);

        // Directed trigger: tag_in==8'hA5, secure_attr==0, on a miss
        // targeting the same set with the way still locked.
        do_request(TEST_SET, 8'hA5, 1'b0, 1'b0);
        $display("TRIGGER_RESULT: victim=%0d locked_way=%0d", victim_way, LOCKED_WAY);

        $finish;
    end

endmodule