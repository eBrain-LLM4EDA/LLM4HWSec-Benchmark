// testbench_hd_trace.v
//
// Self-contained testbench for round_datapath. Drives a modest set of
// representative plaintext vectors combined with a small set of fixed
// round_key values, and prints a CSV-like trace of every pipeline register
// on every clock cycle. This produces raw simulation data only; it performs
// no variance computation or leakage judgement itself. Post-process the
// printed lines according to power_model.md to compute hd_variance per
// signal.
//
// Run with:
//   iverilog -g2012 -o sim.out inputs/round_datapath.v inputs/sbox_table.v inputs/testbench_hd_trace.v
//   vvp sim.out

`timescale 1ns/1ps

module testbench_hd_trace;

    reg        clk;
    reg        rst;
    reg  [7:0] plaintext;
    reg  [7:0] round_key;
    wire [7:0] round_out;

    integer cycle_count;
    integer key_idx;
    integer vec_idx;

    // 12 representative plaintext vectors (not exhaustive, hand-reviewable)
    reg [7:0] plaintext_vectors [0:11];

    // 3 fixed round-key values
    reg [7:0] key_vectors [0:2];

    round_datapath dut (
        .clk        (clk),
        .rst        (rst),
        .plaintext  (plaintext),
        .round_key  (round_key),
        .round_out  (round_out)
    );

    // 10ns clock period
    initial clk = 1'b0;
    always #5 clk = ~clk;

    initial begin
        plaintext_vectors[0]  = 8'h00;
        plaintext_vectors[1]  = 8'h01;
        plaintext_vectors[2]  = 8'h02;
        plaintext_vectors[3]  = 8'h04;
        plaintext_vectors[4]  = 8'h08;
        plaintext_vectors[5]  = 8'h10;
        plaintext_vectors[6]  = 8'h20;
        plaintext_vectors[7]  = 8'h40;
        plaintext_vectors[8]  = 8'h80;
        plaintext_vectors[9]  = 8'hff;
        plaintext_vectors[10] = 8'h5a;
        plaintext_vectors[11] = 8'ha5;

        key_vectors[0] = 8'h3c;
        key_vectors[1] = 8'h96;
        key_vectors[2] = 8'he1;
    end

    // Header for the CSV-like trace
    initial begin
        $display("cycle,plaintext,round_key,plaintext_reg,key_mix_reg,sbox_out_reg,round_out_reg");
    end

    initial begin
        cycle_count = 0;

        // Apply reset
        rst       = 1'b1;
        plaintext = 8'h00;
        round_key = 8'h00;
        @(posedge clk);
        @(posedge clk);
        rst = 1'b0;

        // Sweep every plaintext vector against every key vector.
        // A few settle cycles are inserted after each new input so the
        // full pipeline (plaintext_reg -> key_mix_reg -> sbox_out_reg ->
        // round_out_reg) has propagated the new value before the next
        // input change, giving a clean consecutive-cycle transition trace
        // per register.
        for (key_idx = 0; key_idx < 3; key_idx = key_idx + 1) begin
            for (vec_idx = 0; vec_idx < 12; vec_idx = vec_idx + 1) begin
                plaintext = plaintext_vectors[vec_idx];
                round_key = key_vectors[key_idx];

                // hold this input for 5 clock cycles, logging every cycle
                repeat (5) begin
                    @(posedge clk);
                    #1; // small delta to let non-blocking assigns settle
                    cycle_count = cycle_count + 1;
                    $display("%0d,%0d,%0d,%0d,%0d,%0d,%0d",
                              cycle_count,
                              plaintext,
                              round_key,
                              dut.plaintext_reg,
                              dut.key_mix_reg,
                              dut.sbox_out_reg,
                              dut.round_out_reg);
                end
            end
        end

        $finish;
    end

endmodule