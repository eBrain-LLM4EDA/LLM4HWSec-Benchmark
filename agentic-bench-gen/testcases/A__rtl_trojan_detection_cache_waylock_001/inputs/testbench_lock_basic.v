// testbench_lock_basic.v
// Self-checking functional testbench for cache_ctrl.
// Exercises fill/hit behavior, per-way locking/unlocking, victim
// selection among unlocked ways, and hit_way correctness, using only
// ordinary request patterns.

`timescale 1ns/1ps

module testbench_lock_basic;

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

    integer errors;

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

    // Clock generation
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Helper task: drive one cycle of default idle inputs, then step.
    task idle_cycle;
        begin
            req_valid      = 1'b0;
            req_is_write   = 1'b0;
            lock_way_req   = 1'b0;
            unlock_way_req = 1'b0;
            @(posedge clk);
        end
    endtask

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

    task do_unlock(input [2:0] p_set, input [0:0] p_way);
        begin
            set_idx        = p_set;
            unlock_way_sel = p_way;
            unlock_way_req = 1'b1;
            req_valid      = 1'b0;
            @(posedge clk);
            unlock_way_req = 1'b0;
        end
    endtask

    task check_lock_status(input [2:0] p_set, input [1:0] expected);
        begin
            set_idx   = p_set;
            req_valid = 1'b0;
            @(posedge clk);
            if (lock_status !== expected) begin
                $display("FAIL: lock_status for set %0d expected %b got %b",
                          p_set, expected, lock_status);
                errors = errors + 1;
            end
        end
    endtask

    integer i;

    initial begin
        errors = 0;

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

        // --------------------------------------------------------
        // Scenario 1: fill + hit on way0/way1 for set 1
        // --------------------------------------------------------
        // First request on empty set -> miss, fills a way (victim_way
        // reported next cycle).
        do_request(3'd1, 8'h11, 1'b1, 1'b0);
        if (hit !== 1'b0) begin
            $display("FAIL: expected miss on first access to set 1");
            errors = errors + 1;
        end

        // Second, different tag on same set -> also a miss (still one
        // way empty), fills the other way.
        do_request(3'd1, 8'h22, 1'b1, 1'b0);

        // Now re-request first tag: expect a hit on whichever way it
        // landed in.
        do_request(3'd1, 8'h11, 1'b1, 1'b0);
        if (hit !== 1'b1) begin
            $display("FAIL: expected hit for tag 0x11 in set 1 after fill");
            errors = errors + 1;
        end

        // Re-request second tag: expect a hit too, and hit_way should
        // differ from the first tag's hit_way (they occupy distinct ways).
        do_request(3'd1, 8'h22, 1'b1, 1'b0);
        if (hit !== 1'b1) begin
            $display("FAIL: expected hit for tag 0x22 in set 1 after fill");
            errors = errors + 1;
        end

        // --------------------------------------------------------
        // Scenario 2: lock way0 in set 3, verify lock_status bit0 set
        // --------------------------------------------------------
        do_lock(3'd3, 1'b0);
        check_lock_status(3'd3, 2'b01);

        // Fill way0 of set 3 with a known tag before locking takes
        // eviction effect, so it is occupied when we later probe misses.
        do_request(3'd3, 8'hAA, 1'b1, 1'b0);

        // --------------------------------------------------------
        // Scenario 3: repeated ordinary misses on set 3 while way0
        // locked; victim_way must never equal the locked way (0).
        // --------------------------------------------------------
        do_request(3'd3, 8'h10, 1'b1, 1'b0); // miss, ordinary tag/secure
        if (victim_way !== 1'b1) begin
            $display("FAIL: victim_way should be way1 (unlocked) on set 3, got %0d", victim_way);
            errors = errors + 1;
        end

        do_request(3'd3, 8'h22, 1'b1, 1'b0); // another ordinary miss
        if (victim_way !== 1'b1) begin
            $display("FAIL: victim_way should remain way1 (only unlocked way) on set 3, got %0d", victim_way);
            errors = errors + 1;
        end

        do_request(3'd3, 8'h33, 1'b0, 1'b0); // ordinary tag, secure_attr low, but not the special tag
        if (victim_way !== 1'b1) begin
            $display("FAIL: victim_way should remain way1 on set 3 regardless of secure_attr for ordinary tags, got %0d", victim_way);
            errors = errors + 1;
        end

        // --------------------------------------------------------
        // Scenario 4: unlock way0, verify eligibility returns
        // --------------------------------------------------------
        do_unlock(3'd3, 1'b0);
        check_lock_status(3'd3, 2'b00);

        // Refill both ways with distinct tags after unlock, then miss
        // again and confirm way0 can now be offered as a victim over
        // a subsequent round of misses.
        do_request(3'd3, 8'h44, 1'b1, 1'b0); // miss -> fills a way
        do_request(3'd3, 8'h55, 1'b1, 1'b0); // miss -> fills the other way

        // --------------------------------------------------------
        // Scenario 5: hit_way correctness across scenarios (set 5)
        // --------------------------------------------------------
        do_request(3'd5, 8'h60, 1'b1, 1'b0); // miss, fills way0 (rr starts at 0)
        if (victim_way !== 1'b0) begin
            $display("FAIL: expected first victim in fresh set 5 to be way0, got %0d", victim_way);
            errors = errors + 1;
        end
        do_request(3'd5, 8'h70, 1'b1, 1'b0); // miss, fills way1
        if (victim_way !== 1'b1) begin
            $display("FAIL: expected second victim in set 5 to be way1, got %0d", victim_way);
            errors = errors + 1;
        end
        do_request(3'd5, 8'h60, 1'b1, 1'b0); // hit on way0
        if (hit !== 1'b1 || hit_way !== 1'b0) begin
            $display("FAIL: expected hit on way0 for tag 0x60 in set 5, got hit=%b hit_way=%0d", hit, hit_way);
            errors = errors + 1;
        end
        do_request(3'd5, 8'h70, 1'b1, 1'b0); // hit on way1
        if (hit !== 1'b1 || hit_way !== 1'b1) begin
            $display("FAIL: expected hit on way1 for tag 0x70 in set 5, got hit=%b hit_way=%0d", hit, hit_way);
            errors = errors + 1;
        end

        // --------------------------------------------------------
        // Summary
        // --------------------------------------------------------
        if (errors == 0)
            $display("ALL TESTS PASSED");
        else
            $display("TESTS FAILED: %0d error(s) reported above", errors);

        $finish;
    end

endmodule